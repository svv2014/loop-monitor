#!/usr/bin/env python3
"""Loop Monitor — FastAPI service tracking agent performance across Loop pipeline runs."""

import json
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

DB_PATH = Path(__file__).parent / "bounties.db"
STATIC_DIR = Path(__file__).parent / "static"
PORT = 18792


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS events (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ts        INTEGER NOT NULL,
            event     TEXT    NOT NULL,
            agent     TEXT,
            model     TEXT,
            role      TEXT,
            project   TEXT,
            issue_num INTEGER,
            pr_num    INTEGER,
            detail    TEXT
        );

        CREATE TABLE IF NOT EXISTS verdicts (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ts        INTEGER NOT NULL,
            pr_num    INTEGER NOT NULL,
            repo      TEXT    NOT NULL,
            outcome   TEXT    NOT NULL,
            points    INTEGER NOT NULL DEFAULT 0,
            model     TEXT,
            role      TEXT,
            project   TEXT,
            summary   TEXT
        );

        CREATE TABLE IF NOT EXISTS scores (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            model     TEXT    NOT NULL,
            role      TEXT    NOT NULL,
            project   TEXT    NOT NULL,
            total     INTEGER NOT NULL DEFAULT 0,
            wins      INTEGER NOT NULL DEFAULT 0,
            reworks   INTEGER NOT NULL DEFAULT 0,
            UNIQUE(model, role, project)
        );
        """
    )
    conn.commit()
    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Loop Monitor", version="1.0.0", lifespan=lifespan)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Request models ────────────────────────────────────────────────────────────

class ReportPayload(BaseModel):
    """Bounty event payload v1.0 — see Loop core's bounty event API spec.

    `api` is the API version sender claims to use. Monitor accepts 1.x
    (with unknown fields silently ignored) and rejects future majors with
    HTTP 426 in the dispatch handler. Missing `api` is treated as legacy
    v1.0 with a deprecation log entry.
    """
    api: Optional[str] = None              # e.g. "1.0"; v1.x accepted
    core_version: Optional[str] = None     # sender's loop core version, telemetry
    event: str
    agent: Optional[str] = None
    model: Optional[str] = None
    role: Optional[str] = None
    project: Optional[str] = None
    issue_num: Optional[int] = None
    pr_num: Optional[int] = None
    detail: Optional[str] = None
    timestamp: Optional[str] = None        # ISO 8601 UTC; client-set

    class Config:
        extra = "ignore"                   # gracefully ignore unknown fields (forward-compat)


class VerdictPayload(BaseModel):
    pr_num: int
    repo: str
    outcome: str        # clean | rework | qa-fail-rework | blocked
    points: int = 0
    model: Optional[str] = None
    role: Optional[str] = None
    project: Optional[str] = None
    summary: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

OUTCOME_POINTS = {
    "clean": 3,
    "rework": -1,
    "qa-fail-rework": -2,
    "blocked": 0,
}


def _upsert_score(conn: sqlite3.Connection, model: str, role: str, project: str,
                  points: int, outcome: str) -> None:
    m = model or "unknown"
    r = role or "unknown"
    p = project or "unknown"
    wins = 1 if outcome == "clean" else 0
    reworks = 1 if outcome in ("rework", "qa-fail-rework") else 0
    conn.execute(
        """
        INSERT INTO scores (model, role, project, total, wins, reworks)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(model, role, project) DO UPDATE SET
            total   = total   + excluded.total,
            wins    = wins    + excluded.wins,
            reworks = reworks + excluded.reworks
        """,
        (m, r, p, points, wins, reworks),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

SUPPORTED_API_MAJOR = "1"
MONITOR_VERSION = (Path(__file__).parent / "VERSION").read_text().strip() if (Path(__file__).parent / "VERSION").exists() else "unknown"


@app.get("/api/health")
def get_health():
    return {
        "status": "ok",
        "monitor_version": MONITOR_VERSION,
        "supported_bounty_api": f"{SUPPORTED_API_MAJOR}.x",
    }


@app.post("/api/report", status_code=201)
def post_report(payload: ReportPayload):
    # Version negotiation: accept v1.x; reject other majors with 426.
    api = (payload.api or "1.0").strip()
    major = api.split(".", 1)[0] if api else "1"
    if major != SUPPORTED_API_MAJOR:
        raise HTTPException(
            status_code=426,
            detail={
                "error": "version_unsupported",
                "supported": [f"{SUPPORTED_API_MAJOR}.x"],
                "received": api,
            },
        )

    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO events (ts, event, agent, model, role, project, issue_num, pr_num, detail)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(time.time()),
                payload.event,
                payload.agent,
                payload.model,
                payload.role,
                payload.project,
                payload.issue_num,
                payload.pr_num,
                payload.detail,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "monitor_version": MONITOR_VERSION}


@app.post("/api/verdict", status_code=201)
def post_verdict(payload: VerdictPayload):
    if payload.outcome not in OUTCOME_POINTS and payload.points == 0:
        pass  # allow custom outcomes with explicit points
    points = payload.points if payload.points != 0 else OUTCOME_POINTS.get(payload.outcome, 0)
    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO verdicts (ts, pr_num, repo, outcome, points, model, role, project, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(time.time()),
                payload.pr_num,
                payload.repo,
                payload.outcome,
                points,
                payload.model,
                payload.role,
                payload.project,
                payload.summary,
            ),
        )
        if payload.model or payload.role or payload.project:
            _upsert_score(conn, payload.model or "", payload.role or "",
                          payload.project or "", points, payload.outcome)
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "points": points}


@app.get("/api/board")
def get_board():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT model, role, project, total, wins, reworks FROM scores ORDER BY total DESC, wins DESC LIMIT 50"
        ).fetchall()
        return {"board": [dict(r) for r in rows]}
    finally:
        conn.close()


@app.get("/api/feed")
def get_feed(limit: int = 50):
    limit = min(limit, 200)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
        return {"feed": [dict(r) for r in rows]}
    finally:
        conn.close()


@app.get("/api/status")
def get_status():
    conn = get_db()
    try:
        ev_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        vd_count = conn.execute("SELECT COUNT(*) FROM verdicts").fetchone()[0]
        latest = conn.execute("SELECT ts FROM events ORDER BY ts DESC LIMIT 1").fetchone()
        return {
            "ok": True,
            "events": ev_count,
            "verdicts": vd_count,
            "last_event_ts": latest[0] if latest else None,
            "db": str(DB_PATH),
        }
    finally:
        conn.close()


@app.get("/api/projects")
def get_projects():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT DISTINCT project FROM events WHERE project IS NOT NULL ORDER BY project"
        ).fetchall()
        return {"projects": [r[0] for r in rows]}
    finally:
        conn.close()


@app.get("/", response_class=HTMLResponse)
def root():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return HTMLResponse("<h1>Loop Monitor</h1><p>Static files not found.</p>")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from server.constants import MONITOR_VERSION, SUPPORTED_API_MAJOR
from server.db import db_dep

router = APIRouter()

# --- pipeline health cache ---
_pipeline_cache: dict[str, Any] = {"ts": 0.0, "payload": None}
_pipeline_lock = threading.Lock()

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=_REPO_ROOT,
        )
    except Exception:
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    sha = result.stdout.strip()
    return sha or "unknown"


@router.get("/api/health")
def health(conn: sqlite3.Connection = Depends(db_dep)):
    rows = conn.execute(
        "SELECT core_version, COUNT(*) as cnt FROM events WHERE core_version IS NOT NULL GROUP BY core_version"
    ).fetchall()
    core_version_counts = {r["core_version"]: r["cnt"] for r in rows}
    loop_rows = conn.execute(
        "SELECT DISTINCT COALESCE(loop_id, '(unknown)') AS loop_id FROM events ORDER BY loop_id"
    ).fetchall()
    loop_ids = [r["loop_id"] for r in loop_rows]
    return {
        "status": "ok",
        "monitor_version": MONITOR_VERSION,
        "git_sha": _git_sha(),
        "supported_bounty_api": f"{SUPPORTED_API_MAJOR}.x",
        "core_version_counts": core_version_counts,
        "loop_ids": loop_ids,
    }


@router.get("/api/loops")
def get_loops(conn: sqlite3.Connection = Depends(db_dep)):
    rows = conn.execute("""
        SELECT COALESCE(loop_id, '(unknown)') AS loop_id,
               MAX(created_at) AS last_seen,
               COUNT(*) AS event_count,
               GROUP_CONCAT(DISTINCT core_version) AS core_versions
        FROM events
        GROUP BY COALESCE(loop_id, '(unknown)')
        ORDER BY 1
    """).fetchall()
    result = []
    for r in rows:
        entry = dict(r)
        raw = entry.get("core_versions") or ""
        entry["core_versions"] = sorted(set(v for v in raw.split(",") if v)) if raw else []
        result.append(entry)
    return result


def _subsystem_status(last_tick_iso: str | None, interval_seconds: int | None) -> str:
    if last_tick_iso is None or interval_seconds is None or interval_seconds <= 0:
        return "down"
    try:
        last = datetime.fromisoformat(last_tick_iso.replace("Z", "+00:00"))
        age = time.time() - last.timestamp()
    except (ValueError, TypeError):
        return "down"
    if age > 4 * interval_seconds:
        return "down"
    if age > 2 * interval_seconds:
        return "stale"
    return "ok"


def _probe_loop_subsystems() -> dict[str, Any]:
    down: dict[str, Any] = {"status": "down", "last_tick_iso": None, "interval_seconds": None, "detail": ""}
    try:
        result = subprocess.run(
            ["loop", "status", "--json"],
            timeout=5,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        msg = "loop binary not found"
        return {
            "scanner": {**down, "detail": msg},
            "orchestrator": {**down, "detail": msg},
        }
    except subprocess.TimeoutExpired:
        msg = "loop status --json timed out"
        return {
            "scanner": {**down, "detail": msg},
            "orchestrator": {**down, "detail": msg},
        }
    except Exception as exc:
        msg = str(exc)[:200]
        return {
            "scanner": {**down, "detail": msg},
            "orchestrator": {**down, "detail": msg},
        }

    if result.returncode != 0:
        msg = (result.stderr or result.stdout or "non-zero exit")[:200]
        return {
            "scanner": {**down, "detail": msg},
            "orchestrator": {**down, "detail": msg},
        }

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        msg = f"invalid JSON from loop status: {exc}"[:200]
        return {
            "scanner": {**down, "detail": msg},
            "orchestrator": {**down, "detail": msg},
        }

    subsystems = {}
    for key in ("scanner", "orchestrator"):
        raw = data.get(key) or {}
        last_tick = raw.get("last_tick_iso") or raw.get("last_tick")
        interval = raw.get("interval_seconds")
        detail = raw.get("detail") or raw.get("status") or ""
        status = _subsystem_status(last_tick, interval)
        subsystems[key] = {
            "status": status,
            "last_tick_iso": last_tick,
            "interval_seconds": interval,
            "detail": detail,
        }
    return subsystems


def _probe_event_queue() -> dict[str, Any]:
    # Use urllib.request (stdlib) to keep requirements.txt clean.
    base_url = os.getenv("EVENT_QUEUE_URL", "http://localhost:8765")
    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=2) as resp:
            if resp.status != 200:
                return {
                    "status": "down",
                    "last_tick_iso": None,
                    "interval_seconds": None,
                    "detail": f"HTTP {resp.status}",
                }
            body = json.loads(resp.read().decode())
    except Exception as exc:
        return {
            "status": "down",
            "last_tick_iso": None,
            "interval_seconds": None,
            "detail": str(exc)[:200],
        }

    last_tick = body.get("last_tick_iso") or body.get("last_tick")
    interval = body.get("interval_seconds")
    queue_depth = body.get("queue_depth") or body.get("pending_count")
    detail_parts = []
    if queue_depth is not None:
        detail_parts.append(f"queue_depth={queue_depth}")
    detail = ", ".join(detail_parts) or "ok"
    status = _subsystem_status(last_tick, interval) if last_tick and interval else "ok"
    return {
        "status": status,
        "last_tick_iso": last_tick,
        "interval_seconds": interval,
        "detail": detail,
    }


def _compute_pipeline_health() -> dict[str, Any]:
    loop_subs = _probe_loop_subsystems()
    eq = _probe_event_queue()
    return {
        "scanner": loop_subs["scanner"],
        "orchestrator": loop_subs["orchestrator"],
        "event_queue": eq,
    }


@router.get("/api/health/pipeline")
def pipeline_health() -> dict[str, Any]:
    with _pipeline_lock:
        if time.monotonic() - _pipeline_cache["ts"] < 30 and _pipeline_cache["payload"] is not None:
            return _pipeline_cache["payload"]
        payload = _compute_pipeline_health()
        _pipeline_cache["ts"] = time.monotonic()
        _pipeline_cache["payload"] = payload
        return payload

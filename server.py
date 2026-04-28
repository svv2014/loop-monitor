import logging
import sqlite3
import json
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional, Any

from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, model_validator

logger = logging.getLogger(__name__)

DB_PATH = "bounty.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            role TEXT NOT NULL,
            model TEXT,
            event_type TEXT NOT NULL,
            issue_number INTEGER,
            pr_number INTEGER,
            detail TEXT,
            payload TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS verdicts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            role TEXT NOT NULL,
            model TEXT,
            points INTEGER NOT NULL DEFAULT 0,
            reason TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            role TEXT NOT NULL,
            model TEXT,
            total_points INTEGER NOT NULL DEFAULT 0,
            verdict_count INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS issue_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            issue_number INTEGER NOT NULL,
            pr_number INTEGER,
            role TEXT NOT NULL,
            event_type TEXT NOT NULL,
            agent TEXT,
            model TEXT,
            duration_seconds INTEGER,
            rework_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            issue_number INTEGER NOT NULL,
            pr_number INTEGER,
            title TEXT,
            outcome TEXT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            total_duration_seconds INTEGER,
            rework_count INTEGER DEFAULT 0,
            total_bounty INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # Migrate existing events table if new columns are missing
    cols = {row[1] for row in conn.execute("PRAGMA table_info(events)")}
    for col, defn in [
        ("issue_number", "INTEGER"),
        ("pr_number", "INTEGER"),
        ("detail", "TEXT"),
        ("core_version", "TEXT"),
        ("loop_id", "TEXT"),
    ]:
        if col not in cols:
            conn.execute(f"ALTER TABLE events ADD COLUMN {col} {defn}")

    # Migrate pipeline_runs table if new columns are missing
    pr_cols = {row[1] for row in conn.execute("PRAGMA table_info(pipeline_runs)")}
    for col, defn in [
        ("issue_lifetime_seconds", "INTEGER"),
        ("pr_lifetime_seconds", "INTEGER"),
    ]:
        if col not in pr_cols:
            conn.execute(f"ALTER TABLE pipeline_runs ADD COLUMN {col} {defn}")

    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_events_project_role ON events (project, role);
        CREATE INDEX IF NOT EXISTS idx_events_event_type ON events (event_type);
        CREATE INDEX IF NOT EXISTS idx_events_created_at ON events (created_at);
        CREATE INDEX IF NOT EXISTS idx_events_issue_number ON events (project, issue_number) WHERE issue_number IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_events_pr_number ON events (project, pr_number) WHERE pr_number IS NOT NULL;
    """)

    conn.commit()
    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Loop Monitor", lifespan=lifespan)


class ReportPayload(BaseModel):
    """Bounty event payload — accepts both legacy and v1.0 (loop) field names.

    Legacy (asdlc-era):  event_type, issue_number, pr_number, project, role
    v1.0 (loop core):    event,      issue_num,    pr_num,    api, core_version, timestamp

    Server normalizes to legacy field names internally. Either schema works.
    """
    # Bounty event API version (v1.0 spec) — optional; absent = legacy
    api: Optional[str] = None
    core_version: Optional[str] = None
    timestamp: Optional[str] = None

    project: Optional[str] = None
    role: Optional[str] = None
    model: Optional[str] = None
    event_type: Optional[str] = None
    event: Optional[str] = None        # alias for event_type (v1.0 schema)
    payload: Optional[Any] = None
    issue_number: Optional[int] = None
    issue_num: Optional[int] = None     # alias for issue_number (v1.0 schema)
    pr_number: Optional[int] = None
    pr_num: Optional[int] = None        # alias for pr_number (v1.0 schema)
    agent: Optional[str] = None
    detail: Optional[str] = None
    duration_seconds: Optional[int] = None
    rework_count: Optional[int] = None
    loop_id: Optional[str] = None

    class Config:
        extra = "ignore"

    @model_validator(mode="after")
    def _backfill_legacy_aliases(self):
        # v1.0 schema uses 'event' / 'issue_num' / 'pr_num'; legacy uses
        # 'event_type' / 'issue_number' / 'pr_number'. Internal code reads
        # legacy names — backfill from v1.0 when only v1.0 names provided.
        if not self.event_type and self.event:
            self.event_type = self.event
        if self.issue_number is None and self.issue_num is not None:
            self.issue_number = self.issue_num
        if self.pr_number is None and self.pr_num is not None:
            self.pr_number = self.pr_num
        if not self.event_type:
            self.event_type = "unknown"
        return self


class VerdictPayload(BaseModel):
    project: str
    role: str
    model: Optional[str] = None
    points: int
    reason: Optional[str] = None


PROJECTS = {
    'ppl':               'svv2014/ppl-study',
    'boba-event':        'svv2014/boba-event',
    'loop':             'svv2014/loop',
    'bounty':            'svv2014/loop-monitor',
    'vrefm-classifier':  'svv2014/vrefm-classifier',
    'pa-scanner':        'svv2014/pa-scanner',
    'ntc':               'svv2014/NanoTraderCopilot',
}

BOUNTY_POINTS = {
    "dev_done":     3,
    "rework_done":  2,
    "review_done":  2,
    "merge_done":   2,
    "po_done":      2,
    "qa_pass":      1,
    "qa_done":      1,
    "dev_failed":  -1,
    "rework_failed": -1,
    "review_failed": -1,
    "po_failed":   -1,
}


def _auto_bounty(conn, data: "ReportPayload", now: str):
    """Auto-insert a verdict when a terminal event is received."""
    pts = BOUNTY_POINTS.get(data.event_type)
    if pts is None:
        return
    reason = f"auto: {data.event_type}"
    if data.issue_number:
        reason += f" issue #{data.issue_number}"
    elif data.pr_number:
        reason += f" PR #{data.pr_number}"
    conn.execute(
        "INSERT INTO verdicts (project, role, model, points, reason, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (data.project, data.role, data.model, pts, reason, now),
    )
    existing = conn.execute(
        "SELECT id, total_points, verdict_count FROM scores WHERE project=? AND role=? AND model IS ?",
        (data.project, data.role, data.model),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE scores SET total_points=?, verdict_count=?, updated_at=? WHERE id=?",
            (existing["total_points"] + pts, existing["verdict_count"] + 1, now, existing["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO scores (project, role, model, total_points, verdict_count, updated_at) VALUES (?, ?, ?, ?, 1, ?)",
            (data.project, data.role, data.model, pts, now),
        )


def _insert_event(data: ReportPayload):
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO events
           (project, role, model, event_type, issue_number, pr_number, detail, payload, core_version, loop_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data.project,
            data.role,
            data.model,
            data.event_type,
            data.issue_number,
            data.pr_number,
            data.detail,
            json.dumps(data.payload) if data.payload else None,
            data.core_version,
            data.loop_id,
            now,
        ),
    )

    if data.issue_number is not None:
        conn.execute(
            """INSERT INTO issue_history
               (project, issue_number, pr_number, role, event_type, agent, model,
                duration_seconds, rework_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.project,
                data.issue_number,
                data.pr_number,
                data.role,
                data.event_type,
                data.agent,
                data.model,
                data.duration_seconds,
                data.rework_count or 0,
                now,
            ),
        )

        existing_run = conn.execute(
            "SELECT id, rework_count FROM pipeline_runs WHERE project=? AND issue_number=?",
            (data.project, data.issue_number),
        ).fetchone()

        if existing_run:
            updates = ["completed_at=?"]
            params: list = [now]
            if data.pr_number is not None:
                updates.append("pr_number=?")
                params.append(data.pr_number)
            if data.rework_count is not None:
                updates.append("rework_count=rework_count+?")
                params.append(data.rework_count)
            params.append(existing_run["id"])
            conn.execute(
                f"UPDATE pipeline_runs SET {', '.join(updates)} WHERE id=?",
                params,
            )
        else:
            conn.execute(
                """INSERT INTO pipeline_runs
                   (project, issue_number, pr_number, started_at, completed_at, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (data.project, data.issue_number, data.pr_number, now, now, now),
            )

    if data.event_type == "finished" and data.issue_number is not None:
        now_dt = datetime.fromisoformat(now)
        run = conn.execute(
            "SELECT id, started_at FROM pipeline_runs WHERE project=? AND issue_number=? ORDER BY id DESC LIMIT 1",
            (data.project, data.issue_number),
        ).fetchone()
        if run:
            try:
                started = datetime.fromisoformat(run["started_at"].replace("Z", "+00:00"))
                issue_secs = int((now_dt - started).total_seconds())
            except Exception:
                issue_secs = None
            first_pr = conn.execute(
                "SELECT created_at FROM issue_history WHERE project=? AND issue_number=? AND pr_number IS NOT NULL ORDER BY id ASC LIMIT 1",
                (data.project, data.issue_number),
            ).fetchone()
            pr_secs = None
            if first_pr:
                try:
                    pr_start = datetime.fromisoformat(first_pr["created_at"].replace("Z", "+00:00"))
                    pr_secs = int((now_dt - pr_start).total_seconds())
                except Exception:
                    pass
            conn.execute(
                """UPDATE pipeline_runs SET outcome=?, completed_at=?, issue_lifetime_seconds=?, pr_lifetime_seconds=?
                   WHERE id=?""",
                (data.detail or "finished", now, issue_secs, pr_secs, run["id"]),
            )

    _auto_bounty(conn, data, now)
    conn.commit()
    conn.close()


def _insert_verdict(data: VerdictPayload):
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO verdicts (project, role, model, points, reason, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (data.project, data.role, data.model, data.points, data.reason, now),
    )
    # Upsert into scores
    existing = conn.execute(
        "SELECT id, total_points, verdict_count FROM scores WHERE project=? AND role=? AND model IS ?",
        (data.project, data.role, data.model),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE scores SET total_points=?, verdict_count=?, updated_at=? WHERE id=?",
            (
                existing["total_points"] + data.points,
                existing["verdict_count"] + 1,
                now,
                existing["id"],
            ),
        )
    else:
        conn.execute(
            "INSERT INTO scores (project, role, model, total_points, verdict_count, updated_at) VALUES (?, ?, ?, ?, 1, ?)",
            (data.project, data.role, data.model, data.points, now),
        )
    conn.commit()
    conn.close()


SUPPORTED_API_MAJOR = "1"
MONITOR_VERSION = (Path(__file__).parent / "VERSION").read_text().strip() if (Path(__file__).parent / "VERSION").exists() else "unknown"


@app.get("/api/health")
def health():
    conn = get_db()
    rows = conn.execute(
        "SELECT core_version, COUNT(*) as cnt FROM events WHERE core_version IS NOT NULL GROUP BY core_version"
    ).fetchall()
    core_version_counts = {r["core_version"]: r["cnt"] for r in rows}
    loop_rows = conn.execute(
        "SELECT DISTINCT COALESCE(loop_id, '(unknown)') AS loop_id FROM events ORDER BY loop_id"
    ).fetchall()
    loop_ids = [r["loop_id"] for r in loop_rows]
    conn.close()
    return {
        "status": "ok",
        "monitor_version": MONITOR_VERSION,
        "supported_bounty_api": f"{SUPPORTED_API_MAJOR}.x",
        "core_version_counts": core_version_counts,
        "loop_ids": loop_ids,
    }


@app.get("/api/loops")
def get_loops():
    conn = get_db()
    rows = conn.execute("""
        SELECT COALESCE(loop_id, '(unknown)') AS loop_id,
               MAX(created_at) AS last_seen,
               COUNT(*) AS event_count,
               GROUP_CONCAT(DISTINCT core_version) AS core_versions
        FROM events
        GROUP BY COALESCE(loop_id, '(unknown)')
        ORDER BY 1
    """).fetchall()
    conn.close()
    result = []
    for r in rows:
        entry = dict(r)
        raw = entry.get("core_versions") or ""
        entry["core_versions"] = sorted(set(v for v in raw.split(",") if v)) if raw else []
        result.append(entry)
    return result


@app.post("/api/report", status_code=202)
async def report(data: ReportPayload, background_tasks: BackgroundTasks):
    if not data.api:
        logger.warning("Received bounty event with no 'api' field — treating as v1.0 legacy")
    # Bounty event API version negotiation: accept 1.x, reject other majors with 426.
    if data.api:
        major = data.api.split(".", 1)[0]
        if major != SUPPORTED_API_MAJOR:
            raise HTTPException(
                status_code=426,
                detail={
                    "error": "version_unsupported",
                    "supported": [f"{SUPPORTED_API_MAJOR}.x"],
                    "received": data.api,
                },
            )
    background_tasks.add_task(_insert_event, data)
    return {"status": "accepted", "monitor_version": MONITOR_VERSION}


@app.post("/api/verdict", status_code=202)
async def verdict(data: VerdictPayload, background_tasks: BackgroundTasks):
    background_tasks.add_task(_insert_verdict, data)
    return {"status": "accepted"}


@app.get("/api/board")
def board():
    conn = get_db()
    rows = conn.execute(
        "SELECT project, role, model, total_points, verdict_count FROM scores ORDER BY total_points DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/history")
def history(limit: int = 50):
    """Completed jobs: *_done/*_pass events paired with their *_start for duration."""
    conn = get_db()
    rows = conn.execute("""
        SELECT
            d.id, d.project, d.role, d.model, d.event_type,
            d.issue_number, d.pr_number, d.detail, d.created_at AS completed_at,
            s.created_at AS started_at,
            CASE
                WHEN s.created_at IS NOT NULL
                THEN CAST((julianday(d.created_at) - julianday(s.created_at)) * 86400 AS INTEGER)
                ELSE NULL
            END AS duration_seconds,
            v.points
        FROM events d
        LEFT JOIN events s ON s.project = d.project
            AND s.role = d.role
            AND s.event_type = REPLACE(d.event_type, '_done', '_start')
            AND s.id = (
                SELECT MAX(s2.id) FROM events s2
                WHERE s2.project = d.project AND s2.role = d.role
                  AND s2.event_type = REPLACE(d.event_type, '_done', '_start')
                  AND s2.id < d.id
            )
        LEFT JOIN verdicts v ON v.project = d.project AND v.role = d.role
            AND v.reason LIKE '%auto: ' || d.event_type || '%'
            AND v.created_at >= d.created_at
            AND v.id = (SELECT MIN(v2.id) FROM verdicts v2 WHERE v2.project=d.project AND v2.role=d.role AND v2.created_at >= d.created_at AND v2.reason LIKE '%auto: ' || d.event_type || '%')
        WHERE d.event_type LIKE '%_done' OR d.event_type LIKE '%_pass' OR d.event_type LIKE '%_failed'
        ORDER BY d.id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/active")
def active():
    """Currently running workers: latest event per project+role is a *_start within last 4h."""
    conn = get_db()
    rows = conn.execute("""
        SELECT e.project, e.role, e.model, e.event_type, e.issue_number, e.pr_number,
               e.detail, e.created_at
        FROM events e
        INNER JOIN (
            SELECT project, role, MAX(id) AS max_id FROM events GROUP BY project, role
        ) latest ON e.id = latest.max_id
        WHERE e.event_type LIKE '%_start'
          AND e.created_at >= datetime('now', '-4 hours')
        ORDER BY e.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/feed")
def feed():
    conn = get_db()
    rows = conn.execute(
        """SELECT id, project, role, model, event_type, issue_number, pr_number,
                  detail, payload, created_at
           FROM events ORDER BY id DESC LIMIT 50"""
    ).fetchall()
    conn.close()
    now = datetime.now(timezone.utc)
    result = []
    for r in rows:
        entry = dict(r)
        if entry["payload"]:
            entry["payload"] = json.loads(entry["payload"])
        try:
            created = datetime.fromisoformat(entry["created_at"].replace(" ", "T"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            entry["age_seconds"] = int((now - created).total_seconds())
        except Exception:
            entry["age_seconds"] = None
        result.append(entry)
    return result


@app.get("/api/status")
def status():
    conn = get_db()
    rows = conn.execute("""
        SELECT e.project, e.role, e.model, e.event_type, e.issue_number, e.pr_number,
               e.detail, e.payload, e.created_at
        FROM events e
        INNER JOIN (
            SELECT project, role, MAX(id) AS max_id FROM events GROUP BY project, role
        ) latest ON e.id = latest.max_id
        ORDER BY e.project, e.role
    """).fetchall()
    conn.close()
    result = []
    for r in rows:
        entry = dict(r)
        if entry["payload"]:
            entry["payload"] = json.loads(entry["payload"])
        result.append(entry)
    return result


@app.get("/api/verdicts")
def get_verdicts():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, project, role, model, points, reason, created_at FROM verdicts ORDER BY id DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/history/{project}/{issue}")
def get_history(project: str, issue: int):
    conn = get_db()
    rows = conn.execute(
        """SELECT id, project, issue_number, pr_number, role, event_type, agent, model,
                  duration_seconds, rework_count, created_at
           FROM issue_history
           WHERE project=? AND issue_number=?
           ORDER BY id ASC""",
        (project, issue),
    ).fetchall()
    run_row = conn.execute(
        """SELECT outcome, issue_lifetime_seconds, pr_lifetime_seconds, completed_at
           FROM pipeline_runs WHERE project=? AND issue_number=? ORDER BY id DESC LIMIT 1""",
        (project, issue),
    ).fetchone()
    conn.close()
    return {"events": [dict(r) for r in rows], "run": dict(run_row) if run_row else None}


@app.get("/api/runs")
def get_runs():
    conn = get_db()
    rows = conn.execute(
        """SELECT id, project, issue_number, pr_number, title, outcome,
                  started_at, completed_at, total_duration_seconds,
                  rework_count, total_bounty, created_at
           FROM pipeline_runs
           ORDER BY id DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/runs/{project}")
def get_runs_by_project(project: str):
    conn = get_db()
    rows = conn.execute(
        """SELECT id, project, issue_number, pr_number, title, outcome,
                  started_at, completed_at, total_duration_seconds,
                  rework_count, total_bounty, created_at
           FROM pipeline_runs
           WHERE project=?
           ORDER BY id DESC""",
        (project,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/stats")
def get_stats():
    conn = get_db()
    row = conn.execute(
        """SELECT
               COUNT(*) AS total_runs,
               AVG(total_duration_seconds) AS avg_duration_seconds,
               ROUND(100.0 * SUM(CASE WHEN outcome = 'clean' THEN 1 ELSE 0 END) / MAX(COUNT(*), 1), 2) AS success_rate,
               ROUND(100.0 * SUM(CASE WHEN rework_count > 0 THEN 1 ELSE 0 END) / MAX(COUNT(*), 1), 2) AS rework_rate
           FROM pipeline_runs"""
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


@app.get("/api/stats/timeline/pr/{project}/{pr_number}")
def get_timeline_by_pr(project: str, pr_number: int):
    """Look up issue_number from pipeline_runs then return the same timeline payload."""
    from fastapi import HTTPException

    conn = get_db()
    run_row = conn.execute(
        "SELECT issue_number FROM pipeline_runs WHERE project=? AND pr_number=? ORDER BY id DESC LIMIT 1",
        (project, pr_number),
    ).fetchone()

    if run_row is None:
        rows = conn.execute(
            "SELECT * FROM events WHERE project=? AND pr_number=? ORDER BY created_at",
            (project, pr_number),
        ).fetchall()
        conn.close()
        if not rows:
            raise HTTPException(status_code=404, detail="PR not found")
        return {
            "pr_number": pr_number,
            "project": project,
            "issue_number": None,
            "summary": {},
            "events": [dict(r) for r in rows],
        }

    conn.close()
    return get_timeline(project, run_row["issue_number"])


@app.get("/api/stats/timeline/{project}/{issue}")
def get_timeline(project: str, issue: int):
    """Stage-by-stage timeline for a single issue."""
    conn = get_db()

    summary_row = conn.execute(
        """SELECT title, outcome, total_duration_seconds, rework_count, pr_number,
                  issue_lifetime_seconds, pr_lifetime_seconds
           FROM pipeline_runs
           WHERE project=? AND issue_number=?
           ORDER BY id DESC LIMIT 1""",
        (project, issue),
    ).fetchone()

    # Collect all related PR numbers (issue_history may link PRs)
    pr_numbers = [r[0] for r in conn.execute(
        "SELECT DISTINCT pr_number FROM issue_history WHERE project=? AND issue_number=? AND pr_number IS NOT NULL",
        (project, issue),
    ).fetchall()]
    if summary_row and summary_row["pr_number"]:
        pr_numbers.append(summary_row["pr_number"])
    pr_numbers = list(set(pr_numbers))

    # Build timeline from events table — covers both issue-scoped and PR-scoped events
    if pr_numbers:
        placeholders = ",".join("?" * len(pr_numbers))
        params = [project, issue] + pr_numbers
        history_rows = conn.execute(
            f"""SELECT role, event_type, created_at FROM events
               WHERE project=?
                 AND (issue_number=? OR pr_number IN ({placeholders}))
               ORDER BY created_at ASC""",
            params,
        ).fetchall()
    else:
        history_rows = conn.execute(
            """SELECT role, event_type, created_at FROM events
               WHERE project=? AND issue_number=?
               ORDER BY created_at ASC""",
            (project, issue),
        ).fetchall()

    conn.close()

    events = _build_timeline_events(history_rows)

    # Compute total elapsed seconds from first to last event in the set
    total_elapsed_seconds = None
    ts_candidates = []
    for e in events:
        ts_candidates.append(_parse_ts(e.get("started_at")))
        ts_candidates.append(_parse_ts(e.get("completed_at")))
    ts_valid = [t for t in ts_candidates if t is not None]
    if len(ts_valid) >= 2:
        total_elapsed_seconds = int((max(ts_valid) - min(ts_valid)).total_seconds())

    summary: dict = {}
    if summary_row:
        summary = dict(summary_row)

    return {
        "issue_number": issue,
        "project": project,
        "repo": PROJECTS.get(project, project),
        "summary": summary,
        "total_elapsed_seconds": total_elapsed_seconds,
        "events": events,
    }


_TS_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S",
)


def _parse_ts(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    normalized = s.replace("+00:00", "+0000")
    for fmt in _TS_FORMATS:
        try:
            dt = datetime.strptime(normalized, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def _build_timeline_events(history_rows) -> list:
    """Pair *_start and *_done/*_failed rows into stage entries."""
    # key: (role, prefix) -> start row
    pending: dict = {}
    result = []
    first_event_ts: Optional[datetime] = None

    for row in history_rows:
        role = row["role"]
        event_type = row["event_type"]
        created_at = row["created_at"]

        if first_event_ts is None:
            first_event_ts = _parse_ts(created_at)

        if event_type.endswith("_start"):
            prefix = event_type[: -len("_start")]
            pending[(role, prefix)] = created_at
        elif event_type.endswith("_done") or event_type.endswith("_failed"):
            if event_type.endswith("_done"):
                prefix = event_type[: -len("_done")]
                status = "done"
            else:
                prefix = event_type[: -len("_failed")]
                status = "failed"
            started_at = pending.pop((role, prefix), None)
            duration_seconds = None
            t_end = _parse_ts(created_at)
            if started_at and t_end:
                t_start = _parse_ts(started_at)
                if t_start:
                    duration_seconds = int((t_end - t_start).total_seconds())
            cumulative_seconds = None
            if first_event_ts and t_end:
                cumulative_seconds = int((t_end - first_event_ts).total_seconds())
            result.append({
                "role": role,
                "event_type": f"{prefix}_{status}",
                "status": status,
                "started_at": started_at,
                "completed_at": created_at,
                "duration_seconds": duration_seconds,
                "cumulative_seconds": cumulative_seconds,
            })

    # Any still-pending starts are running
    for (role, prefix), started_at in pending.items():
        t_start = _parse_ts(started_at)
        cumulative_seconds = None
        if first_event_ts and t_start:
            cumulative_seconds = int((t_start - first_event_ts).total_seconds())
        result.append({
            "role": role,
            "event_type": f"{prefix}_start",
            "status": "running",
            "started_at": started_at,
            "completed_at": None,
            "duration_seconds": None,
            "cumulative_seconds": cumulative_seconds,
        })

    # Sort by started_at
    result.sort(key=lambda e: e["started_at"] or "")
    return result


@app.get("/api/stats/stages")
def get_stats_stages():
    """Avg duration per pipeline stage by pairing *_start and *_done events."""
    conn = get_db()
    rows = conn.execute("""
        SELECT
            REPLACE(d.event_type, '_done', '') AS stage,
            ROUND(AVG(
                (julianday(d.created_at) - julianday(s.created_at)) * 86400
            ), 2) AS avg_seconds,
            COUNT(*) AS count
        FROM events d
        JOIN events s ON s.project = d.project
            AND s.role = d.role
            AND s.event_type = REPLACE(d.event_type, '_done', '_start')
            AND s.id = (
                SELECT MAX(s2.id) FROM events s2
                WHERE s2.project = d.project AND s2.role = d.role
                  AND s2.event_type = REPLACE(d.event_type, '_done', '_start')
                  AND s2.id < d.id
            )
        WHERE d.event_type LIKE '%_done'
        GROUP BY stage
        ORDER BY stage
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/stats/activity")
def get_stats_activity():
    """Daily event counts per project for the last 14 days."""
    conn = get_db()
    rows = conn.execute("""
        SELECT DATE(created_at) as date, project, COUNT(*) as n
        FROM events
        WHERE created_at >= datetime('now', '-14 days')
        GROUP BY DATE(created_at), project
        ORDER BY date
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/stats/rework")
def get_stats_rework():
    """Per-project rework_start and review_done counts for rework rate cards."""
    conn = get_db()
    rows = conn.execute("""
        SELECT
            project,
            SUM(CASE WHEN event_type = 'rework_start' THEN 1 ELSE 0 END) AS rework_starts,
            SUM(CASE WHEN event_type = 'review_done'  THEN 1 ELSE 0 END) AS review_dones
        FROM events
        GROUP BY project
        ORDER BY project
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/projects")
def get_projects():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT project FROM events").fetchall()
    conn.close()
    active = {r["project"] for r in rows}
    return [{"project": p, "repo": r} for p, r in PROJECTS.items() if p in active]


def _percentile_stats(values: list) -> dict:
    """Return median, P90, sample_size, most_recent for a sorted list of values."""
    n = len(values)
    if n == 0:
        return None
    sorted_vals = sorted(values)
    median = sorted_vals[int(0.5 * n)]
    p90 = sorted_vals[int(0.9 * n)]
    return {
        "median_seconds": median,
        "p90_seconds": p90,
        "sample_size": n,
        "most_recent_seconds": values[-1],
    }


@app.get("/api/projects/{slug}/cycle_times")
def get_cycle_times(slug: str):
    null_response = {"total_duration": None, "issue_lifetime": None, "pr_lifetime": None}
    conn = get_db()
    rows = conn.execute(
        """SELECT total_duration_seconds, issue_lifetime_seconds, pr_lifetime_seconds
           FROM pipeline_runs
           WHERE project=? AND total_duration_seconds IS NOT NULL
           ORDER BY id ASC""",
        (slug,),
    ).fetchall()
    conn.close()

    if not rows:
        return null_response

    total_vals = [r["total_duration_seconds"] for r in rows]
    issue_vals = [r["issue_lifetime_seconds"] for r in rows if r["issue_lifetime_seconds"] is not None]
    pr_vals = [r["pr_lifetime_seconds"] for r in rows if r["pr_lifetime_seconds"] is not None]

    return {
        "total_duration": _percentile_stats(total_vals),
        "issue_lifetime": _percentile_stats(issue_vals) if issue_vals else None,
        "pr_lifetime": _percentile_stats(pr_vals) if pr_vals else None,
    }


app.mount("/", StaticFiles(directory="static", html=True), name="static")

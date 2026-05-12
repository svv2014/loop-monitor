import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends

from server.db import db_dep

router = APIRouter()


@router.get("/api/stats")
def get_stats(conn: sqlite3.Connection = Depends(db_dep)):
    row = conn.execute(
        """SELECT
               COUNT(*) AS total_runs,
               AVG(total_duration_seconds) AS avg_duration_seconds,
               ROUND(100.0 * SUM(CASE WHEN outcome = 'clean' THEN 1 ELSE 0 END) / MAX(COUNT(*), 1), 2) AS success_rate,
               ROUND(100.0 * SUM(CASE WHEN rework_count > 0 THEN 1 ELSE 0 END) / MAX(COUNT(*), 1), 2) AS rework_rate
           FROM pipeline_runs"""
    ).fetchone()
    return dict(row) if row else {}


@router.get("/api/stats/stages")
def get_stats_stages(conn: sqlite3.Connection = Depends(db_dep)):
    """Avg duration per pipeline stage by pairing *_start and *_done events."""
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
    return [dict(r) for r in rows]


@router.get("/api/stats/activity")
def get_stats_activity(conn: sqlite3.Connection = Depends(db_dep)):
    """Daily event counts per project for the last 14 days."""
    rows = conn.execute("""
        SELECT DATE(created_at) as date, project, COUNT(*) as n
        FROM events
        WHERE created_at >= datetime('now', '-14 days')
        GROUP BY DATE(created_at), project
        ORDER BY date
    """).fetchall()
    return [dict(r) for r in rows]


@router.get("/api/stats/rework")
def get_stats_rework(conn: sqlite3.Connection = Depends(db_dep)):
    """Per-project rework_start and review_done counts for rework rate cards."""
    rows = conn.execute("""
        SELECT
            project,
            SUM(CASE WHEN event_type = 'rework_start' THEN 1 ELSE 0 END) AS rework_starts,
            SUM(CASE WHEN event_type = 'review_done'  THEN 1 ELSE 0 END) AS review_dones
        FROM events
        GROUP BY project
        ORDER BY project
    """).fetchall()
    return [dict(r) for r in rows]


@router.get("/api/projects")
def get_projects(conn: sqlite3.Connection = Depends(db_dep)):
    from server.constants import PROJECTS
    rows = conn.execute("SELECT DISTINCT project FROM events").fetchall()
    active = {r["project"] for r in rows}
    return [{"project": p, "repo": r} for p, r in PROJECTS.items() if p in active]


_TS_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
)

_MIN_STAGE_SAMPLES = 5


def _parse_ts_unix(ts_str: Optional[str]) -> Optional[float]:
    if not ts_str:
        return None
    normalized = str(ts_str).replace("+0000", "+00:00").replace(" ", "T")
    for fmt in _TS_FORMATS:
        try:
            dt = datetime.strptime(normalized, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            continue
    return None


def _load_label_transitions(conn: sqlite3.Connection, slug: str) -> dict[int, list]:
    """Load label_transition events grouped by issue_number."""
    rows = conn.execute(
        """SELECT issue_number, payload, created_at
           FROM events
           WHERE project = ? AND event_type = 'label_transition' AND issue_number IS NOT NULL
           ORDER BY issue_number, created_at ASC""",
        (slug,),
    ).fetchall()

    by_issue: dict[int, list] = {}
    for row in rows:
        inum = row["issue_number"]
        if inum not in by_issue:
            by_issue[inum] = []
        try:
            payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else (row["payload"] or {})
        except (json.JSONDecodeError, TypeError):
            payload = {}
        by_issue[inum].append({"payload": payload, "created_at": row["created_at"]})

    return by_issue


def _compute_stage_durations(by_issue: dict) -> dict[str, list[float]]:
    """Bucket consecutive label_transition event durations by (from_label, to_label)."""
    buckets: dict[str, list[float]] = {}

    for _issue_num, events in by_issue.items():
        prev_ts: Optional[float] = None

        for ev in events:
            payload = ev["payload"]
            ts = _parse_ts_unix(ev["created_at"])

            before = set(payload.get("before_labels") or [])
            after = set(payload.get("after_labels") or [])
            removed = before - after
            added = after - before

            if prev_ts is not None and removed and added and ts is not None:
                duration = ts - prev_ts
                if duration >= 0:
                    for fl in removed:
                        for tl in added:
                            key = f"{fl}->{tl}"
                            buckets.setdefault(key, []).append(duration)

            prev_ts = ts

    return buckets


def _detect_rework_for_run(events: list) -> bool:
    """Return True if this run has a backward label transition (label reappears after removal)."""
    removed_labels: set[str] = set()
    for ev in events:
        payload = ev["payload"]
        before = set(payload.get("before_labels") or [])
        after = set(payload.get("after_labels") or [])
        if removed_labels & after:
            return True
        removed_labels |= before - after
    return False


def _stage_percentile_stats(values: list) -> Optional[dict]:
    n = len(values)
    if n < _MIN_STAGE_SAMPLES:
        return None
    sv = sorted(values)
    return {
        "p50_seconds": sv[int(0.5 * n)],
        "p90_seconds": sv[int(0.9 * n)],
        "sample_size": n,
    }


def _percentile_stats(values: list) -> Optional[dict]:
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


@router.get("/api/projects/{slug}/cycle_times")
def get_cycle_times(slug: str, conn: sqlite3.Connection = Depends(db_dep)):
    null_response: dict = {
        "total_duration": None, "issue_lifetime": None, "pr_lifetime": None,
        "stages": {}, "rework_rate": None,
    }
    rows = conn.execute(
        """SELECT total_duration_seconds, issue_lifetime_seconds, pr_lifetime_seconds
           FROM pipeline_runs
           WHERE project=? AND total_duration_seconds IS NOT NULL
           ORDER BY id ASC""",
        (slug,),
    ).fetchall()

    by_issue = _load_label_transitions(conn, slug)

    stage_buckets = _compute_stage_durations(by_issue)
    stages: dict = {}
    for key, durations in stage_buckets.items():
        stats = _stage_percentile_stats(durations)
        if stats is not None:
            stages[key] = stats

    rework_rate: Optional[float] = None
    if by_issue:
        reworked = sum(1 for evs in by_issue.values() if _detect_rework_for_run(evs))
        rework_rate = round(reworked / len(by_issue), 4)

    if not rows:
        return {**null_response, "stages": stages, "rework_rate": rework_rate}

    total_vals = [r["total_duration_seconds"] for r in rows]
    issue_vals = [r["issue_lifetime_seconds"] for r in rows if r["issue_lifetime_seconds"] is not None]
    pr_vals = [r["pr_lifetime_seconds"] for r in rows if r["pr_lifetime_seconds"] is not None]

    return {
        "total_duration": _percentile_stats(total_vals),
        "issue_lifetime": _percentile_stats(issue_vals) if issue_vals else None,
        "pr_lifetime": _percentile_stats(pr_vals) if pr_vals else None,
        "stages": stages,
        "rework_rate": rework_rate,
    }

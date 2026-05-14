import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query

from server.db import db_dep
from server.routes.stats import _compute_stage_durations, _parse_ts_unix

router = APIRouter()

# The 7 stage transitions defined in the analytics epic (#235).
_STAGE_TRANSITIONS = [
    "needs-po->in-po",
    "in-po->needs-dev",
    "in-dev->needs-review",
    "needs-review->in-review",
    "in-review->needs-qa",
    "needs-qa->qa-pass",
    "qa-pass->done",
]


def _since_iso(days: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _load_transitions_since(conn: sqlite3.Connection, since_iso: str) -> dict:
    """Load all label_transition events across all projects since the given ISO timestamp."""
    rows = conn.execute(
        """SELECT project, issue_number, payload, created_at
           FROM events
           WHERE event_type = 'label_transition' AND issue_number IS NOT NULL
             AND created_at >= ?
           ORDER BY project, issue_number, created_at ASC""",
        (since_iso,),
    ).fetchall()

    by_issue: dict = {}
    for row in rows:
        key = (row["project"], row["issue_number"])
        if key not in by_issue:
            by_issue[key] = []
        try:
            payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else (row["payload"] or {})
        except (json.JSONDecodeError, TypeError):
            payload = {}
        by_issue[key].append({"payload": payload, "created_at": row["created_at"]})

    return by_issue


def _pct_stats(values: list[float]) -> Optional[dict]:
    """Compute p50/p75/p95/count.
    Uses floor-based index — known small-sample underestimate; see issue #129."""
    n = len(values)
    if n == 0:
        return None
    sv = sorted(values)
    return {
        "p50": sv[int(0.50 * n)],
        "p75": sv[int(0.75 * n)],
        "p95": sv[int(0.95 * n)],
        "count": n,
    }


def _compute_lead_times(by_issue: dict) -> list[float]:
    """Compute full lead-time (needs-po added → done added) per issue."""
    lead_times = []
    for events in by_issue.values():
        po_ts: Optional[float] = None
        done_ts: Optional[float] = None
        for ev in events:
            payload = ev["payload"]
            ts = _parse_ts_unix(ev["created_at"])
            after = set(payload.get("after_labels") or [])
            before = set(payload.get("before_labels") or [])
            added = after - before
            if "needs-po" in added and po_ts is None:
                po_ts = ts
            if "done" in added:
                done_ts = ts
        if po_ts is not None and done_ts is not None and done_ts > po_ts:
            lead_times.append(done_ts - po_ts)
    return lead_times


@router.get("/api/analytics/cycle_time")
def get_analytics_cycle_time(
    days: int = Query(30, ge=1, le=365),
    conn: sqlite3.Connection = Depends(db_dep),
) -> dict:
    since = _since_iso(days)
    by_issue = _load_transitions_since(conn, since)

    # _compute_stage_durations only iterates .values() so tuple keys are fine.
    all_buckets = _compute_stage_durations(by_issue)

    stages = []
    for transition in _STAGE_TRANSITIONS:
        durations = all_buckets.get(transition, [])
        stats = _pct_stats(durations)
        if stats is not None:
            stages.append({"stage": transition, **stats})

    lead_times = _compute_lead_times(by_issue)
    lead_time = _pct_stats(lead_times)

    return {"stages": stages, "lead_time": lead_time}

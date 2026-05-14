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


@router.get("/api/analytics/quality")
def get_analytics_quality(
    days: int = Query(30, ge=1, le=365),
    conn: sqlite3.Connection = Depends(db_dep),
) -> dict:
    since = _since_iso(days)

    # --- Failure type counts ---
    fail_rows = conn.execute(
        """SELECT event_type, COUNT(*) AS cnt
           FROM events
           WHERE event_type IN ('po_failed','dev_failed','qa_failed','review_failed','merge_failed')
             AND created_at >= ?
           GROUP BY event_type""",
        (since,),
    ).fetchall()
    failure_counts = {r["event_type"]: r["cnt"] for r in fail_rows}
    failure_types = {
        "po_failed":     failure_counts.get("po_failed", 0),
        "dev_failed":    failure_counts.get("dev_failed", 0),
        "qa_fail":       failure_counts.get("qa_failed", 0),
        "review_failed": failure_counts.get("review_failed", 0),
        "merge_failed":  failure_counts.get("merge_failed", 0),
    }

    # --- Stage failure rate ---
    _STAGES = ["po", "dev", "review", "qa", "merge"]
    stage_agg = conn.execute(
        """SELECT
               SUM(CASE WHEN event_type = 'po_start'      THEN 1 ELSE 0 END) AS po_start,
               SUM(CASE WHEN event_type = 'po_failed'     THEN 1 ELSE 0 END) AS po_failed,
               SUM(CASE WHEN event_type = 'dev_start'     THEN 1 ELSE 0 END) AS dev_start,
               SUM(CASE WHEN event_type = 'dev_failed'    THEN 1 ELSE 0 END) AS dev_failed,
               SUM(CASE WHEN event_type = 'review_start'  THEN 1 ELSE 0 END) AS review_start,
               SUM(CASE WHEN event_type = 'review_failed' THEN 1 ELSE 0 END) AS review_failed,
               SUM(CASE WHEN event_type = 'qa_start'      THEN 1 ELSE 0 END) AS qa_start,
               SUM(CASE WHEN event_type = 'qa_failed'     THEN 1 ELSE 0 END) AS qa_failed,
               SUM(CASE WHEN event_type = 'merge_start'   THEN 1 ELSE 0 END) AS merge_start,
               SUM(CASE WHEN event_type = 'merge_failed'  THEN 1 ELSE 0 END) AS merge_failed
           FROM events
           WHERE created_at >= ?""",
        (since,),
    ).fetchone()

    stage_failure = []
    for stage in _STAGES:
        starts = stage_agg[f"{stage}_start"] or 0
        fails = stage_agg[f"{stage}_failed"] or 0
        if starts > 0:
            stage_failure.append({
                "stage": stage,
                "fail_rate": round(fails / starts, 4),
                "sample": starts,
            })

    # --- QA pass rate overall ---
    qa_pass_cnt = conn.execute(
        "SELECT COUNT(*) FROM events WHERE event_type IN ('qa_pass','qa_done') AND created_at >= ?",
        (since,),
    ).fetchone()[0] or 0
    qa_fail_cnt = failure_counts.get("qa_failed", 0)
    qa_total = qa_pass_cnt + qa_fail_cnt
    qa_pass_rate: Optional[float] = round(qa_pass_cnt / qa_total, 4) if qa_total > 0 else None

    # --- QA pass rate daily ---
    today_dt = datetime.now(timezone.utc).date()
    all_days = [(today_dt - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]

    daily_rows = conn.execute(
        """SELECT date(created_at) AS day,
                  SUM(CASE WHEN event_type IN ('qa_pass','qa_done') THEN 1 ELSE 0 END) AS passes,
                  SUM(CASE WHEN event_type = 'qa_failed' THEN 1 ELSE 0 END) AS fails
           FROM events
           WHERE event_type IN ('qa_pass','qa_done','qa_failed') AND created_at >= ?
           GROUP BY day""",
        (since,),
    ).fetchall()
    daily_qa: dict[str, tuple[int, int]] = {r["day"]: (r["passes"] or 0, r["fails"] or 0) for r in daily_rows}

    qa_pass_rate_daily = []
    for d in all_days:
        passes, fails = daily_qa.get(d, (0, 0))
        total = passes + fails
        rate: Optional[float] = round(passes / total, 4) if total > 0 else None
        qa_pass_rate_daily.append({"date": d, "rate": rate})

    # --- Rework factor distribution (per issue, simplified formula: actual_runs/5) ---
    rf_rows = conn.execute(
        """SELECT project, issue_number,
                  SUM(CASE WHEN event_type LIKE '%_start' THEN 1 ELSE 0 END) AS actual_runs
           FROM events
           WHERE issue_number IS NOT NULL AND created_at >= ?
           GROUP BY project, issue_number
           HAVING actual_runs > 0""",
        (since,),
    ).fetchall()

    rework_factors = [round((r["actual_runs"] or 0) / 5, 4) for r in rf_rows]

    # Verdict mix bucketed by rework factor
    verdicts: dict[str, int] = {"clean": 0, "light_rework": 0, "heavy_rework": 0, "blocked": 0}
    for rf in rework_factors:
        if rf <= 1.0:
            verdicts["clean"] += 1
        elif rf <= 2.0:
            verdicts["light_rework"] += 1
        elif rf <= 4.0:
            verdicts["heavy_rework"] += 1
        else:
            verdicts["blocked"] += 1

    rf_pct = _pct_stats(rework_factors)
    buckets = [
        {"label": "<=1x", "count": verdicts["clean"]},
        {"label": "1-2x", "count": verdicts["light_rework"]},
        {"label": "2-4x", "count": verdicts["heavy_rework"]},
        {"label": ">4x",  "count": verdicts["blocked"]},
    ]
    rework_dist: dict = {
        "p50": rf_pct["p50"] if rf_pct else None,
        "p75": rf_pct["p75"] if rf_pct else None,
        "p95": rf_pct["p95"] if rf_pct else None,
        "buckets": buckets,
    }

    return {
        "verdicts": verdicts,
        "qa_pass_rate": qa_pass_rate,
        "qa_pass_rate_daily": qa_pass_rate_daily,
        "stage_failure": stage_failure,
        "rework_dist": rework_dist,
        "failure_types": failure_types,
    }


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

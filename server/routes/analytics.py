import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from server.db import db_dep

router = APIRouter()

_STAGES = ["po", "dev", "review", "qa", "merge"]
_HAPPY_PATH = 5  # happy-path run count assuming no child issues
_BUCKET_LABELS = ["≤1", "1–1.5", "1.5–2", "2–3", "3–4", ">4"]


def _empty_buckets() -> list[dict]:
    return [{"label": lbl, "count": 0} for lbl in _BUCKET_LABELS]


def _compute_rework_dist(sorted_factors: list[float]) -> dict:
    n = len(sorted_factors)
    if n == 0:
        return {"p50": 0.0, "p75": 0.0, "p95": 0.0, "buckets": _empty_buckets()}

    def pct(p: float) -> float:
        return sorted_factors[int(p * (n - 1))]

    buckets = _empty_buckets()
    for v in sorted_factors:
        if v <= 1.0:
            buckets[0]["count"] += 1
        elif v <= 1.5:
            buckets[1]["count"] += 1
        elif v <= 2.0:
            buckets[2]["count"] += 1
        elif v <= 3.0:
            buckets[3]["count"] += 1
        elif v <= 4.0:
            buckets[4]["count"] += 1
        else:
            buckets[5]["count"] += 1

    return {"p50": pct(0.50), "p75": pct(0.75), "p95": pct(0.95), "buckets": buckets}


@router.get("/api/analytics/quality")
def get_quality(
    days: int = 30,
    conn: sqlite3.Connection = Depends(db_dep),
) -> dict:
    since_dt = datetime.now(timezone.utc) - timedelta(days=days)
    since_iso = since_dt.isoformat()

    # Verdict mix from verdicts table (categorise by points)
    verdict_rows = conn.execute(
        "SELECT points FROM verdicts WHERE created_at >= ?",
        (since_iso,),
    ).fetchall()
    verdicts: dict[str, int] = {"clean": 0, "light_rework": 0, "heavy_rework": 0, "blocked": 0}
    for row in verdict_rows:
        pts = row["points"] or 0
        if pts <= 0:
            verdicts["blocked"] += 1
        elif pts < 4:
            verdicts["heavy_rework"] += 1
        elif pts < 8:
            verdicts["light_rework"] += 1
        else:
            verdicts["clean"] += 1

    # QA pass rate overall
    qa_agg = conn.execute(
        """
        SELECT
            SUM(CASE WHEN event_type = 'qa_start'                     THEN 1 ELSE 0 END) AS qa_starts,
            SUM(CASE WHEN event_type IN ('qa_failed', 'qa_fail')      THEN 1 ELSE 0 END) AS qa_fails
        FROM events
        WHERE created_at >= ?
        """,
        (since_iso,),
    ).fetchone()
    qa_starts = qa_agg["qa_starts"] or 0
    qa_fails = qa_agg["qa_fails"] or 0
    qa_pass_rate = round(1.0 - qa_fails / qa_starts, 4) if qa_starts > 0 else 0.0

    # QA pass rate per day
    daily_rows = conn.execute(
        """
        SELECT
            DATE(created_at) AS day,
            SUM(CASE WHEN event_type = 'qa_start'                THEN 1 ELSE 0 END) AS s,
            SUM(CASE WHEN event_type IN ('qa_failed', 'qa_fail') THEN 1 ELSE 0 END) AS f
        FROM events
        WHERE created_at >= ?
          AND event_type IN ('qa_start', 'qa_failed', 'qa_fail')
        GROUP BY day
        ORDER BY day
        """,
        (since_iso,),
    ).fetchall()
    qa_pass_rate_daily = [
        {"date": r["day"], "rate": round(1.0 - (r["f"] or 0) / r["s"], 4) if (r["s"] or 0) > 0 else 0.0}
        for r in daily_rows
    ]

    # Per-stage failure rate
    stage_failure = []
    for stage in _STAGES:
        row = conn.execute(
            """
            SELECT
                SUM(CASE WHEN event_type = ? THEN 1 ELSE 0 END) AS starts,
                SUM(CASE WHEN event_type = ? THEN 1 ELSE 0 END) AS fails
            FROM events
            WHERE created_at >= ?
            """,
            (f"{stage}_start", f"{stage}_failed", since_iso),
        ).fetchone()
        starts = row["starts"] or 0
        fails = row["fails"] or 0
        stage_failure.append({
            "stage": stage,
            "fail_rate": round(fails / starts, 4) if starts > 0 else 0.0,
            "sample": starts,
        })

    # Rework-factor distribution (happy_path=5, no GH call needed for aggregate)
    rf_rows = conn.execute(
        """
        WITH agg AS (
            SELECT
                project,
                issue_number,
                SUM(CASE WHEN event_type LIKE '%_start' THEN 1 ELSE 0 END) AS actual_runs
            FROM events
            WHERE issue_number IS NOT NULL
              AND created_at >= ?
            GROUP BY project, issue_number
            HAVING actual_runs > 0
        )
        SELECT actual_runs FROM agg ORDER BY actual_runs
        """,
        (since_iso,),
    ).fetchall()
    sorted_factors = sorted(round(r["actual_runs"] / _HAPPY_PATH, 2) for r in rf_rows)
    rework_dist = _compute_rework_dist(sorted_factors)

    # Failure type counts
    ft = conn.execute(
        """
        SELECT
            SUM(CASE WHEN event_type = 'po_failed'                    THEN 1 ELSE 0 END) AS po_failed,
            SUM(CASE WHEN event_type = 'dev_failed'                   THEN 1 ELSE 0 END) AS dev_failed,
            SUM(CASE WHEN event_type IN ('qa_failed', 'qa_fail')      THEN 1 ELSE 0 END) AS qa_fail,
            SUM(CASE WHEN event_type = 'review_failed'                THEN 1 ELSE 0 END) AS review_failed,
            SUM(CASE WHEN event_type = 'merge_failed'                 THEN 1 ELSE 0 END) AS merge_failed
        FROM events
        WHERE created_at >= ?
        """,
        (since_iso,),
    ).fetchone()
    failure_types = {
        "po_failed":     ft["po_failed"] or 0,
        "dev_failed":    ft["dev_failed"] or 0,
        "qa_fail":       ft["qa_fail"] or 0,
        "review_failed": ft["review_failed"] or 0,
        "merge_failed":  ft["merge_failed"] or 0,
    }

    return {
        "verdicts": verdicts,
        "qa_pass_rate": qa_pass_rate,
        "qa_pass_rate_daily": qa_pass_rate_daily,
        "stage_failure": stage_failure,
        "rework_dist": rework_dist,
        "failure_types": failure_types,
    }

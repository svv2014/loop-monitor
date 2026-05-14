import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from server.db import db_dep

router = APIRouter()


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _date_range(start: date, days: int) -> list[date]:
    """Return a list of `days` dates starting at `start` (inclusive)."""
    return [start + timedelta(days=i) for i in range(days)]


@router.get("/api/analytics/velocity")
def get_velocity(
    days: Optional[str] = Query(default="30", description="Window in days (1–365)"),
    project: Optional[str] = Query(default=None, description="Filter by project slug"),
    conn: sqlite3.Connection = Depends(db_dep),
):
    """Merge velocity metrics from pipeline_runs.

    A run is counted as 'merged' when outcome = 'clean'.  This matches the
    success_rate calculation in /api/stats which uses the same column/value.
    Alternative: outcome = 'merged' if the pipeline writes that value — but
    current ingest uses 'clean' for successfully merged issues.
    """
    # Validate and parse days: must be an integer string, else 400.
    try:
        days_int = int(days)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="days must be an integer")

    # Clamp to [1, 365]
    days_int = max(1, min(365, days_int))

    today = _utc_today()
    window_start = today - timedelta(days=days_int - 1)  # inclusive

    # ── daily counts within the requested window ──────────────────────────────
    proj_filter = "AND project = ?" if project else ""
    params_window: list = [str(window_start)]
    if project:
        params_window.append(project)

    daily_rows = conn.execute(
        f"""
        SELECT DATE(completed_at) AS day, COUNT(*) AS cnt
        FROM pipeline_runs
        WHERE outcome = 'clean'
          AND DATE(completed_at) >= ?
          {proj_filter}
        GROUP BY DATE(completed_at)
        ORDER BY DATE(completed_at)
        """,
        params_window,
    ).fetchall()

    # Build a zero-filled dict for every date in the window
    daily_map: dict[str, int] = {str(window_start + timedelta(days=i)): 0 for i in range(days_int)}
    for row in daily_rows:
        if row["day"] in daily_map:
            daily_map[row["day"]] = row["cnt"]

    daily_list = [{"date": d, "count": daily_map[d]} for d in sorted(daily_map)]

    # ── scalar aggregates ──────────────────────────────────────────────────────
    today_str = str(today)
    today_count = daily_map.get(today_str, 0)

    total_merged = sum(daily_map.values())
    avg_per_day = round(total_merged / days_int, 2)

    # Trend: compare last 7 days vs previous 7 days
    last7_start = today - timedelta(days=6)
    prev7_start = today - timedelta(days=13)
    prev7_end   = today - timedelta(days=7)

    last7 = sum(
        cnt for d, cnt in daily_map.items()
        if str(last7_start) <= d <= today_str
    )
    prev7 = sum(
        cnt for d, cnt in daily_map.items()
        if str(prev7_start) <= d <= str(prev7_end)
    )

    last7_avg = last7 / 7
    prev7_avg = prev7 / 7

    if prev7_avg == 0.0:
        trend_pct = 0.0
    else:
        trend_pct = round(((last7_avg - prev7_avg) / prev7_avg) * 100, 1)

    prev_period_avg = round(prev7_avg, 2)

    # ── per-project breakdown ─────────────────────────────────────────────────
    per_project: list[dict] = []
    if not project:
        proj_rows = conn.execute(
            """
            SELECT
                project AS slug,
                SUM(CASE WHEN DATE(completed_at) = ? THEN 1 ELSE 0 END) AS today_cnt,
                COUNT(*) AS total_cnt
            FROM pipeline_runs
            WHERE outcome = 'clean'
              AND DATE(completed_at) >= ?
            GROUP BY project
            ORDER BY total_cnt DESC
            """,
            [today_str, str(window_start)],
        ).fetchall()

        for r in proj_rows:
            per_project.append({
                "slug": r["slug"],
                "today": r["today_cnt"],
                "avg_per_day": round(r["total_cnt"] / days_int, 2),
            })

    return {
        "today": today_count,
        "avg_per_day": avg_per_day,
        "prev_period_avg": prev_period_avg,
        "trend_pct": trend_pct,
        "daily": daily_list,
        "per_project": per_project,
    }

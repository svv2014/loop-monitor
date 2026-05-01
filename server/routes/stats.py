from typing import Optional

from fastapi import APIRouter

from server.db import get_db

router = APIRouter()


@router.get("/api/stats")
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


@router.get("/api/stats/stages")
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


@router.get("/api/stats/activity")
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


@router.get("/api/stats/rework")
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


@router.get("/api/projects")
def get_projects():
    from server.constants import PROJECTS
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT project FROM events").fetchall()
    conn.close()
    active = {r["project"] for r in rows}
    return [{"project": p, "repo": r} for p, r in PROJECTS.items() if p in active]


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

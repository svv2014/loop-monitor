import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from server.constants import PROJECTS
from server.db import db_dep
from server.helpers.event_mapping import remap_legacy_judge_event
from server.helpers.timeline import build_timeline_events, parse_ts

router = APIRouter()


def _get_timeline_data(conn: sqlite3.Connection, project: str, issue: int) -> dict:
    """Shared implementation for timeline queries."""
    summary_row = conn.execute(
        """SELECT title, outcome, total_duration_seconds, rework_count, pr_number,
                  issue_lifetime_seconds, pr_lifetime_seconds
           FROM pipeline_runs
           WHERE project=? AND issue_number=?
           ORDER BY id DESC LIMIT 1""",
        (project, issue),
    ).fetchone()

    pr_numbers = [r[0] for r in conn.execute(
        "SELECT DISTINCT pr_number FROM issue_history WHERE project=? AND issue_number=? AND pr_number IS NOT NULL",
        (project, issue),
    ).fetchall()]
    if summary_row and summary_row["pr_number"]:
        pr_numbers.append(summary_row["pr_number"])
    pr_numbers = list(set(pr_numbers))

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

    events = build_timeline_events([remap_legacy_judge_event(dict(r)) for r in history_rows])

    total_elapsed_seconds = None
    ts_candidates = []
    for e in events:
        ts_candidates.append(parse_ts(e.get("started_at")))
        ts_candidates.append(parse_ts(e.get("completed_at")))
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


@router.get("/api/stats/timeline/pr/{project}/{pr_number}")
def get_timeline_by_pr(project: str, pr_number: int, conn: sqlite3.Connection = Depends(db_dep)):
    """Look up issue_number from pipeline_runs then return the same timeline payload."""
    run_row = conn.execute(
        "SELECT issue_number FROM pipeline_runs WHERE project=? AND pr_number=? ORDER BY id DESC LIMIT 1",
        (project, pr_number),
    ).fetchone()

    if run_row is None:
        rows = conn.execute(
            "SELECT * FROM events WHERE project=? AND pr_number=? ORDER BY created_at",
            (project, pr_number),
        ).fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="PR not found")
        return {
            "pr_number": pr_number,
            "project": project,
            "issue_number": None,
            "summary": {},
            "events": [remap_legacy_judge_event(dict(r)) for r in rows],
        }

    return _get_timeline_data(conn, project, run_row["issue_number"])


@router.get("/api/stats/timeline/{project}/{issue}")
def get_timeline(project: str, issue: int, conn: sqlite3.Connection = Depends(db_dep)):
    """Stage-by-stage timeline for a single issue."""
    return _get_timeline_data(conn, project, issue)


@router.get("/api/events_graph")
def get_events_graph(window: int = 24, conn: sqlite3.Connection = Depends(db_dep)):
    window = max(1, min(window, 168))
    # Bug fix: GROUP BY must use the CASE expression directly, not the
    # alias `role`. In SQLite `GROUP BY role` resolves to the column, not
    # the SELECT alias — so legacy judge rows (role='dev', event_type='judge')
    # would group with regular dev_done in the same hour. Repeating the
    # CASE keeps the grouping aligned with what we project.
    rows = conn.execute(
        """SELECT
              strftime('%Y-%m-%dT%H:00:00', created_at) AS hour,
              CASE WHEN event_type = 'judge' THEN 'judge' ELSE role END AS role,
              COUNT(*) AS count
           FROM events
           WHERE created_at > datetime('now', ? || ' hours')
           GROUP BY hour, CASE WHEN event_type = 'judge' THEN 'judge' ELSE role END
           ORDER BY hour""",
        (f"-{window}",),
    ).fetchall()
    return {"window_hours": window, "buckets": [dict(r) for r in rows]}

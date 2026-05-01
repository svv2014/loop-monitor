from fastapi import APIRouter

from server.db import get_db

router = APIRouter()


@router.get("/api/history/{project}/{issue}")
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


@router.get("/api/runs")
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


@router.get("/api/runs/{project}")
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

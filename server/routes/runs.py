import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends

from server.constants import PROJECTS
from server.db import db_dep
from server.helpers.timeline import parse_ts

router = APIRouter()


STAGE_MAP = {
    "dev_start": "in-development",
    "dev_done": "dev-complete",
    "dev_failed": "dev-failed",
    "review_start": "in-review",
    "review_done": "review-complete",
    "review_failed": "review-failed",
    "rework_start": "needs-rework",
    "rework_done": "rework-complete",
    "rework_failed": "rework-failed",
    "qa_start": "in-qa",
    "qa_pass": "qa-passed",
    "qa_done": "qa-complete",
    "merge_start": "merging",
    "merge_done": "merged",
    "po_start": "in-po",
    "po_done": "po-approved",
    "po_failed": "po-failed",
    "finished": "finished",
}


def _derive_stage(event_type: Optional[str]) -> Optional[str]:
    if not event_type:
        return None
    return STAGE_MAP.get(event_type, event_type)


@router.get("/api/history/{project}/{issue}")
def get_history(project: str, issue: int, conn: sqlite3.Connection = Depends(db_dep)):
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
    return {"events": [dict(r) for r in rows], "run": dict(run_row) if run_row else None}


@router.get("/api/runs")
def get_runs(conn: sqlite3.Connection = Depends(db_dep)):
    rows = conn.execute(
        """SELECT id, project, issue_number, pr_number, title, outcome,
                  started_at, completed_at, total_duration_seconds,
                  rework_count, total_bounty, created_at
           FROM pipeline_runs
           ORDER BY id DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/api/runs/{project}")
def get_runs_by_project(project: str, conn: sqlite3.Connection = Depends(db_dep)):
    rows = conn.execute(
        """SELECT id, project, issue_number, pr_number, title, outcome,
                  started_at, completed_at, total_duration_seconds,
                  rework_count, total_bounty, created_at
           FROM pipeline_runs
           WHERE project=?
           ORDER BY id DESC""",
        (project,),
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/api/projects/{slug}/prs")
def get_project_prs(slug: str, include_finished: bool = False, conn: sqlite3.Connection = Depends(db_dep)):
    """PR monitor: every PR seen by the pipeline with current stage and time-in-stage."""
    finished_clause = "" if include_finished else " AND pr.outcome IS NULL"
    rows = conn.execute(
        f"""SELECT pr.issue_number, pr.pr_number, pr.title, pr.outcome, pr.rework_count,
                   e.event_type, e.created_at AS event_created_at, e.payload
            FROM pipeline_runs pr
            LEFT JOIN events e ON e.id = (
                SELECT MAX(id) FROM events
                WHERE project = pr.project
                  AND (issue_number = pr.issue_number OR pr_number = pr.pr_number)
            )
            WHERE pr.project = ? AND pr.pr_number IS NOT NULL{finished_clause}
            ORDER BY pr.id DESC""",
        (slug,),
    ).fetchall()

    repo = PROJECTS.get(slug)
    now = datetime.now(timezone.utc)
    result = []
    for row in rows:
        stage = None
        last_event_type = None
        last_event_at = None
        time_in_stage = None
        branch = None
        is_draft = None
        if row["event_type"] is not None:
            last_event_type = row["event_type"]
            last_event_at = row["event_created_at"]
            stage = _derive_stage(last_event_type)
            ts = parse_ts(last_event_at)
            if ts is not None:
                time_in_stage = int((now - ts).total_seconds())
            if row["payload"]:
                try:
                    p = json.loads(row["payload"])
                    if isinstance(p, dict):
                        branch = p.get("branch")
                        if "draft" in p:
                            is_draft = bool(p.get("draft"))
                except Exception:
                    pass

        github_url = f"https://github.com/{repo}/pull/{row['pr_number']}" if repo else None

        result.append({
            "pr_number": row["pr_number"],
            "title": row["title"],
            "branch": branch,
            "stage": stage,
            "time_in_stage_seconds": time_in_stage,
            "retry_count": row["rework_count"] or 0,
            "last_event": last_event_type,
            "last_event_at": last_event_at,
            "github_url": github_url,
            "is_finished": row["outcome"] is not None,
            "is_draft": is_draft,
        })

    return result

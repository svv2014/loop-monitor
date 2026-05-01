import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter

from server.constants import PROJECTS
from server.db import get_db
from server.helpers.timeline import parse_ts

router = APIRouter()

STUCK_STAGES = {"blocked", "needs-clarification"}
TIMEOUT_STAGES = {"in-progress", "in-review", "in-rework"}
QA_FAIL_STAGE = "qa-fail"
QA_FAIL_RETRY_THRESHOLD = 3


def _handler_timeout_seconds() -> int:
    try:
        return int(os.environ.get("HANDLER_TIMEOUT", "3600"))
    except ValueError:
        return 3600


def _action_queue_reason(
    stage: str, age_seconds: int, retry_count: int, threshold: int
) -> Optional[str]:
    if stage in STUCK_STAGES:
        return "stuck_label"
    if stage in TIMEOUT_STAGES and age_seconds > threshold:
        return "timeout"
    if stage == QA_FAIL_STAGE and retry_count >= QA_FAIL_RETRY_THRESHOLD:
        return "qa_fail_repeated"
    return None


@router.get("/api/action_queue")
def action_queue():
    """Items across all projects awaiting human input.

    Derived from the latest event per (project, kind, number). No GitHub API call.
    """
    threshold = _handler_timeout_seconds() * 2
    conn = get_db()
    rows = conn.execute(
        """
        SELECT e.project, e.role, e.event_type, e.issue_number, e.pr_number,
               e.detail, e.loop_id, e.created_at,
               COALESCE(h.rework_count, 0) AS rework_count,
               COALESCE(r.title, '') AS title
        FROM events e
        INNER JOIN (
            SELECT project,
                   COALESCE(issue_number, -1) AS i,
                   COALESCE(pr_number, -1) AS p,
                   MAX(id) AS max_id
            FROM events
            WHERE issue_number IS NOT NULL OR pr_number IS NOT NULL
            GROUP BY project, COALESCE(issue_number, -1), COALESCE(pr_number, -1)
        ) latest
            ON e.id = latest.max_id
        LEFT JOIN issue_history h ON h.id = (
            SELECT MAX(h2.id) FROM issue_history h2
            WHERE h2.project = e.project
              AND (h2.issue_number = e.issue_number OR h2.pr_number = e.pr_number)
        )
        LEFT JOIN pipeline_runs r ON r.id = (
            SELECT MAX(r2.id) FROM pipeline_runs r2
            WHERE r2.project = e.project
              AND (r2.issue_number = e.issue_number OR r2.pr_number = e.pr_number)
        )
        """
    ).fetchall()
    conn.close()

    now = datetime.now(timezone.utc)
    result = []
    for r in rows:
        stage = (r["event_type"] or "").lower()
        created = parse_ts(r["created_at"])
        age_seconds = int((now - created).total_seconds()) if created else 0
        reason = _action_queue_reason(stage, age_seconds, r["rework_count"] or 0, threshold)
        if reason is None:
            continue
        if r["issue_number"] is not None:
            kind = "issue"
            number = r["issue_number"]
        elif r["pr_number"] is not None:
            kind = "pr"
            number = r["pr_number"]
        else:
            continue
        repo = PROJECTS.get(r["project"])
        github_url = (
            f"https://github.com/{repo}/{'issues' if kind == 'issue' else 'pull'}/{number}"
            if repo else None
        )
        result.append({
            "project": r["project"],
            "kind": kind,
            "number": number,
            "title": r["title"] or r["detail"] or "",
            "stage": stage,
            "age_seconds": age_seconds,
            "reason": reason,
            "loop_id": r["loop_id"],
            "github_url": github_url,
        })
    result.sort(key=lambda x: x["age_seconds"], reverse=True)
    return result

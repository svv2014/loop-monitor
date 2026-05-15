import json
import logging
import os
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from server.constants import PROJECTS
from server.db import db_dep
from server.helpers.github import fetch_failure_context
from server.helpers.timeline import parse_ts

logger = logging.getLogger(__name__)

# Per-project open-set cache: repo -> ({"issue": set|None, "pr": set|None}, expires_at)
_OPEN_SET_CACHE: dict[str, tuple[dict[str, Optional[set[int]]], float]] = {}
_OPEN_SET_TTL = 60  # seconds

router = APIRouter()

STUCK_STAGES = {"blocked", "needs-clarification", "loop:result:blocked"}
TIMEOUT_STAGES = {
    "in-dev", "in-review", "in-qa",
    "loop:active:dev", "loop:active:review", "loop:active:qa",
    "needs-review", "needs-qa", "needs-dev",
    "loop:action:review", "loop:action:qa", "loop:action:dev",
}
QA_FAIL_STAGES = {"qa-fail", "loop:result:qa-fail"}
QA_FAIL_RETRY_THRESHOLD = 3

_ALL_STAGES = STUCK_STAGES | TIMEOUT_STAGES | QA_FAIL_STAGES

STAGE_THRESHOLD_ENV = {
    "in-dev":             "HANDLER_TIMEOUT_DEV",
    "loop:active:dev":    "HANDLER_TIMEOUT_DEV",
    "loop:action:dev":    "HANDLER_TIMEOUT_DEV",
    "needs-dev":          "HANDLER_TIMEOUT_DEV",
    "in-review":          "HANDLER_TIMEOUT_REVIEW",
    "needs-review":       "HANDLER_TIMEOUT_REVIEW",
    "loop:active:review": "HANDLER_TIMEOUT_REVIEW",
    "loop:action:review": "HANDLER_TIMEOUT_REVIEW",
    "in-qa":              "HANDLER_TIMEOUT_QA",
    "needs-qa":           "HANDLER_TIMEOUT_QA",
    "loop:active:qa":     "HANDLER_TIMEOUT_QA",
    "loop:action:qa":     "HANDLER_TIMEOUT_QA",
}

STAGE_DEFAULTS = {
    "in-dev":             7200,
    "loop:active:dev":    7200,
    "loop:action:dev":    7200,
    "needs-dev":          7200,
    "in-review":          1800,
    "needs-review":       1800,
    "loop:active:review": 1800,
    "loop:action:review": 1800,
    "in-qa":              3600,
    "needs-qa":           3600,
    "loop:active:qa":     3600,
    "loop:action:qa":     3600,
}

_EVENT_TO_STAGE: dict[str, Optional[str]] = {
    "dev_start":      "in-dev",
    "rework_start":   "in-dev",
    "review_start":   "in-review",
    "qa_start":       "in-qa",
    "qa_fail":        "qa-fail",
    "po_done":        "needs-dev",
    "dev_done":       "needs-review",
    "rework_done":    "needs-review",
    "review_done":    "needs-qa",
    "qa_pass":        None,
    "merge_done":     None,
    "po_failed":      "blocked",
    "dev_failed":     "blocked",
    "review_failed":  "blocked",
    "merge_failed":   "blocked",
    "merge_conflict": "blocked",
    "rework_failed":  "blocked",
}


def _infer_stage(role: str, event_type: str, payload: Optional[str] = None) -> Optional[str]:
    """Map the latest event per ticket to a canonical stage label.

    Temporary stop-gap; superseded once the `current_labels` table lands (see Option 1 in #221).

    Returns None for events that imply no action needed (e.g. dev_done — work finished).
    """
    et = (event_type or "").lower()

    if et in _EVENT_TO_STAGE:
        return _EVENT_TO_STAGE[et]

    if et == "label_transition":
        # Parse the after_labels from payload to find the resulting stage.
        # Payload schema defined in server/models.py (loop#344 namespace migration).
        if payload:
            try:
                data = json.loads(payload)
                op = data.get("op", "")
                if op in ("add", "swap"):
                    for label in data.get("after_labels", []):
                        if label in _ALL_STAGES:
                            return label
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass
        return None

    # Passthrough: if event_type is already a known stage name, use it directly.
    # Handles legacy data that predates the inference table.
    if et in _ALL_STAGES:
        return et

    return None


def _handler_timeout_seconds() -> int:
    try:
        return int(os.environ.get("HANDLER_TIMEOUT", "3600"))
    except ValueError:
        return 3600


def _threshold_for_stage(stage: str) -> int:
    env_key = STAGE_THRESHOLD_ENV.get(stage)
    fallback = STAGE_DEFAULTS.get(stage, _handler_timeout_seconds() * 2)
    if env_key:
        try:
            return int(os.environ.get(env_key, fallback))
        except ValueError:
            return fallback
    return fallback


def _action_queue_reason(
    stage: str, age_seconds: int, retry_count: int, threshold: int
) -> Optional[str]:
    if stage in STUCK_STAGES:
        return "stuck_label"
    if stage in TIMEOUT_STAGES and age_seconds > threshold:
        return "timeout"
    if stage in QA_FAIL_STAGES and retry_count >= QA_FAIL_RETRY_THRESHOLD:
        return "qa_fail_repeated"
    return None


def _fetch_open_numbers(repo: str, kind: str) -> Optional[set[int]]:
    """Call gh to list open issues or PRs for a repo.

    Returns None when the gh call fails (caller should include items conservatively).
    Returns a set (possibly empty) when gh succeeds.
    """
    entity = "issue" if kind == "issue" else "pr"
    try:
        result = subprocess.run(
            [
                "gh", entity, "list",
                "--repo", repo,
                "--state", "open",
                "--limit", "1000",
                "--json", "number",
                "--jq", "[.[].number]",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    try:
        return set(json.loads(result.stdout))
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def _get_open_set(repo: str) -> dict[str, Optional[set[int]]]:
    """Return cached open issue/PR numbers for a repo, refreshing after TTL.

    Values are None when the corresponding gh call failed — callers treat None
    as "unknown" and include the item conservatively.
    """
    now = time.monotonic()
    cached = _OPEN_SET_CACHE.get(repo)
    if cached and now < cached[1]:
        return cached[0]
    open_set: dict[str, Optional[set[int]]] = {
        "issue": _fetch_open_numbers(repo, "issue"),
        "pr": _fetch_open_numbers(repo, "pr"),
    }
    _OPEN_SET_CACHE[repo] = (open_set, now + _OPEN_SET_TTL)
    return open_set


@router.get("/api/action_queue")
def action_queue(conn: sqlite3.Connection = Depends(db_dep)):
    """Items across all projects awaiting human input.

    Derived from the latest event per (project, kind, number), then filtered
    to only items currently open on GitHub (cached 60 s per project).
    """
    rows = conn.execute(
        """
        SELECT e.project, e.role, e.event_type, e.issue_number, e.pr_number,
               e.detail, e.loop_id, e.payload, e.created_at,
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

    now = datetime.now(timezone.utc)
    result = []
    for r in rows:
        stage = _infer_stage(r["role"], r["event_type"], r["payload"])
        if stage is None:
            continue
        created = parse_ts(r["created_at"])
        age_seconds = int((now - created).total_seconds()) if created else 0
        threshold = _threshold_for_stage(stage)
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
            "threshold_seconds": threshold if reason == "timeout" else None,
            "loop_id": r["loop_id"],
            "github_url": github_url,
        })
    # Filter to only currently-open items on GitHub.
    # Group candidates by project, fetch open-sets once per project per minute.
    # When gh call fails (open_numbers is None), include conservatively.
    before_count = len(result)
    filtered: list[dict] = []
    for item in result:
        repo = PROJECTS.get(item["project"])
        if repo is None:
            # No repo mapping — cannot verify state, include conservatively.
            filtered.append(item)
            continue
        open_set = _get_open_set(repo)
        open_numbers = open_set.get(item["kind"])
        if open_numbers is None or item["number"] in open_numbers:
            filtered.append(item)
    after_count = len(filtered)
    if before_count != after_count:
        logger.info(
            "action_queue: filtered %d closed/merged items out of %d candidates (%d open remain)",
            before_count - after_count,
            before_count,
            after_count,
        )
    filtered.sort(key=lambda x: x["age_seconds"], reverse=True)
    return filtered


@router.get("/api/action_queue/{project}/{kind}/{number}/failure")
def action_queue_failure(project: str, kind: str, number: int):
    """Most-recent failure-context comment for a ticket.

    Returns 200 with excerpt=null when no failure comment exists.
    Returns 400 for invalid kind values.
    """
    if kind not in ("issue", "pr"):
        raise HTTPException(status_code=400, detail="kind must be 'issue' or 'pr'")
    repo = PROJECTS.get(project)
    if repo is None:
        return {
            "excerpt": None,
            "model": None,
            "run_id": None,
            "retry_count": 0,
            "timestamp": None,
            "github_comment_url": None,
            "log_path": None,
        }
    cache_key = (project, kind, number)
    return fetch_failure_context(repo=repo, kind=kind, number=number, project=project, cache_key=cache_key)

import json
import re
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends

from server.constants import PROJECTS
from server.db import db_dep

router = APIRouter()

# (project, issue_number) -> (expiry_timestamp, meta_dict)
_gh_cache: dict[tuple[str, int], tuple[float, dict]] = {}
_GH_TTL = 60

_PRIORITY_LABELS = {"p0-critical", "p1-high", "p2-medium", "p3-low"}
_ROLES = ["po", "dev", "review", "qa", "merge"]
_CHILD_RE = re.compile(r"(?:closes|depends\s+on)\s+#(\d+)", re.IGNORECASE)


def _fetch_gh_meta(project: str, issue_number: int) -> dict:
    key = (project, issue_number)
    now = datetime.now(timezone.utc).timestamp()
    if key in _gh_cache:
        expiry, data = _gh_cache[key]
        if now < expiry:
            return data

    default: dict = {"title": "", "state": "unknown", "priority": None, "body": "", "merged": False}
    repo = PROJECTS.get(project)
    if not repo:
        _gh_cache[key] = (now + _GH_TTL, default)
        return default
    try:
        result = subprocess.run(
            [
                "gh", "api",
                f"repos/{repo}/issues/{issue_number}",
                "--jq",
                "{title, state, body, labels: [.labels[].name], pull_request}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            _gh_cache[key] = (now + _GH_TTL, default)
            return default
        raw = json.loads(result.stdout)
        labels: list[str] = raw.get("labels") or []
        priority: Optional[str] = next((lbl for lbl in labels if lbl in _PRIORITY_LABELS), None)
        pr_field = raw.get("pull_request") or {}
        merged = bool(pr_field.get("merged_at"))
        meta: dict = {
            "title": raw.get("title") or "",
            "state": raw.get("state") or "unknown",
            "priority": priority,
            "body": raw.get("body") or "",
            "merged": merged,
        }
        _gh_cache[key] = (now + _GH_TTL, meta)
        return meta
    except Exception:
        _gh_cache[key] = (now + _GH_TTL, default)
        return default


def _parse_children(body: str) -> int:
    return len(set(_CHILD_RE.findall(body)))


def _build_row(raw: dict, meta: dict, now_ts: float) -> dict:
    actual_runs: int = raw.get("actual_runs") or 0
    child_count = _parse_children(meta.get("body") or "")
    happy_path_runs = 5 + (5 * child_count)
    rework_factor = 0.0 if actual_runs == 0 else round(actual_runs / happy_path_runs, 2)

    state: str = meta.get("state") or "unknown"
    merged: bool = meta.get("merged") or False
    stranded_seconds: Optional[int] = None
    if state == "open" and not merged:
        last_event: Optional[str] = raw.get("last_event")
        if last_event:
            try:
                last_dt = datetime.fromisoformat(last_event.replace(" ", "T"))
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                stranded_seconds = int(now_ts - last_dt.timestamp())
            except Exception:
                pass

    stage_runs: dict = {}
    for role in _ROLES:
        stage_runs[role] = raw.get(f"{role}_runs") or 0
        stage_runs[f"{role}_failed"] = raw.get(f"{role}_failed") or 0

    project = raw["project"]
    repo = PROJECTS.get(project)
    github_url = (
        f"https://github.com/{repo}/issues/{raw['issue_number']}"
        if repo else None
    )

    return {
        "project": project,
        "issue_number": raw["issue_number"],
        "title": meta.get("title") or "",
        "priority": meta.get("priority"),
        "state": state,
        "first_event": raw.get("first_event"),
        "last_event": raw.get("last_event"),
        "stage_runs": stage_runs,
        "happy_path_runs": happy_path_runs,
        "actual_runs": actual_runs,
        "rework_factor": rework_factor,
        "total_points": raw.get("total_points") or 0,
        "verdict_count": raw.get("verdict_count") or 0,
        "stranded_seconds": stranded_seconds,
        "github_url": github_url,
    }


@router.get("/api/issues/cost")
def get_issues_cost(
    project: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    conn: sqlite3.Connection = Depends(db_dep),
) -> list:
    if since is None:
        since_dt = datetime.now(timezone.utc) - timedelta(days=30)
        since_iso = since_dt.isoformat()
    else:
        since_iso = since

    project_param: Optional[str] = project

    rows = conn.execute(
        """
        WITH agg AS (
            SELECT
                project,
                issue_number,
                MIN(created_at)                                                    AS first_event,
                MAX(created_at)                                                    AS last_event,
                SUM(CASE WHEN event_type LIKE '%_start'   THEN 1 ELSE 0 END)      AS actual_runs,
                SUM(CASE WHEN event_type = 'po_start'     THEN 1 ELSE 0 END)      AS po_runs,
                SUM(CASE WHEN event_type = 'po_failed'    THEN 1 ELSE 0 END)      AS po_failed,
                SUM(CASE WHEN event_type = 'dev_start'    THEN 1 ELSE 0 END)      AS dev_runs,
                SUM(CASE WHEN event_type = 'dev_failed'   THEN 1 ELSE 0 END)      AS dev_failed,
                SUM(CASE WHEN event_type = 'review_start' THEN 1 ELSE 0 END)      AS review_runs,
                SUM(CASE WHEN event_type = 'review_failed' THEN 1 ELSE 0 END)     AS review_failed,
                SUM(CASE WHEN event_type = 'qa_start'     THEN 1 ELSE 0 END)      AS qa_runs,
                SUM(CASE WHEN event_type = 'qa_failed'    THEN 1 ELSE 0 END)      AS qa_failed,
                SUM(CASE WHEN event_type = 'merge_start'  THEN 1 ELSE 0 END)      AS merge_runs,
                SUM(CASE WHEN event_type = 'merge_failed' THEN 1 ELSE 0 END)      AS merge_failed
            FROM events
            WHERE issue_number IS NOT NULL
              AND created_at >= ?
              AND (? IS NULL OR project = ?)
            GROUP BY project, issue_number
            HAVING actual_runs > 0
            ORDER BY actual_runs DESC
            LIMIT ? OFFSET ?
        )
        SELECT
            a.*,
            (
                SELECT COUNT(*)
                FROM verdicts v
                WHERE v.project = a.project
                  AND v.created_at BETWEEN a.first_event AND a.last_event
            ) AS verdict_count,
            (
                SELECT COALESCE(SUM(v.points), 0)
                FROM verdicts v
                WHERE v.project = a.project
                  AND v.created_at BETWEEN a.first_event AND a.last_event
            ) AS total_points
        FROM agg a
        """,
        (since_iso, project_param, project_param, limit, offset),
    ).fetchall()

    now_ts = datetime.now(timezone.utc).timestamp()
    result = []
    for raw in rows:
        raw_dict = dict(raw)
        project_slug = raw_dict["project"]
        issue_num = raw_dict["issue_number"]
        meta = _fetch_gh_meta(project_slug, issue_num)
        result.append(_build_row(raw_dict, meta, now_ts))

    result.sort(key=lambda r: (-r["rework_factor"], -r["actual_runs"]))
    return result

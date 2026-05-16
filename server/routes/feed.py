import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends

from server.constants import PROJECTS
from server.db import db_dep
from server.helpers.event_mapping import remap_legacy_judge_event

router = APIRouter()


def _github_url(project: str, issue_number: Optional[int], pr_number: Optional[int]) -> Optional[str]:
    repo = PROJECTS.get(project)
    if not repo:
        return None
    if issue_number is not None:
        return f"https://github.com/{repo}/issues/{issue_number}"
    if pr_number is not None:
        return f"https://github.com/{repo}/pull/{pr_number}"
    return None


@router.get("/api/history")
def history(limit: int = 50, loop_id: Optional[str] = None, conn: sqlite3.Connection = Depends(db_dep)):
    """Completed jobs: *_done/*_pass events paired with their *_start for duration."""
    loop_clause = "AND d.loop_id = ?" if loop_id is not None else ""
    params = (loop_id, limit) if loop_id is not None else (limit,)
    rows = conn.execute(f"""
        SELECT
            d.id, d.project, d.role, d.model, d.event_type,
            d.issue_number, d.pr_number, d.detail, d.created_at AS completed_at,
            s.created_at AS started_at,
            CASE
                WHEN s.created_at IS NOT NULL
                THEN CAST((julianday(d.created_at) - julianday(s.created_at)) * 86400 AS INTEGER)
                ELSE NULL
            END AS duration_seconds,
            v.points
        FROM events d
        LEFT JOIN events s ON s.project = d.project
            AND s.role = d.role
            AND s.event_type = REPLACE(d.event_type, '_done', '_start')
            AND s.id = (
                SELECT MAX(s2.id) FROM events s2
                WHERE s2.project = d.project AND s2.role = d.role
                  AND s2.event_type = REPLACE(d.event_type, '_done', '_start')
                  AND s2.id < d.id
            )
        LEFT JOIN verdicts v ON v.project = d.project AND v.role = d.role
            AND v.reason LIKE '%auto: ' || d.event_type || '%'
            AND v.created_at >= d.created_at
            AND v.id = (
                SELECT MIN(v2.id) FROM verdicts v2
                WHERE v2.project=d.project AND v2.role=d.role
                  AND v2.created_at >= d.created_at
                  AND v2.reason LIKE '%auto: ' || d.event_type || '%'
            )
        WHERE (
            d.event_type LIKE '%_done'
            OR d.event_type LIKE '%_pass'
            OR d.event_type LIKE '%_failed'
            OR d.event_type = 'judge'
        )
        {loop_clause}
        ORDER BY d.id DESC
        LIMIT ?
    """, params).fetchall()
    result = []
    for r in rows:
        entry = remap_legacy_judge_event(dict(r))
        entry["github_url"] = _github_url(entry["project"], entry.get("issue_number"), entry.get("pr_number"))
        result.append(entry)
    return result


@router.get("/api/active")
def active(conn: sqlite3.Connection = Depends(db_dep)):
    """Currently running workers: latest event per project+role is a *_start within last 4h."""
    rows = conn.execute("""
        SELECT e.project, e.role, e.model, e.event_type, e.issue_number, e.pr_number,
               e.detail, e.created_at
        FROM events e
        INNER JOIN (
            SELECT project, role, MAX(id) AS max_id FROM events GROUP BY project, role
        ) latest ON e.id = latest.max_id
        WHERE e.event_type LIKE '%_start'
          AND e.created_at >= datetime('now', '-4 hours')
        ORDER BY e.created_at DESC
    """).fetchall()
    return [dict(r) for r in rows]


VALID_FEED_STATUSES = {'done', 'fail', 'pass', 'skip'}


def _derive_status(event_type: str) -> str:
    if not event_type:
        return 'unknown'
    suffix = event_type.rsplit('_', 1)[-1].lower()
    if suffix in ('fail', 'failed'):
        return 'fail'
    if suffix in ('done', 'pass', 'skip', 'start'):
        return suffix
    return 'unknown'


@router.get("/api/feed")
def feed(
    role: Optional[str] = None,
    status: Optional[str] = None,
    loop_id: Optional[str] = None,
    conn: sqlite3.Connection = Depends(db_dep),
):
    status_lower = status.lower() if status else None
    if status_lower is not None and status_lower not in VALID_FEED_STATUSES:
        return []

    where_clauses: list[str] = []
    params: list = []

    if loop_id is not None:
        where_clauses.append("loop_id = ?")
        params.append(loop_id)

    if role:
        if role.lower() == "judge":
            where_clauses.append("(lower(role) = lower(?) OR event_type = 'judge')")
            params.append(role)
        else:
            # Bug fix: exclude legacy-judge rows from non-judge role filters.
            # Legacy rows have role='dev' + event_type='judge' in the DB and get
            # remapped to role='judge' at read time. Without this filter,
            # `role=dev` queries leaked legacy-judge rows that then rendered as
            # 'judge' — confusing for any UI consumer.
            where_clauses.append("lower(role) = lower(?) AND event_type != 'judge'")
            params.append(role)

    if status_lower == 'fail':
        where_clauses.append("(event_type LIKE '%_fail' OR event_type LIKE '%_failed')")
    elif status_lower == 'done':
        where_clauses.append("(event_type LIKE '%_done' OR event_type = 'judge')")
    elif status_lower:
        where_clauses.append(f"event_type LIKE '%_{status_lower}'")

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    rows = conn.execute(
        f"""SELECT id, project, role, model, event_type, issue_number, pr_number,
                  detail, payload, created_at
           FROM events {where_sql} ORDER BY id DESC LIMIT 50""",
        params,
    ).fetchall()
    now = datetime.now(timezone.utc)
    result = []
    for r in rows:
        entry = remap_legacy_judge_event(dict(r))
        if entry["payload"]:
            entry["payload"] = json.loads(entry["payload"])
        try:
            created = datetime.fromisoformat(entry["created_at"].replace(" ", "T"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            entry["age_seconds"] = int((now - created).total_seconds())
        except Exception:
            entry["age_seconds"] = None
        entry["status"] = _derive_status(entry["event_type"])
        entry["github_url"] = _github_url(entry["project"], entry.get("issue_number"), entry.get("pr_number"))
        result.append(entry)
    return result


@router.get("/api/status")
def status(conn: sqlite3.Connection = Depends(db_dep)):
    rows = conn.execute("""
        SELECT e.project, e.role, e.model, e.event_type, e.issue_number, e.pr_number,
               e.detail, e.payload, e.created_at
        FROM events e
        INNER JOIN (
            SELECT project, role, MAX(id) AS max_id FROM events GROUP BY project, role
        ) latest ON e.id = latest.max_id
        ORDER BY e.project, e.role
    """).fetchall()
    result = []
    for r in rows:
        entry = remap_legacy_judge_event(dict(r))
        if entry["payload"]:
            entry["payload"] = json.loads(entry["payload"])
        result.append(entry)
    return result

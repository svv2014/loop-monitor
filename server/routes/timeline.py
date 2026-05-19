import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from server.db import db_dep

router = APIRouter()


def _parse_payload(value: Optional[str]) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _parse_ts(value: str) -> float:
    normalized = value.replace(" ", "T")
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        parsed = datetime.strptime(normalized[:19], "%Y-%m-%dT%H:%M:%S")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _event_role(event: dict) -> str:
    role = event.get("role")
    if role:
        return role
    event_type = event["event_type"]
    if "_" not in event_type:
        return "unknown"
    return event_type.split("_", 1)[0]


def _with_durations(events: list[dict]) -> list[dict]:
    result = []
    for idx, event in enumerate(events):
        item = dict(event)
        item["duration_seconds"] = None
        if item["event_type"].endswith("_start"):
            role = _event_role(item)
            for next_event in events[idx + 1 :]:
                if _event_role(next_event) == role and next_event["event_type"].endswith(("_done", "_pass")):
                    item["duration_seconds"] = max(0, int(_parse_ts(next_event["created_at"]) - _parse_ts(item["created_at"])))
                    break
        result.append(item)
    return result


def _latest_stage(conn: sqlite3.Connection, project: str, kind: str, number: int) -> Optional[str]:
    column = "issue_number" if kind == "issue" else "pr_number"
    rows = conn.execute(
        f"""
        SELECT payload, detail
        FROM events
        WHERE project = ? AND {column} = ? AND event_type = 'label_transition'
        ORDER BY created_at DESC, id DESC
        """,
        (project, number),
    ).fetchall()
    for row in rows:
        payload = _parse_payload(row["payload"])
        labels = payload.get("after_labels")
        if isinstance(labels, list):
            for label in labels:
                if isinstance(label, str) and label.startswith("loop:stage:"):
                    return label
        if row["detail"] and str(row["detail"]).startswith("loop:stage:"):
            return row["detail"]
    return None


def _totals(events: list[dict]) -> dict:
    total_duration = sum(event["duration_seconds"] or 0 for event in events)
    role_starts: dict[str, int] = {}
    total_points = 0
    verdict = None
    for event in events:
        if event["event_type"].endswith("_start"):
            role = _event_role(event)
            role_starts[role] = role_starts.get(role, 0) + 1
        payload = _parse_payload(event.get("payload"))
        points = payload.get("points")
        if isinstance(points, int):
            event["points"] = points
            total_points += points
        else:
            event["points"] = None
        if event["event_type"] in {"judge_done", "qa_pass", "merge_done"}:
            verdict = event.get("detail") or event["event_type"]

    return {
        "total_duration_seconds": total_duration if events else None,
        "total_points": total_points,
        "rework_count": sum(max(0, count - 1) for count in role_starts.values()),
        "verdict": verdict,
    }


def _github_url(project: str, kind: str, number: int) -> str:
    path = "issues" if kind == "issue" else "pull"
    return f"https://github.com/svv2014/{project}/{path}/{number}"


def _legacy_response(events: list[dict]) -> dict:
    legacy_events = []
    for event in events:
        entry = dict(event)
        entry["ts"] = entry["created_at"]
        entry["type"] = entry["event_type"]
        if entry.get("payload"):
            entry["payload"] = _parse_payload(entry["payload"])
        legacy_events.append(entry)
    return {"events": legacy_events}


@router.get("/api/timeline")
def timeline(
    project: Optional[str] = Query(None),
    issue: Optional[int] = Query(None),
    pr: Optional[int] = Query(None),
    slug: Optional[str] = Query(None),
    num: Optional[int] = Query(None),
    include_skips: bool = Query(False),
    conn: sqlite3.Connection = Depends(db_dep),
):
    """Per-ticket event timeline.

    Supports the newer project+issue/pr contract while preserving the older
    slug+num response used by the current v2 screen.
    """
    legacy_mode = project is None and slug is not None and num is not None
    if legacy_mode:
        project = slug
        issue = num

    if project is None:
        raise HTTPException(status_code=400, detail="project is required")
    if (issue is None and pr is None) or (issue is not None and pr is not None):
        raise HTTPException(status_code=400, detail="provide exactly one of issue or pr")

    kind = "issue" if issue is not None else "pr"
    number = issue if issue is not None else pr
    assert number is not None
    ticket_clause = "(issue_number = ? OR pr_number = ?)" if legacy_mode else (
        "issue_number = ?" if kind == "issue" else "pr_number = ?"
    )
    ticket_params = (number, number) if legacy_mode else (number,)
    skip_clause = (
        ""
        if include_skips
        else "AND NOT (event_type = 'reconcile_check' AND json_extract(payload, '$.decision') = 'skip')"
    )

    rows = conn.execute(
        f"""
        SELECT id, project, role, model, event_type, issue_number, pr_number,
               detail, payload, core_version, loop_id, created_at
        FROM events
        WHERE project = ? AND {ticket_clause}
          {skip_clause}
        ORDER BY created_at ASC, id ASC
        """,
        (project, *ticket_params),
    ).fetchall()
    events = _with_durations([dict(row) for row in rows])

    if legacy_mode:
        return _legacy_response(events)

    title = next((event["detail"] for event in reversed(events) if event.get("detail")), None)
    linked_pr = None
    linked_issue = None
    if kind == "issue":
        row = conn.execute(
            """
            SELECT pr_number FROM events
            WHERE project = ? AND issue_number = ? AND pr_number IS NOT NULL
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (project, number),
        ).fetchone()
        linked_pr = row["pr_number"] if row else None
    else:
        row = conn.execute(
            """
            SELECT issue_number FROM events
            WHERE project = ? AND pr_number = ? AND issue_number IS NOT NULL
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (project, number),
        ).fetchone()
        linked_issue = row["issue_number"] if row else None

    totals = _totals(events)
    clean_events = [
        {
            "id": event["id"],
            "role": event["role"],
            "event_type": event["event_type"],
            "model": event["model"],
            "created_at": event["created_at"],
            "duration_seconds": event["duration_seconds"],
            "points": event["points"],
            "detail": event["detail"],
        }
        for event in events
    ]

    return {
        "project": project,
        "kind": kind,
        "number": number,
        "title": title,
        "github_url": _github_url(project, kind, number),
        "stage": _latest_stage(conn, project, kind, number),
        "linked_pr": linked_pr,
        "linked_issue": linked_issue,
        "events": clean_events,
        "totals": totals,
    }

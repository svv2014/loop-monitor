import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from server.db import db_dep

router = APIRouter()

_ROLE_MAP = {
    "po_start": "po", "po_done": "po", "po_failed": "po",
    "dev_start": "dev", "dev_done": "dev", "dev_failed": "dev",
    "review_start": "review", "review_done": "review", "review_failed": "review",
    "qa_start": "qa", "qa_done": "qa", "qa_failed": "qa", "qa_pass": "qa", "qa_fail": "qa",
    "merge_start": "merge", "merge_done": "merge", "merge_failed": "merge",
    "judge_start": "judge", "judge_done": "judge", "judge_failed": "judge",
}


def _pair_durations(events: list[dict]) -> list[dict]:
    """Add duration_seconds by pairing *_start with the next matching *_done for the same role."""
    # Build a mutable list; iterate forwards
    result = []
    for i, ev in enumerate(events):
        ev = dict(ev)
        ev["duration_seconds"] = None
        if ev["event_type"].endswith("_start"):
            role = ev.get("role") or _ROLE_MAP.get(ev["event_type"])
            # Look forward for next *_done for same role
            for j in range(i + 1, len(events)):
                nxt = events[j]
                nxt_role = nxt.get("role") or _ROLE_MAP.get(nxt["event_type"])
                if nxt_role == role and nxt["event_type"].endswith("_done"):
                    try:
                        t0 = _parse_ts(ev["created_at"])
                        t1 = _parse_ts(nxt["created_at"])
                        ev["duration_seconds"] = max(0, int(t1 - t0))
                    except Exception:
                        pass
                    break
        result.append(ev)
    return result


def _parse_ts(s: str) -> float:
    from datetime import datetime, timezone

    s = s.replace(" ", "T")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        dt = datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _compute_totals(events: list[dict], conn: sqlite3.Connection, project: str) -> dict:
    total_dur = None
    for ev in events:
        d = ev.get("duration_seconds")
        if d is not None:
            total_dur = (total_dur or 0) + d

    rework_count = sum(
        1 for ev in events
        if ev["event_type"].endswith("_start")
        and ev["event_type"] not in ("po_start",)
        # count any re-start (more than one start per role) as rework
    )
    # rework = extra starts beyond the first per role
    role_starts: dict[str, int] = {}
    for ev in events:
        if ev["event_type"].endswith("_start"):
            role = ev.get("role") or _ROLE_MAP.get(ev["event_type"], "unknown")
            role_starts[role] = role_starts.get(role, 0) + 1
    rework_count = sum(max(0, v - 1) for v in role_starts.values())

    # Get total points from verdicts — scoped to this project in the time window
    total_points: Optional[int] = None
    if events:
        first_at = min(ev["created_at"] for ev in events)
        last_at = max(ev["created_at"] for ev in events)
        row = conn.execute(
            "SELECT COALESCE(SUM(points), 0) FROM verdicts WHERE project = ? AND created_at BETWEEN ? AND ?",
            (project, first_at, last_at),
        ).fetchone()
        if row:
            total_points = row[0]

    # verdict: last judge_done or dev_done detail
    verdict: Optional[str] = None
    for ev in reversed(events):
        if ev["event_type"] in ("judge_done", "qa_pass", "merge_done"):
            verdict = ev.get("detail") or ev["event_type"]
            break

    return {
        "total_duration_seconds": total_dur,
        "total_points": total_points,
        "rework_count": rework_count,
        "verdict": verdict,
    }


@router.get("/api/timeline")
def get_timeline(
    project: str,
    issue: Optional[int] = None,
    pr: Optional[int] = None,
    conn: sqlite3.Connection = Depends(db_dep),
) -> dict:
    if issue is None and pr is None:
        raise HTTPException(status_code=400, detail="Provide either 'issue' or 'pr' query param")
    if issue is not None and pr is not None:
        raise HTTPException(status_code=400, detail="Provide only one of 'issue' or 'pr', not both")

    kind = "issue" if issue is not None else "pr"
    number = issue if issue is not None else pr

    # Fetch events for this ticket
    if kind == "issue":
        rows = conn.execute(
            """
            SELECT id, role, model, event_type, issue_number, pr_number, detail, created_at
            FROM events
            WHERE project = ? AND issue_number = ?
            ORDER BY created_at ASC, id ASC
            """,
            (project, number),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, role, model, event_type, issue_number, pr_number, detail, created_at
            FROM events
            WHERE project = ? AND pr_number = ?
            ORDER BY created_at ASC, id ASC
            """,
            (project, number),
        ).fetchall()

    events = [dict(r) for r in rows]

    # Pair durations
    events = _pair_durations(events)

    # Derive stage from the most recent label_transition event detail, if any
    stage: Optional[str] = None
    label_rows = conn.execute(
        """
        SELECT detail FROM events
        WHERE project = ? AND event_type = 'label_transition'
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (project,),
    ).fetchone()
    if label_rows and label_rows[0]:
        stage = label_rows[0]

    # Derive title from latest event detail
    title: Optional[str] = None
    for ev in reversed(events):
        if ev.get("detail"):
            title = ev["detail"]
            break

    # Linked PR / linked issue detection
    linked_pr: Optional[int] = None
    linked_issue: Optional[int] = None
    if kind == "issue":
        # Look for events in same project with same issue_number AND a pr_number
        pr_row = conn.execute(
            """
            SELECT pr_number FROM events
            WHERE project = ? AND issue_number = ? AND pr_number IS NOT NULL
            ORDER BY created_at DESC LIMIT 1
            """,
            (project, number),
        ).fetchone()
        if pr_row:
            linked_pr = pr_row[0]
    else:
        # Look for events in same project with same pr_number AND an issue_number
        iss_row = conn.execute(
            """
            SELECT issue_number FROM events
            WHERE project = ? AND pr_number = ? AND issue_number IS NOT NULL
            ORDER BY created_at DESC LIMIT 1
            """,
            (project, number),
        ).fetchone()
        if iss_row:
            linked_issue = iss_row[0]

    # GitHub URL
    base = f"https://github.com/svv2014/{project}"
    if kind == "issue":
        github_url = f"{base}/issues/{number}"
    else:
        github_url = f"{base}/pull/{number}"

    totals = _compute_totals(events, conn, project)

    # Strip internal fields not in response shape
    clean_events = []
    for ev in events:
        clean_events.append({
            "id": ev["id"],
            "role": ev["role"],
            "event_type": ev["event_type"],
            "model": ev.get("model"),
            "created_at": ev["created_at"],
            "duration_seconds": ev["duration_seconds"],
            "points": None,  # points come from verdicts table, not per-event
            "detail": ev.get("detail"),
        })

    return {
        "project": project,
        "kind": kind,
        "number": number,
        "title": title,
        "github_url": github_url,
        "stage": stage,
        "linked_pr": linked_pr,
        "linked_issue": linked_issue,
        "events": clean_events,
        "totals": totals,
    }

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from server.db import db_dep

router = APIRouter()


@router.get("/api/timeline")
def timeline(
    slug: str,
    num: int,
    skip_reconcile_skip: bool = True,
    conn: sqlite3.Connection = Depends(db_dep),
):
    """Return all events for a single issue/PR in chronological order."""
    if not slug or num <= 0:
        raise HTTPException(status_code=422, detail="slug and num are required")

    rows = conn.execute(
        """
        SELECT id, project, role, model, event_type, issue_number, pr_number,
               detail, payload, loop_id, created_at
        FROM events
        WHERE project = ?
          AND (issue_number = ? OR pr_number = ?)
        ORDER BY created_at ASC, id ASC
        """,
        (slug, num, num),
    ).fetchall()

    result = []
    for r in rows:
        entry = dict(r)
        if entry["payload"]:
            try:
                entry["payload"] = json.loads(entry["payload"])
            except (json.JSONDecodeError, TypeError):
                pass

        # Filter out reconcile_check events where decision == 'skip'
        if skip_reconcile_skip and entry.get("event_type") == "reconcile_check":
            payload = entry.get("payload")
            if isinstance(payload, dict) and payload.get("decision") == "skip":
                continue

        result.append(entry)

    return {"events": result}

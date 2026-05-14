import json
import sqlite3

from fastapi import APIRouter, Depends, Query

from server.db import db_dep

router = APIRouter()


@router.get("/api/timeline")
def timeline(
    slug: str = Query(...),
    num: int = Query(...),
    include_skips: bool = Query(False),
    conn: sqlite3.Connection = Depends(db_dep),
):
    """Per-ticket event timeline ordered ascending by created_at."""
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
        WHERE project = ?
          AND (issue_number = ? OR pr_number = ?)
          {skip_clause}
        ORDER BY created_at ASC, id ASC
        """,
        (slug, num, num),
    ).fetchall()

    events = []
    for r in rows:
        entry = dict(r)
        entry["ts"] = entry["created_at"]
        entry["type"] = entry["event_type"]
        if entry["payload"]:
            try:
                entry["payload"] = json.loads(entry["payload"])
            except (json.JSONDecodeError, TypeError):
                pass
        events.append(entry)

    return {"events": events}

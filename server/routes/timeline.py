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
    """Per-ticket event timeline ordered ascending by timestamp."""
    where_clauses = ["project = ?", "issue_number = ?"]
    params: list = [slug, num]

    if not include_skips:
        where_clauses.append(
            "NOT (event_type = 'reconcile_check'"
            " AND json_extract(payload, '$.decision') = 'skip')"
        )

    where_sql = " AND ".join(where_clauses)

    rows = conn.execute(
        f"""
        SELECT id, project, role, model, event_type, issue_number, pr_number,
               detail, payload, created_at AS ts
        FROM events
        WHERE {where_sql}
        ORDER BY created_at ASC, id ASC
        """,
        params,
    ).fetchall()

    events = []
    for r in rows:
        entry = dict(r)
        if entry["payload"]:
            try:
                entry["payload"] = json.loads(entry["payload"])
            except (json.JSONDecodeError, TypeError):
                entry["payload"] = None
        events.append(entry)

    return {"events": events}

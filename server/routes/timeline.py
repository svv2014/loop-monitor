import json
import sqlite3

from fastapi import APIRouter, Depends

from server.db import db_dep

router = APIRouter()


@router.get("/api/timeline")
def timeline(
    slug: str,
    num: int,
    include_skips: bool = False,
    conn: sqlite3.Connection = Depends(db_dep),
):
    where_clauses = ["project = ?", "issue_number = ?"]
    params: list = [slug, num]

    if not include_skips:
        where_clauses.append(
            "NOT (type = 'reconcile_check' AND json_extract(payload, '$.decision') = 'skip')"
        )

    where_sql = "WHERE " + " AND ".join(where_clauses)

    rows = conn.execute(
        f"""
        SELECT id, ts, type, payload, pr_number
        FROM event_audit
        {where_sql}
        ORDER BY ts ASC, id ASC
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
                pass
        events.append(entry)

    return {"events": events}

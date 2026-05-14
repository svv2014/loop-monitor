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
    """Per-ticket event timeline ordered ascending by created_at.

    By default hides reconcile_check events where payload.decision == 'skip'
    (workflow-aware skip noise). Pass include_skips=true to reveal them.
    """
    skip_clause = (
        ""
        if include_skips
        else "AND NOT (event_type = 'reconcile_check' AND json_extract(payload, '$.decision') = 'skip')"
    )
    rows = conn.execute(
        f"""
        SELECT id, project, role, model, event_type,
               issue_number, pr_number, detail, payload, created_at
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
        row = dict(r)
        payload = None
        if row["payload"]:
            try:
                payload = json.loads(row["payload"])
            except Exception:
                payload = row["payload"]
        events.append({
            "id": row["id"],
            "ts": row["created_at"],
            "type": row["event_type"],
            "payload": payload,
            "project": row["project"],
            "role": row["role"],
            "model": row["model"],
            "issue_number": row["issue_number"],
            "pr_number": row["pr_number"],
            "detail": row["detail"],
        })

    return {"events": events}

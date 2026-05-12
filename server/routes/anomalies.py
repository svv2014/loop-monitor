import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from server.db import db_dep

router = APIRouter()


@router.get("/api/anomalies")
def get_anomalies(
    project: Optional[str] = Query(default=None),
    window_hours: Optional[str] = Query(default=None),
    threshold: Optional[str] = Query(default=None),
    conn: sqlite3.Connection = Depends(db_dep),
):
    # Validate required params
    params = [("project", project), ("window_hours", window_hours), ("threshold", threshold)]
    missing = [p for p, v in params if v is None]
    if missing:
        return JSONResponse(status_code=400, content={"error": f"Missing required parameters: {', '.join(missing)}"})

    # Validate numeric params
    try:
        window_hours_f = float(window_hours)
    except (ValueError, TypeError):
        return JSONResponse(status_code=400, content={"error": "window_hours must be numeric"})

    try:
        threshold_i = int(threshold)
    except (ValueError, TypeError):
        return JSONResponse(status_code=400, content={"error": "threshold must be an integer"})

    since = (datetime.now(timezone.utc) - timedelta(hours=window_hours_f)).isoformat()
    rows = conn.execute(
        """
        SELECT issue_number, COUNT(*) AS touches
        FROM events
        WHERE project = :project
          AND event_type IN ('label_transition', 'reconcile_check')
          AND created_at > :since
          AND issue_number IS NOT NULL
        GROUP BY issue_number
        HAVING COUNT(*) >= :threshold
        ORDER BY touches DESC
        """,
        {"project": project, "since": since, "threshold": threshold_i},
    ).fetchall()
    return [{"issue_number": r["issue_number"], "touches": r["touches"]} for r in rows]

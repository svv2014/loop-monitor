import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from server.db import db_dep

router = APIRouter()


def _positive_float(value: Optional[str], name: str) -> float:
    if value is None:
        raise HTTPException(status_code=400, detail=f"{name} is required")
    try:
        parsed = float(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{name} must be numeric")
    if parsed <= 0:
        raise HTTPException(status_code=400, detail=f"{name} must be positive")
    return parsed


def _positive_int(value: Optional[str], name: str) -> int:
    if value is None:
        raise HTTPException(status_code=400, detail=f"{name} is required")
    try:
        parsed = int(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{name} must be an integer")
    if parsed <= 0:
        raise HTTPException(status_code=400, detail=f"{name} must be positive")
    return parsed


@router.get("/api/anomalies")
def get_anomalies(
    project: Optional[str] = Query(default=None),
    window_hours: Optional[str] = Query(default=None),
    threshold: Optional[str] = Query(default=None),
    conn: sqlite3.Connection = Depends(db_dep),
) -> list[dict]:
    if not project:
        raise HTTPException(status_code=400, detail="project is required")

    parsed_window_hours = _positive_float(window_hours, "window_hours")
    parsed_threshold = _positive_int(threshold, "threshold")
    since = (datetime.now(timezone.utc) - timedelta(hours=parsed_window_hours)).isoformat()

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
        ORDER BY touches DESC, issue_number ASC
        """,
        {
            "project": project,
            "since": since,
            "threshold": parsed_threshold,
        },
    ).fetchall()

    return [
        {"issue_number": row["issue_number"], "touches": row["touches"]}
        for row in rows
    ]

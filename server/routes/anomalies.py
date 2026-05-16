import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from server.db import db_dep

router = APIRouter()


def _required(value: Optional[str], name: str) -> str:
    if value is None or value == "":
        raise HTTPException(status_code=400, detail=f"{name} is required")
    return value


def _parse_window_hours(value: Optional[str]) -> float:
    raw = _required(value, "window_hours")
    try:
        window_hours = float(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="window_hours must be numeric") from None
    if window_hours <= 0:
        raise HTTPException(status_code=400, detail="window_hours must be greater than 0")
    return window_hours


def _parse_threshold(value: Optional[str]) -> int:
    raw = _required(value, "threshold")
    try:
        threshold = int(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="threshold must be an integer") from None
    if threshold <= 0:
        raise HTTPException(status_code=400, detail="threshold must be greater than 0")
    return threshold


@router.get("/api/anomalies")
def anomalies(
    project: Optional[str] = Query(default=None),
    window_hours: Optional[str] = Query(default=None),
    threshold: Optional[str] = Query(default=None),
    conn: sqlite3.Connection = Depends(db_dep),
):
    """Issues with repeated label/reconcile activity inside a rolling window."""
    project_slug = _required(project, "project")
    window = _parse_window_hours(window_hours)
    min_touches = _parse_threshold(threshold)
    since = (datetime.now(timezone.utc) - timedelta(hours=window)).isoformat()

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
        {"project": project_slug, "since": since, "threshold": min_touches},
    ).fetchall()

    return [{"issue_number": r["issue_number"], "touches": r["touches"]} for r in rows]

import sqlite3

from fastapi import APIRouter, Depends

from server.db import db_dep

router = APIRouter()


@router.get("/api/board")
def board(conn: sqlite3.Connection = Depends(db_dep)):
    rows = conn.execute(
        "SELECT project, role, model, total_points, verdict_count FROM scores ORDER BY total_points DESC"
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/api/verdicts")
def get_verdicts(conn: sqlite3.Connection = Depends(db_dep)):
    rows = conn.execute(
        "SELECT id, project, role, model, points, reason, created_at FROM verdicts ORDER BY id DESC LIMIT 50"
    ).fetchall()
    return [dict(r) for r in rows]

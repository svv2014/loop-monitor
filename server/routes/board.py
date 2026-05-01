from fastapi import APIRouter

from server.db import get_db

router = APIRouter()


@router.get("/api/board")
def board():
    conn = get_db()
    rows = conn.execute(
        "SELECT project, role, model, total_points, verdict_count FROM scores ORDER BY total_points DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/api/verdicts")
def get_verdicts():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, project, role, model, points, reason, created_at FROM verdicts ORDER BY id DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

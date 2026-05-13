import sqlite3
import time
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from server.db import db_dep

router = APIRouter()


class SloBody(BaseModel):
    total_seconds: Optional[int] = None
    breach_grace_seconds: int = 3600


@router.get("/api/projects/{slug}/slo")
def get_slo(slug: str, conn: sqlite3.Connection = Depends(db_dep)):
    row = conn.execute(
        "SELECT slug, total_seconds, breach_grace_seconds, updated_at FROM project_slos WHERE slug = ?",
        (slug,),
    ).fetchone()
    if not row:
        return {"slug": slug, "total_seconds": None, "breach_grace_seconds": 3600, "updated_at": None}
    return dict(row)


@router.put("/api/projects/{slug}/slo")
def put_slo(slug: str, body: SloBody, conn: sqlite3.Connection = Depends(db_dep)):
    now = int(time.time())
    conn.execute(
        """INSERT INTO project_slos (slug, total_seconds, breach_grace_seconds, updated_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(slug) DO UPDATE SET
               total_seconds = excluded.total_seconds,
               breach_grace_seconds = excluded.breach_grace_seconds,
               updated_at = excluded.updated_at""",
        (slug, body.total_seconds, body.breach_grace_seconds, now),
    )
    conn.commit()
    return {
        "slug": slug,
        "total_seconds": body.total_seconds,
        "breach_grace_seconds": body.breach_grace_seconds,
        "updated_at": now,
    }

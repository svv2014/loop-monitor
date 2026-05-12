import os
import sqlite3
from datetime import date, timedelta

from fastapi import APIRouter, Depends

from server.db import db_dep

router = APIRouter()


def _tokens_per_event() -> int:
    try:
        return max(1, int(os.environ.get("LOOPMON_TOKENS_PER_EVENT", "5000")))
    except ValueError:
        return 5000


def _input_ratio() -> float:
    try:
        r = float(os.environ.get("LOOPMON_INPUT_RATIO", "0.8"))
        return max(0.0, min(1.0, r))
    except ValueError:
        return 0.8


def _cost_per_1m(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, str(default)))
    except ValueError:
        return default


@router.get("/api/token_spend")
def get_token_spend(conn: sqlite3.Connection = Depends(db_dep)) -> dict:
    today = date.today()
    since = today - timedelta(days=29)  # 30 days so frontend can show today/7d/30d

    rows = conn.execute(
        """
        SELECT
            date(created_at) AS day,
            role,
            project,
            COALESCE(model, '') AS model,
            COUNT(*) AS n
        FROM events
        WHERE date(created_at) >= ?
        GROUP BY day, role, project, model
        ORDER BY day DESC, n DESC
        """,
        (since.isoformat(),),
    ).fetchall()

    tpe = _tokens_per_event()
    ir = _input_ratio()
    c_in = _cost_per_1m("LOOPMON_COST_PER_1M_INPUT", 3.0)
    c_out = _cost_per_1m("LOOPMON_COST_PER_1M_OUTPUT", 15.0)

    result = []
    for row in rows:
        n = row["n"]
        total = n * tpe
        inp = int(total * ir)
        out = total - inp
        cost = (inp / 1_000_000 * c_in) + (out / 1_000_000 * c_out)
        result.append(
            {
                "date": row["day"],
                "role": row["role"],
                "project": row["project"],
                "model": row["model"],
                "event_count": n,
                "input_tokens": inp,
                "output_tokens": out,
                "cost_usd": round(cost, 6),
            }
        )

    return {
        "rows": result,
        "config": {
            "tokens_per_event": tpe,
            "input_ratio": ir,
            "cost_per_1m_input": c_in,
            "cost_per_1m_output": c_out,
        },
    }

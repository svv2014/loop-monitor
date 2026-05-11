"""
GET /api/token_spend

Returns per-role / per-project / per-day token spend estimates derived from
event counts in the events table.  Actual token counts are not stored, so
spend is estimated from event counts × configurable tokens-per-event rates.

Config env vars:
  TOKEN_COST_PER_1M_INPUT    USD per 1M input tokens  (default 3.0)
  TOKEN_COST_PER_1M_OUTPUT   USD per 1M output tokens (default 15.0)
  TOKEN_EST_INPUT_PER_EVENT  estimated input tokens per event (default 50000)
  TOKEN_EST_OUTPUT_PER_EVENT estimated output tokens per event (default 10000)
"""

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter

from server.db import get_db

router = APIRouter()

ROLES = ["po", "dev", "qa", "reviewer", "merge", "judge"]


def _float_env(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, str(default)))
    except ValueError:
        return default


def _est_cost(events: int, cost_1m_in: float, cost_1m_out: float, in_per_ev: float, out_per_ev: float) -> float:
    inp = events * in_per_ev
    out = events * out_per_ev
    return round((inp / 1_000_000) * cost_1m_in + (out / 1_000_000) * cost_1m_out, 4)


@router.get("/api/token_spend")
def get_token_spend() -> dict[str, Any]:
    cost_1m_in = _float_env("TOKEN_COST_PER_1M_INPUT", 3.0)
    cost_1m_out = _float_env("TOKEN_COST_PER_1M_OUTPUT", 15.0)
    in_per_ev = _float_env("TOKEN_EST_INPUT_PER_EVENT", 50_000)
    out_per_ev = _float_env("TOKEN_EST_OUTPUT_PER_EVENT", 10_000)

    now = datetime.now(timezone.utc)
    today_str = now.date().isoformat()
    week_start = (now - timedelta(days=6)).date().isoformat()
    month_start = (now - timedelta(days=29)).date().isoformat()

    conn = get_db()

    rows_7d = conn.execute(
        """
        SELECT date(created_at) AS day, role, COUNT(*) AS event_count
        FROM events
        WHERE date(created_at) >= ?
        GROUP BY day, role
        ORDER BY day
        """,
        (week_start,),
    ).fetchall()

    project_agg = conn.execute(
        """
        SELECT
            project,
            SUM(CASE WHEN date(created_at) = ?  THEN 1 ELSE 0 END) AS today_events,
            SUM(CASE WHEN date(created_at) >= ? THEN 1 ELSE 0 END) AS week_events,
            SUM(CASE WHEN date(created_at) >= ? THEN 1 ELSE 0 END) AS month_events
        FROM events
        WHERE date(created_at) >= ?
        GROUP BY project
        ORDER BY month_events DESC
        """,
        (today_str, week_start, month_start, month_start),
    ).fetchall()

    conn.close()

    # day -> role -> event_count
    day_role: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows_7d:
        day_role[row["day"]][row["role"]] += row["event_count"]

    # Build 7-day chart array (one entry per day, cost keyed by role)
    chart: list[dict[str, Any]] = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).date().isoformat()
        label = (now - timedelta(days=i)).strftime("%m/%d")
        entry: dict[str, Any] = {"date": day, "label": label}
        for role in ROLES:
            ev = day_role[day].get(role, 0)
            entry[role] = _est_cost(ev, cost_1m_in, cost_1m_out, in_per_ev, out_per_ev)
            entry[f"{role}_events"] = ev
            entry[f"{role}_input_tokens"] = int(ev * in_per_ev)
            entry[f"{role}_output_tokens"] = int(ev * out_per_ev)
        chart.append(entry)

    # Per-project table rows
    projects: list[dict[str, Any]] = []
    for row in project_agg:
        te = int(row["today_events"] or 0)
        we = int(row["week_events"] or 0)
        me = int(row["month_events"] or 0)
        projects.append({
            "project": row["project"],
            "today_events": te,
            "week_events": we,
            "month_events": me,
            "today_input_tokens": int(te * in_per_ev),
            "today_output_tokens": int(te * out_per_ev),
            "week_input_tokens": int(we * in_per_ev),
            "week_output_tokens": int(we * out_per_ev),
            "month_input_tokens": int(me * in_per_ev),
            "month_output_tokens": int(me * out_per_ev),
            "today_cost_usd": _est_cost(te, cost_1m_in, cost_1m_out, in_per_ev, out_per_ev),
            "week_cost_usd": _est_cost(we, cost_1m_in, cost_1m_out, in_per_ev, out_per_ev),
            "month_cost_usd": _est_cost(me, cost_1m_in, cost_1m_out, in_per_ev, out_per_ev),
        })

    return {
        "chart": chart,
        "projects": projects,
        "config": {
            "cost_per_1m_input": cost_1m_in,
            "cost_per_1m_output": cost_1m_out,
            "est_input_per_event": in_per_ev,
            "est_output_per_event": out_per_ev,
        },
    }

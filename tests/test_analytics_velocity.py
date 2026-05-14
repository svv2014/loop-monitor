"""Tests for GET /api/analytics/velocity.

Scenarios:
  a) empty table → all-zero response, no div-by-zero
  b) seeded rows → today, avg_per_day, daily, per_project reflect them
  c) project=<slug> filter restricts count
  d) invalid days param → 400
"""
import sqlite3
from datetime import datetime, timezone

import server.db


def _insert_run(conn: sqlite3.Connection, project: str, completed_at: str, outcome: str = "clean") -> None:
    conn.execute(
        """INSERT INTO pipeline_runs (project, issue_number, outcome, completed_at, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (project, 1, outcome, completed_at, completed_at),
    )
    conn.commit()


# ── a) empty table ────────────────────────────────────────────────────────────

def test_velocity_empty_table(isolated_client):
    """All-zero response when pipeline_runs is empty — no division by zero."""
    resp = isolated_client.get("/api/analytics/velocity?days=30")
    assert resp.status_code == 200
    data = resp.json()

    assert data["today"] == 0
    assert data["avg_per_day"] == 0.0
    assert data["prev_period_avg"] == 0.0
    assert data["trend_pct"] == 0.0
    assert len(data["daily"]) == 30
    assert data["per_project"] == []

    # every daily bucket should be zero
    for bucket in data["daily"]:
        assert bucket["count"] == 0


# ── b) seeded rows ────────────────────────────────────────────────────────────

def test_velocity_with_seeded_rows(isolated_client):
    """today count, avg_per_day, daily list, and per_project reflect inserted rows."""
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.row_factory = sqlite3.Row

    # Use today's UTC date so the 'today' field is populated
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _insert_run(conn, "alpha", f"{today_str}T10:00:00")
    _insert_run(conn, "alpha", f"{today_str}T11:00:00")
    _insert_run(conn, "beta",  f"{today_str}T12:00:00")
    conn.close()

    resp = isolated_client.get("/api/analytics/velocity?days=30")
    assert resp.status_code == 200
    data = resp.json()

    # 3 merged today across both projects
    assert data["today"] == 3
    # avg across 30 days = 3 / 30
    assert data["avg_per_day"] == round(3 / 30, 2)

    # daily list has 30 entries and the last entry (today) has count 3
    assert len(data["daily"]) == 30
    last_bucket = data["daily"][-1]
    assert last_bucket["date"] == today_str
    assert last_bucket["count"] == 3

    # per_project: both projects present
    slugs = {p["slug"] for p in data["per_project"]}
    assert "alpha" in slugs
    assert "beta" in slugs

    alpha = next(p for p in data["per_project"] if p["slug"] == "alpha")
    assert alpha["today"] == 2

    beta = next(p for p in data["per_project"] if p["slug"] == "beta")
    assert beta["today"] == 1


# ── c) project filter ─────────────────────────────────────────────────────────

def test_velocity_project_filter(isolated_client):
    """project= query param restricts counts to that slug only."""
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.row_factory = sqlite3.Row

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _insert_run(conn, "proj-a", f"{today_str}T09:00:00")
    _insert_run(conn, "proj-a", f"{today_str}T09:30:00")
    _insert_run(conn, "proj-b", f"{today_str}T10:00:00")
    conn.close()

    # Filter to proj-a only
    resp = isolated_client.get("/api/analytics/velocity?days=30&project=proj-a")
    assert resp.status_code == 200
    data = resp.json()

    assert data["today"] == 2
    # per_project is empty when a project filter is active
    assert data["per_project"] == []

    # proj-b should not contribute
    resp_b = isolated_client.get("/api/analytics/velocity?days=30&project=proj-b")
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert data_b["today"] == 1


# ── d) invalid days param → 400 ───────────────────────────────────────────────

def test_velocity_invalid_days_returns_400(isolated_client):
    """Non-integer days value must return HTTP 400."""
    resp = isolated_client.get("/api/analytics/velocity?days=abc")
    assert resp.status_code == 400

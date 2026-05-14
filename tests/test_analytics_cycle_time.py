import json
import sqlite3

import pytest

import server.db


def _insert_transition(conn, project, issue_number, before_labels, after_labels, created_at):
    payload = json.dumps({"before_labels": before_labels, "after_labels": after_labels})
    conn.execute(
        """INSERT INTO events (project, role, event_type, issue_number, payload, created_at)
           VALUES (?, 'scanner', 'label_transition', ?, ?, ?)""",
        (project, issue_number, payload, created_at),
    )


def test_cycle_time_empty(isolated_client):
    resp = isolated_client.get("/api/analytics/cycle_time?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stages"] == []
    assert data["lead_time"] is None


def test_cycle_time_stages(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.row_factory = sqlite3.Row

    # Six issues each spending 1 hour in needs-po state.
    for i in range(1, 7):
        _insert_transition(conn, "proj-s", i, [], ["needs-po"], f"2026-01-{i:02d}T10:00:00")
        _insert_transition(conn, "proj-s", i, ["needs-po"], ["in-po"], f"2026-01-{i:02d}T11:00:00")

    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/analytics/cycle_time?days=365")
    assert resp.status_code == 200
    data = resp.json()

    stages_by_name = {s["stage"]: s for s in data["stages"]}

    npo = stages_by_name.get("needs-po->in-po")
    assert npo is not None
    assert npo["count"] == 6
    assert npo["p50"] == pytest.approx(3600, rel=0.01)
    assert npo["p75"] >= npo["p50"]
    assert npo["p95"] >= npo["p75"]
    assert "p50" in npo and "p75" in npo and "p95" in npo


def test_cycle_time_lead_time(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.row_factory = sqlite3.Row

    # Five issues with lead times of 1d, 2d, 3d, 4d, 5d.
    one_day = 86400
    for i in range(1, 6):
        _insert_transition(conn, "proj-lt", i, [], ["needs-po"], "2026-02-01T00:00:00")
        _insert_transition(conn, "proj-lt", i, ["needs-po", "in-dev"], ["done"],
                           f"2026-02-{1 + i:02d}T00:00:00")

    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/analytics/cycle_time?days=365")
    assert resp.status_code == 200
    data = resp.json()

    lt = data["lead_time"]
    assert lt is not None
    assert lt["count"] == 5
    # sorted: [1d, 2d, 3d, 4d, 5d]; floor(0.5 * 5) = 2 → index 2 → 3d
    assert lt["p50"] == pytest.approx(3 * one_day, rel=0.01)
    assert lt["p75"] >= lt["p50"]
    assert lt["p95"] >= lt["p75"]


def test_cycle_time_days_filter(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.row_factory = sqlite3.Row

    # Transitions >60 days in the past — should be excluded when days=30.
    for i in range(1, 7):
        _insert_transition(conn, "proj-df", i, [], ["needs-po"], "2025-01-01T00:00:00")
        _insert_transition(conn, "proj-df", i, ["needs-po"], ["in-po"], "2025-01-01T01:00:00")

    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/analytics/cycle_time?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stages"] == []
    assert data["lead_time"] is None

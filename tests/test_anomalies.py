import sqlite3
from datetime import datetime, timedelta, timezone

import server.db


def _insert_event(conn, project, event_type, issue_number, created_at):
    conn.execute(
        """
        INSERT INTO events (project, role, event_type, issue_number, created_at)
        VALUES (?, 'dev', ?, ?, ?)
        """,
        (project, event_type, issue_number, created_at),
    )
    conn.commit()


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _hours_ago_iso(hours):
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


# ── (a) no events → empty list ────────────────────────────────────────────────

def test_no_events_returns_empty(isolated_client):
    resp = isolated_client.get("/api/anomalies?project=myproject&window_hours=24&threshold=2")
    assert resp.status_code == 200
    assert resp.json() == []


# ── (b) one issue over threshold → returned ───────────────────────────────────

def test_issue_over_threshold_returned(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    for _ in range(3):
        _insert_event(conn, "proj", "label_transition", 42, _now_iso())
    conn.close()

    resp = isolated_client.get("/api/anomalies?project=proj&window_hours=24&threshold=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["issue_number"] == 42
    assert data[0]["touches"] == 3


# ── (c) one issue below threshold → not returned ──────────────────────────────

def test_issue_below_threshold_excluded(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert_event(conn, "proj", "label_transition", 99, _now_iso())
    conn.close()

    resp = isolated_client.get("/api/anomalies?project=proj&window_hours=24&threshold=3")
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["issue_number"] != 99 for item in data)


# ── (d) events outside the window → not counted ───────────────────────────────

def test_events_outside_window_not_counted(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    old_ts = _hours_ago_iso(48)
    for _ in range(5):
        _insert_event(conn, "proj-old", "label_transition", 7, old_ts)
    conn.close()

    resp = isolated_client.get("/api/anomalies?project=proj-old&window_hours=24&threshold=2")
    assert resp.status_code == 200
    assert resp.json() == []


# ── (e) wrong event_type → not counted ────────────────────────────────────────

def test_wrong_event_type_not_counted(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    for _ in range(5):
        _insert_event(conn, "proj-et", "dev_done", 55, _now_iso())
    conn.close()

    resp = isolated_client.get("/api/anomalies?project=proj-et&window_hours=24&threshold=2")
    assert resp.status_code == 200
    assert resp.json() == []


# ── unknown project → empty list (no error) ───────────────────────────────────

def test_unknown_project_returns_empty(isolated_client):
    resp = isolated_client.get("/api/anomalies?project=no-such-project&window_hours=24&threshold=1")
    assert resp.status_code == 200
    assert resp.json() == []


# ── 400 for missing params ────────────────────────────────────────────────────

def test_missing_all_params_returns_400(isolated_client):
    resp = isolated_client.get("/api/anomalies")
    assert resp.status_code == 400


def test_missing_project_returns_400(isolated_client):
    resp = isolated_client.get("/api/anomalies?window_hours=24&threshold=2")
    assert resp.status_code == 400


def test_missing_window_hours_returns_400(isolated_client):
    resp = isolated_client.get("/api/anomalies?project=p&threshold=2")
    assert resp.status_code == 400


def test_missing_threshold_returns_400(isolated_client):
    resp = isolated_client.get("/api/anomalies?project=p&window_hours=24")
    assert resp.status_code == 400


# ── 400 for non-numeric params ────────────────────────────────────────────────

def test_non_numeric_window_hours_returns_400(isolated_client):
    resp = isolated_client.get("/api/anomalies?project=p&window_hours=abc&threshold=2")
    assert resp.status_code == 400


def test_non_numeric_threshold_returns_400(isolated_client):
    resp = isolated_client.get("/api/anomalies?project=p&window_hours=24&threshold=xyz")
    assert resp.status_code == 400


# ── both event types counted ─────────────────────────────────────────────────

def test_both_event_types_counted(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert_event(conn, "proj-both", "label_transition", 10, _now_iso())
    _insert_event(conn, "proj-both", "reconcile_check", 10, _now_iso())
    conn.close()

    resp = isolated_client.get("/api/anomalies?project=proj-both&window_hours=24&threshold=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["issue_number"] == 10
    assert data[0]["touches"] == 2

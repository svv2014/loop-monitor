import sqlite3

import server
import server.db


def test_events_graph_empty_db(isolated_client):
    resp = isolated_client.get("/api/events_graph")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"window_hours": 24, "buckets": []}


def test_events_graph_with_data(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        "INSERT INTO events (project, role, event_type, created_at) VALUES (?,?,?,?)",
        ("proj-g", "po", "po_done", "2026-04-28T10:00:00"),
    )
    conn.execute(
        "INSERT INTO events (project, role, event_type, created_at) VALUES (?,?,?,?)",
        ("proj-g", "po", "po_done", "2026-04-28T10:30:00"),
    )
    conn.execute(
        "INSERT INTO events (project, role, event_type, created_at) VALUES (?,?,?,?)",
        ("proj-g", "dev", "dev_done", "2026-04-28T11:00:00"),
    )
    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/events_graph?window=168")
    assert resp.status_code == 200
    data = resp.json()
    assert data["window_hours"] == 168
    buckets = data["buckets"]
    assert isinstance(buckets, list)
    po_bucket = next((b for b in buckets if b["role"] == "po" and b["hour"] == "2026-04-28T10:00:00"), None)
    assert po_bucket is not None
    assert po_bucket["count"] == 2
    dev_bucket = next((b for b in buckets if b["role"] == "dev"), None)
    assert dev_bucket is not None
    assert dev_bucket["count"] == 1


def test_events_graph_window_param(isolated_client):
    resp = isolated_client.get("/api/events_graph?window=48")
    assert resp.status_code == 200
    data = resp.json()
    assert data["window_hours"] == 48


def test_events_graph_window_clamped_to_max(isolated_client):
    resp = isolated_client.get("/api/events_graph?window=9999")
    assert resp.status_code == 200
    data = resp.json()
    assert data["window_hours"] == 168


def test_events_graph_default_window(isolated_client):
    resp = isolated_client.get("/api/events_graph")
    assert resp.status_code == 200
    data = resp.json()
    assert data["window_hours"] == 24

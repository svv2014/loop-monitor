import sqlite3
from datetime import datetime, timedelta

import server
import server.db


def test_events_graph_empty_db(isolated_client):
    resp = isolated_client.get("/api/events_graph")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"window_hours": 24, "buckets": []}


def test_events_graph_with_data(isolated_client):
    base = (datetime.now() - timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
    first = base.isoformat()
    second = (base + timedelta(minutes=30)).isoformat()
    third = (base + timedelta(hours=1)).isoformat()
    first_hour = base.strftime("%Y-%m-%dT%H:00:00")

    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        "INSERT INTO events (project, role, event_type, created_at) VALUES (?,?,?,?)",
        ("proj-g", "po", "po_done", first),
    )
    conn.execute(
        "INSERT INTO events (project, role, event_type, created_at) VALUES (?,?,?,?)",
        ("proj-g", "po", "po_done", second),
    )
    conn.execute(
        "INSERT INTO events (project, role, event_type, created_at) VALUES (?,?,?,?)",
        ("proj-g", "dev", "dev_done", third),
    )
    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/events_graph?window=168")
    assert resp.status_code == 200
    data = resp.json()
    assert data["window_hours"] == 168
    buckets = data["buckets"]
    assert isinstance(buckets, list)
    po_bucket = next((b for b in buckets if b["role"] == "po" and b["hour"] == first_hour), None)
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


def test_events_graph_counts_legacy_judge_rows_as_judge_role(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        """INSERT INTO events
           (project, role, event_type, issue_number, created_at)
           VALUES (?, ?, ?, ?, datetime('now', '-1 hour'))""",
        ("proj-judge-graph", "dev", "judge", 213),
    )
    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/events_graph?window=24")
    assert resp.status_code == 200
    buckets = resp.json()["buckets"]

    judge_bucket = next((b for b in buckets if b["role"] == "judge"), None)
    assert judge_bucket is not None
    assert judge_bucket["count"] == 1


def test_timeline_remaps_legacy_judge_pr_rows(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        """INSERT INTO events
           (project, role, event_type, issue_number, pr_number, created_at)
           VALUES (?, ?, ?, ?, ?, datetime('now', '-1 hour'))""",
        ("proj-judge-timeline", "dev", "judge", 213, 17),
    )
    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/stats/timeline/pr/proj-judge-timeline/17")
    assert resp.status_code == 200
    events = resp.json()["events"]

    assert len(events) == 1
    assert events[0]["project"] == "proj-judge-timeline"
    assert events[0]["role"] == "judge"
    assert events[0]["event_type"] == "judge_done"
    assert events[0]["issue_number"] == 213
    assert events[0]["pr_number"] == 17

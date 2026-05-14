import json
import sqlite3

import server.db


def _insert(conn, *, project, issue_number, event_type, payload=None, created_at="2026-01-01T00:00:00"):
    conn.execute(
        "INSERT INTO events (project, role, event_type, issue_number, payload, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (project, "dev", event_type, issue_number, json.dumps(payload) if payload else None, created_at),
    )
    conn.commit()


def test_timeline_happy_path(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert(conn, project="proj-tl", issue_number=42, event_type="dev_start", created_at="2026-01-01T00:00:00")
    _insert(conn, project="proj-tl", issue_number=42, event_type="dev_done", created_at="2026-01-01T00:01:00")
    conn.close()

    resp = isolated_client.get("/api/timeline?slug=proj-tl&num=42")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert len(data["events"]) == 2
    types = [e["event_type"] for e in data["events"]]
    assert types == ["dev_start", "dev_done"]
    # ascending by ts
    assert data["events"][0]["ts"] <= data["events"][1]["ts"]


def test_timeline_empty(isolated_client):
    resp = isolated_client.get("/api/timeline?slug=no-such-project&num=9999")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"events": []}


def test_timeline_skip_filter_default(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert(conn, project="proj-skip", issue_number=1, event_type="dev_start", created_at="2026-01-01T00:00:00")
    _insert(
        conn, project="proj-skip", issue_number=1, event_type="reconcile_check",
        payload={"decision": "skip", "reason": "workflow-aware skip"},
        created_at="2026-01-01T00:01:00",
    )
    _insert(conn, project="proj-skip", issue_number=1, event_type="dev_done", created_at="2026-01-01T00:02:00")
    conn.close()

    # By default, reconcile_check decision=skip are hidden
    resp = isolated_client.get("/api/timeline?slug=proj-skip&num=1")
    assert resp.status_code == 200
    types = [e["event_type"] for e in resp.json()["events"]]
    assert "reconcile_check" not in types
    assert "dev_start" in types
    assert "dev_done" in types


def test_timeline_skip_filter_revealed(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert(conn, project="proj-skip2", issue_number=2, event_type="dev_start", created_at="2026-01-01T00:00:00")
    _insert(
        conn, project="proj-skip2", issue_number=2, event_type="reconcile_check",
        payload={"decision": "skip"},
        created_at="2026-01-01T00:01:00",
    )
    conn.close()

    resp = isolated_client.get("/api/timeline?slug=proj-skip2&num=2&include_skips=true")
    assert resp.status_code == 200
    types = [e["event_type"] for e in resp.json()["events"]]
    assert "reconcile_check" in types


def test_timeline_non_skip_reconcile_shown_by_default(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert(
        conn, project="proj-rec", issue_number=3, event_type="reconcile_check",
        payload={"decision": "proceed"},
        created_at="2026-01-01T00:00:00",
    )
    conn.close()

    resp = isolated_client.get("/api/timeline?slug=proj-rec&num=3")
    assert resp.status_code == 200
    types = [e["event_type"] for e in resp.json()["events"]]
    assert "reconcile_check" in types


def test_timeline_scope_isolation(isolated_client):
    """Events from a different issue are not returned."""
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert(conn, project="proj-iso", issue_number=10, event_type="dev_start", created_at="2026-01-01T00:00:00")
    _insert(conn, project="proj-iso", issue_number=20, event_type="dev_start", created_at="2026-01-01T00:00:00")
    conn.close()

    resp = isolated_client.get("/api/timeline?slug=proj-iso&num=10")
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert all(e["issue_number"] == 10 for e in events)
    assert len(events) == 1

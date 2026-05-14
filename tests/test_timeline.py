import json
import sqlite3

import server.db

TS0 = "2026-01-01T00:00:00+00:00"


def _ins(conn, project, role, event_type, issue_number=None, pr_number=None, payload=None, created_at=TS0):
    conn.execute(
        "INSERT INTO events (project, role, event_type, issue_number, pr_number, payload, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (project, role, event_type, issue_number, pr_number, json.dumps(payload) if payload else None, created_at),
    )
    conn.commit()


def test_timeline_happy_path(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _ins(conn, "proj-tl", "dev", "dev_start", issue_number=42, created_at="2026-01-01T00:00:01+00:00")
    _ins(conn, "proj-tl", "qa", "qa_pass", issue_number=42, created_at="2026-01-01T00:00:02+00:00")
    conn.close()

    resp = isolated_client.get("/api/timeline?slug=proj-tl&num=42")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    events = data["events"]
    assert len(events) == 2
    # ascending order
    assert events[0]["type"] == "dev_start"
    assert events[1]["type"] == "qa_pass"
    assert events[0]["ts"] < events[1]["ts"]


def test_timeline_empty_result(isolated_client):
    resp = isolated_client.get("/api/timeline?slug=no-such-project&num=9999")
    assert resp.status_code == 200
    assert resp.json() == {"events": []}


def test_timeline_skip_filter_hides_by_default(isolated_client):
    """reconcile_check/skip events are hidden when include_skips is omitted."""
    conn = sqlite3.connect(server.db.DB_PATH)
    _ins(conn, "proj-sk", "reconciler", "reconcile_check", issue_number=7,
         payload={"decision": "skip", "reason": "workflow-aware skip"},
         created_at="2026-01-01T00:00:01+00:00")
    _ins(conn, "proj-sk", "dev", "dev_start", issue_number=7,
         created_at="2026-01-01T00:00:02+00:00")
    conn.close()

    resp = isolated_client.get("/api/timeline?slug=proj-sk&num=7")
    assert resp.status_code == 200
    types = [e["type"] for e in resp.json()["events"]]
    assert "dev_start" in types
    assert "reconcile_check" not in types


def test_timeline_skip_filter_revealed_with_flag(isolated_client):
    """With include_skips=true, reconcile_check/skip events are returned."""
    conn = sqlite3.connect(server.db.DB_PATH)
    _ins(conn, "proj-sk2", "reconciler", "reconcile_check", issue_number=8,
         payload={"decision": "skip"},
         created_at="2026-01-01T00:00:01+00:00")
    conn.close()

    resp = isolated_client.get("/api/timeline?slug=proj-sk2&num=8&include_skips=true")
    assert resp.status_code == 200
    types = [e["type"] for e in resp.json()["events"]]
    assert "reconcile_check" in types


def test_timeline_non_skip_reconcile_always_shown(isolated_client):
    """reconcile_check events with decision != 'skip' are not filtered."""
    conn = sqlite3.connect(server.db.DB_PATH)
    _ins(conn, "proj-sk3", "reconciler", "reconcile_check", issue_number=9,
         payload={"decision": "act"},
         created_at="2026-01-01T00:00:01+00:00")
    conn.close()

    resp = isolated_client.get("/api/timeline?slug=proj-sk3&num=9")
    assert resp.status_code == 200
    types = [e["type"] for e in resp.json()["events"]]
    assert "reconcile_check" in types


def test_timeline_event_fields(isolated_client):
    """Each event includes ts, type, payload, role, and other required fields."""
    conn = sqlite3.connect(server.db.DB_PATH)
    _ins(conn, "proj-tf", "dev", "dev_done", issue_number=10,
         payload={"result": "ok"}, created_at="2026-01-01T00:00:01+00:00")
    conn.close()

    resp = isolated_client.get("/api/timeline?slug=proj-tf&num=10")
    events = resp.json()["events"]
    assert len(events) == 1
    e = events[0]
    assert e["ts"] == "2026-01-01T00:00:01+00:00"
    assert e["type"] == "dev_done"
    assert e["payload"] == {"result": "ok"}
    assert e["role"] == "dev"
    assert "id" in e
    assert e["issue_number"] == 10

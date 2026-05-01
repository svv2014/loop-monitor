import sqlite3

import server
import server.db


def test_action_queue_empty(isolated_client):
    resp = isolated_client.get("/api/action_queue")
    assert resp.status_code == 200
    assert resp.json() == []


def test_action_queue_blocked_label(isolated_client):
    server._insert_event(server.ReportPayload(
        project="boba-event", role="dev", event_type="blocked", issue_number=42,
        detail="needs human"
    ))
    resp = isolated_client.get("/api/action_queue")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["project"] == "boba-event"
    assert data[0]["kind"] == "issue"
    assert data[0]["number"] == 42
    assert data[0]["stage"] == "blocked"
    assert data[0]["reason"] == "stuck_label"
    assert data[0]["github_url"].endswith("/issues/42")


def test_action_queue_needs_clarification(isolated_client):
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="needs-clarification", issue_number=7
    ))
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    assert any(item["reason"] == "stuck_label" and item["stage"] == "needs-clarification" for item in data)


def test_action_queue_timeout_threshold(isolated_client, monkeypatch):
    monkeypatch.setenv("HANDLER_TIMEOUT", "100")  # threshold = 200
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="in-progress", issue_number=11
    ))
    # backdate created_at to 300s ago — exceeds 200s threshold
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        "UPDATE events SET created_at = datetime('now', '-300 seconds') WHERE issue_number = 11"
    )
    conn.commit()
    conn.close()
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    timeout_items = [it for it in data if it["reason"] == "timeout" and it["number"] == 11]
    assert len(timeout_items) == 1
    assert timeout_items[0]["stage"] == "in-progress"
    assert timeout_items[0]["age_seconds"] >= 200


def test_action_queue_in_progress_below_threshold_excluded(isolated_client, monkeypatch):
    monkeypatch.setenv("HANDLER_TIMEOUT", "3600")
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="in-progress", issue_number=13
    ))
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    assert all(it["number"] != 13 for it in data)


def test_action_queue_sorted_by_age_desc(isolated_client, monkeypatch):
    monkeypatch.setenv("HANDLER_TIMEOUT", "100")
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="blocked", issue_number=200
    ))
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="blocked", issue_number=201
    ))
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        "UPDATE events SET created_at = datetime('now', '-9000 seconds') WHERE issue_number = 200"
    )
    conn.commit()
    conn.close()
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    nums = [it["number"] for it in data if it["number"] in (200, 201)]
    assert nums == [200, 201]

import json
import sqlite3

import server
import server.db


def _insert_raw(
    slug: str, issue_num: int | None, event_type: str,
    payload: dict | None = None, pr_num: int | None = None,
):
    """Insert directly into the events table for precise test control."""
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        "INSERT INTO events (project, role, event_type, issue_number, pr_number, payload, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
        (slug, "test-role", event_type, issue_num, pr_num, json.dumps(payload) if payload else None),
    )
    conn.commit()
    conn.close()


def test_timeline_happy_path(isolated_client):
    """Events for a valid slug+num are returned in ascending order."""
    _insert_raw("proj-a", 7, "dev_start")
    _insert_raw("proj-a", 7, "dev_done")

    resp = isolated_client.get("/api/timeline?slug=proj-a&num=7")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    events = data["events"]
    assert len(events) == 2
    # Verify ascending order by checking event types sequence
    types = [e["event_type"] for e in events]
    assert types == ["dev_start", "dev_done"]


def test_timeline_empty_result(isolated_client):
    """Returns {events: []} with HTTP 200 when no events exist for the slug+num."""
    resp = isolated_client.get("/api/timeline?slug=nonexistent-proj&num=999")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"events": []}


def test_timeline_skip_reconcile_skip_default(isolated_client):
    """reconcile_check events with decision=skip are hidden by default."""
    _insert_raw("proj-b", 3, "dev_start")
    _insert_raw("proj-b", 3, "reconcile_check", payload={"decision": "skip", "reason": "no change"})
    _insert_raw("proj-b", 3, "reconcile_check", payload={"decision": "act", "reason": "labels changed"})
    _insert_raw("proj-b", 3, "dev_done")

    # Default: skip_reconcile_skip=true → only 3 events
    resp = isolated_client.get("/api/timeline?slug=proj-b&num=3")
    assert resp.status_code == 200
    data = resp.json()
    events = data["events"]
    assert "reconcile_check" not in [
        e["event_type"] for e in events
        if isinstance(e.get("payload"), dict) and e["payload"].get("decision") == "skip"
    ]
    # The act event should still be present
    assert any(e["event_type"] == "reconcile_check" for e in events), "non-skip reconcile_check should survive"
    assert len(events) == 3  # dev_start + reconcile_check(act) + dev_done


def test_timeline_show_skipped_events_when_toggled(isolated_client):
    """All events including reconcile_check/skip are returned when skip_reconcile_skip=false."""
    _insert_raw("proj-c", 5, "dev_start")
    _insert_raw("proj-c", 5, "reconcile_check", payload={"decision": "skip"})
    _insert_raw("proj-c", 5, "dev_done")

    resp = isolated_client.get("/api/timeline?slug=proj-c&num=5&skip_reconcile_skip=false")
    assert resp.status_code == 200
    data = resp.json()
    events = data["events"]
    assert len(events) == 3
    skip_events = [e for e in events if e.get("event_type") == "reconcile_check"]
    assert len(skip_events) == 1


def test_timeline_filters_by_slug_and_num(isolated_client):
    """Events from other projects or issue numbers are not included."""
    _insert_raw("proj-d", 1, "po_done")
    _insert_raw("proj-d", 2, "qa_pass")
    _insert_raw("proj-e", 1, "merge_done")

    resp = isolated_client.get("/api/timeline?slug=proj-d&num=1")
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert len(events) == 1
    assert events[0]["event_type"] == "po_done"
    assert events[0]["project"] == "proj-d"


def test_timeline_includes_pr_number_events(isolated_client):
    """Events matching by pr_number are also included."""
    _insert_raw("proj-f", None, "merge_done", pr_num=42)

    resp = isolated_client.get("/api/timeline?slug=proj-f&num=42")
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert len(events) == 1
    assert events[0]["pr_number"] == 42


def test_timeline_payload_decoded_as_json(isolated_client):
    """Payload is returned as a decoded object, not a JSON string."""
    _insert_raw("proj-g", 10, "label_change", payload={"label": "loop:stage:dev", "action": "added"})

    resp = isolated_client.get("/api/timeline?slug=proj-g&num=10")
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert len(events) == 1
    payload = events[0]["payload"]
    assert isinstance(payload, dict)
    assert payload["label"] == "loop:stage:dev"

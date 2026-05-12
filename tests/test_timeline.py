import json
import sqlite3

import server.db


def _insert_audit(
    db_path: str, project: str, issue_number: int, ts: str, type_: str,
    payload: dict | None = None, pr_number: int | None = None,
):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO event_audit (project, issue_number, pr_number, ts, type, payload) VALUES (?, ?, ?, ?, ?, ?)",
        (project, issue_number, pr_number, ts, type_, json.dumps(payload) if payload is not None else None),
    )
    conn.commit()
    conn.close()


def test_timeline_happy_path(isolated_client):
    db = server.db.DB_PATH
    _insert_audit(db, "myproj", 42, "2026-01-01T10:00:00Z", "label_change", {"from": "open", "to": "in-progress"})
    _insert_audit(db, "myproj", 42, "2026-01-01T11:00:00Z", "handler_run", {"handler": "dev"})
    _insert_audit(db, "myproj", 42, "2026-01-01T12:00:00Z", "merge", None)

    resp = isolated_client.get("/api/timeline?slug=myproj&num=42")
    assert resp.status_code == 200

    data = resp.json()
    assert "events" in data
    events = data["events"]
    assert len(events) == 3
    assert events[0]["type"] == "label_change"
    assert events[1]["type"] == "handler_run"
    assert events[2]["type"] == "merge"
    # ascending order by ts
    assert events[0]["ts"] < events[1]["ts"] < events[2]["ts"]
    # payload deserialized
    assert events[0]["payload"] == {"from": "open", "to": "in-progress"}
    assert events[2]["payload"] is None


def test_timeline_empty(isolated_client):
    resp = isolated_client.get("/api/timeline?slug=no-such-project&num=999")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"events": []}


def test_timeline_skip_filter_default(isolated_client):
    """reconcile_check with decision=skip is hidden by default."""
    db = server.db.DB_PATH
    _insert_audit(db, "proj-skip", 1, "2026-01-01T09:00:00Z", "label_change")
    _insert_audit(db, "proj-skip", 1, "2026-01-01T09:01:00Z", "reconcile_check",
                  {"decision": "skip", "reason": "workflow-aware"})
    _insert_audit(db, "proj-skip", 1, "2026-01-01T09:02:00Z", "reconcile_check", {"decision": "run"})

    resp = isolated_client.get("/api/timeline?slug=proj-skip&num=1")
    assert resp.status_code == 200
    events = resp.json()["events"]
    types = [e["type"] for e in events]
    # skip is filtered, run is kept
    assert types.count("label_change") == 1
    assert types.count("reconcile_check") == 1
    assert events[1]["payload"]["decision"] == "run"


def test_timeline_include_skips(isolated_client):
    """include_skips=true reveals reconcile_check decision=skip events."""
    db = server.db.DB_PATH
    _insert_audit(db, "proj-skips2", 2, "2026-01-01T08:00:00Z", "reconcile_check", {"decision": "skip"})
    _insert_audit(db, "proj-skips2", 2, "2026-01-01T08:01:00Z", "reconcile_check", {"decision": "run"})

    resp = isolated_client.get("/api/timeline?slug=proj-skips2&num=2&include_skips=true")
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert len(events) == 2
    decisions = [e["payload"]["decision"] for e in events]
    assert "skip" in decisions
    assert "run" in decisions


def test_timeline_isolates_by_project(isolated_client):
    """Events from a different project are not returned."""
    db = server.db.DB_PATH
    _insert_audit(db, "proj-a", 10, "2026-01-01T07:00:00Z", "merge")
    _insert_audit(db, "proj-b", 10, "2026-01-01T07:01:00Z", "handler_run")

    resp = isolated_client.get("/api/timeline?slug=proj-a&num=10")
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert len(events) == 1
    assert events[0]["type"] == "merge"

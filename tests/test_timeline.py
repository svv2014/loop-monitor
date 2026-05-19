import json
import sqlite3
from typing import Optional

import server.db


def _insert(conn: sqlite3.Connection, project: str, event_type: str, issue_number: Optional[int] = None,
            pr_number: Optional[int] = None, payload: Optional[dict] = None, created_at: str = "2026-01-01T00:00:00"):
    conn.execute(
        """INSERT INTO events (project, role, event_type, issue_number, pr_number, payload, created_at)
           VALUES (?, 'dev', ?, ?, ?, ?, ?)""",
        (project, event_type, issue_number, pr_number,
         json.dumps(payload) if payload else None, created_at),
    )
    conn.commit()


def test_timeline_happy_path(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert(conn, "proj-tl", "dev_start", issue_number=42, created_at="2026-01-01T00:00:01")
    _insert(conn, "proj-tl", "dev_done",  issue_number=42, created_at="2026-01-01T00:00:02")
    conn.close()

    resp = isolated_client.get("/api/timeline?slug=proj-tl&num=42")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    events = data["events"]
    assert len(events) == 2
    # Ordered ascending by ts
    assert events[0]["ts"] <= events[1]["ts"]
    assert events[0]["type"] == "dev_start"
    assert events[1]["type"] == "dev_done"
    # ts and type aliases present
    assert "ts" in events[0]
    assert "type" in events[0]


def test_timeline_empty_result(isolated_client):
    resp = isolated_client.get("/api/timeline?slug=no-such-project&num=999")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"events": []}


def test_timeline_filters_reconcile_skip_by_default(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert(conn, "proj-skip", "dev_done", issue_number=7,
            created_at="2026-01-01T00:00:01")
    _insert(conn, "proj-skip", "reconcile_check", issue_number=7,
            payload={"decision": "skip"}, created_at="2026-01-01T00:00:02")
    _insert(conn, "proj-skip", "reconcile_check", issue_number=7,
            payload={"decision": "run"}, created_at="2026-01-01T00:00:03")
    conn.close()

    # Default: skip-decision reconcile_check hidden
    resp = isolated_client.get("/api/timeline?slug=proj-skip&num=7")
    assert resp.status_code == 200
    events = resp.json()["events"]
    types = [e["type"] for e in events]
    assert "dev_done" in types
    assert {"decision": "run"} in [e.get("payload") for e in events if e["type"] == "reconcile_check"]
    skip_events = [e for e in events if e["type"] == "reconcile_check" and
                   isinstance(e.get("payload"), dict) and e["payload"].get("decision") == "skip"]
    assert len(skip_events) == 0


def test_timeline_include_skips_shows_all(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert(conn, "proj-incl", "dev_done", issue_number=8,
            created_at="2026-01-01T00:00:01")
    _insert(conn, "proj-incl", "reconcile_check", issue_number=8,
            payload={"decision": "skip"}, created_at="2026-01-01T00:00:02")
    conn.close()

    resp = isolated_client.get("/api/timeline?slug=proj-incl&num=8&include_skips=true")
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert len(events) == 2
    skip_event = next(e for e in events if e["type"] == "reconcile_check")
    assert skip_event["payload"]["decision"] == "skip"


def test_timeline_matches_pr_number(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert(conn, "proj-pr", "merge_done", pr_number=55,
            created_at="2026-01-01T00:00:01")
    conn.close()

    resp = isolated_client.get("/api/timeline?slug=proj-pr&num=55")
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert len(events) == 1
    assert events[0]["type"] == "merge_done"


def test_timeline_isolates_by_project(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert(conn, "proj-a", "dev_done", issue_number=10, created_at="2026-01-01T00:00:01")
    _insert(conn, "proj-b", "dev_start", issue_number=10, created_at="2026-01-01T00:00:01")
    conn.close()

    resp = isolated_client.get("/api/timeline?slug=proj-a&num=10")
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert all(e["project"] == "proj-a" for e in events)
    assert len(events) == 1


def test_timeline_issue_contract_with_totals_and_stage(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert(conn, "proj-contract", "dev_start", issue_number=42, created_at="2026-01-01T00:00:00")
    _insert(conn, "proj-contract", "dev_done", issue_number=42, payload={"points": 3}, created_at="2026-01-01T00:10:00")
    _insert(conn, "proj-contract", "dev_start", issue_number=42, created_at="2026-01-01T00:20:00")
    conn.execute(
        """INSERT INTO events (project, role, event_type, issue_number, payload, created_at)
           VALUES (?, 'scanner', 'label_transition', ?, ?, ?)""",
        (
            "proj-contract",
            42,
            json.dumps({"after_labels": ["loop:stage:dev"]}),
            "2026-01-01T00:30:00",
        ),
    )
    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/timeline?project=proj-contract&issue=42")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project"] == "proj-contract"
    assert data["kind"] == "issue"
    assert data["number"] == 42
    assert data["github_url"] == "https://github.com/svv2014/proj-contract/issues/42"
    assert data["stage"] == "loop:stage:dev"
    assert data["totals"]["total_duration_seconds"] == 600
    assert data["totals"]["total_points"] == 3
    assert data["totals"]["rework_count"] == 1
    start = next(e for e in data["events"] if e["event_type"] == "dev_start")
    assert start["duration_seconds"] == 600


def test_timeline_requires_exactly_one_ticket_selector(isolated_client):
    missing = isolated_client.get("/api/timeline?project=proj-contract")
    assert missing.status_code == 400

    both = isolated_client.get("/api/timeline?project=proj-contract&issue=1&pr=2")
    assert both.status_code == 400


def test_timeline_pr_contract_and_linked_issue(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert(
        conn,
        "proj-pr-contract",
        "review_done",
        issue_number=13,
        pr_number=99,
        created_at="2026-01-01T00:00:01",
    )
    conn.close()

    resp = isolated_client.get("/api/timeline?project=proj-pr-contract&pr=99")
    assert resp.status_code == 200
    data = resp.json()
    assert data["kind"] == "pr"
    assert data["number"] == 99
    assert data["linked_issue"] == 13
    assert data["linked_pr"] is None
    assert data["github_url"] == "https://github.com/svv2014/proj-pr-contract/pull/99"


def test_timeline_issue_contract_detects_linked_pr(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert(
        conn,
        "proj-link",
        "merge_done",
        issue_number=44,
        pr_number=144,
        created_at="2026-01-01T00:00:01",
    )
    conn.close()

    resp = isolated_client.get("/api/timeline?project=proj-link&issue=44")
    assert resp.status_code == 200
    data = resp.json()
    assert data["linked_pr"] == 144
    assert data["linked_issue"] is None

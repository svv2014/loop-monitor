import sqlite3

from fastapi.testclient import TestClient

import server
import server.db


def _make_client(monkeypatch, tmp_path):
    monkeypatch.setattr(server.db, "DB_PATH", str(tmp_path / "test.db"))
    server.db.apply_pending_migrations()
    return TestClient(server.app)


def _insert_events(db_path: str, events: list) -> None:
    conn = sqlite3.connect(db_path)
    for ev in events:
        conn.execute(
            """
            INSERT INTO events (project, role, event_type, issue_number, pr_number, detail, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ev["project"],
                ev["role"],
                ev["event_type"],
                ev.get("issue_number"),
                ev.get("pr_number"),
                ev.get("detail"),
                ev["created_at"],
            ),
        )
    conn.commit()
    conn.close()


# (a) happy path — events returned and basic fields present
def test_happy_path_issue(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-a", "role": "dev", "event_type": "dev_start",
         "issue_number": 10, "created_at": "2026-04-01T10:00:00+00:00"},
        {"project": "proj-a", "role": "dev", "event_type": "dev_done",
         "issue_number": 10, "created_at": "2026-04-01T10:30:00+00:00"},
    ])
    resp = client.get("/api/timeline?project=proj-a&issue=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project"] == "proj-a"
    assert data["kind"] == "issue"
    assert data["number"] == 10
    assert len(data["events"]) == 2
    assert data["github_url"] == "https://github.com/svv2014/proj-a/issues/10"


# (b) happy path for PR
def test_happy_path_pr(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-b", "role": "review", "event_type": "review_start",
         "pr_number": 55, "created_at": "2026-04-01T11:00:00+00:00"},
    ])
    resp = client.get("/api/timeline?project=proj-b&pr=55")
    assert resp.status_code == 200
    data = resp.json()
    assert data["kind"] == "pr"
    assert data["number"] == 55
    assert data["github_url"] == "https://github.com/svv2014/proj-b/pull/55"


# (c) 400 on missing params (no issue or pr)
def test_missing_params(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    resp = client.get("/api/timeline?project=proj-a")
    assert resp.status_code == 400


# (d) 400 on both params provided
def test_both_params(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    resp = client.get("/api/timeline?project=proj-a&issue=10&pr=20")
    assert resp.status_code == 400


# (e) 200 with empty events when no rows match
def test_empty_events(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    resp = client.get("/api/timeline?project=no-such-project&issue=999")
    assert resp.status_code == 200
    data = resp.json()
    assert data["events"] == []


# (f) duration pairing — start → done computes correct duration_seconds
def test_duration_pairing(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-c", "role": "dev", "event_type": "dev_start",
         "issue_number": 20, "created_at": "2026-04-01T10:00:00+00:00"},
        {"project": "proj-c", "role": "dev", "event_type": "dev_done",
         "issue_number": 20, "created_at": "2026-04-01T10:15:00+00:00"},
    ])
    resp = client.get("/api/timeline?project=proj-c&issue=20")
    assert resp.status_code == 200
    events = resp.json()["events"]
    start_ev = next(e for e in events if e["event_type"] == "dev_start")
    # 15 minutes = 900 seconds
    assert start_ev["duration_seconds"] == 900
    done_ev = next(e for e in events if e["event_type"] == "dev_done")
    assert done_ev["duration_seconds"] is None


# (g) duration pairing — start with no matching done → duration is None
def test_duration_no_done(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-d", "role": "po", "event_type": "po_start",
         "issue_number": 30, "created_at": "2026-04-01T09:00:00+00:00"},
    ])
    resp = client.get("/api/timeline?project=proj-d&issue=30")
    assert resp.status_code == 200
    start_ev = resp.json()["events"][0]
    assert start_ev["duration_seconds"] is None


# (h) linked-PR detection — issue with pr_number in events
def test_linked_pr_detection(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-e", "role": "dev", "event_type": "dev_done",
         "issue_number": 50, "pr_number": 75, "created_at": "2026-04-01T12:00:00+00:00"},
    ])
    resp = client.get("/api/timeline?project=proj-e&issue=50")
    assert resp.status_code == 200
    data = resp.json()
    assert data["linked_pr"] == 75
    assert data["linked_issue"] is None


# (i) linked-issue detection — pr with issue_number in events
def test_linked_issue_detection(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-f", "role": "review", "event_type": "review_done",
         "issue_number": 60, "pr_number": 80, "created_at": "2026-04-01T13:00:00+00:00"},
    ])
    resp = client.get("/api/timeline?project=proj-f&pr=80")
    assert resp.status_code == 200
    data = resp.json()
    assert data["linked_issue"] == 60
    assert data["linked_pr"] is None


# (j) totals — rework_count is correct for multiple starts of same role
def test_rework_count(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-g", "role": "dev", "event_type": "dev_start",
         "issue_number": 70, "created_at": "2026-04-01T10:00:00+00:00"},
        {"project": "proj-g", "role": "dev", "event_type": "dev_done",
         "issue_number": 70, "created_at": "2026-04-01T10:30:00+00:00"},
        {"project": "proj-g", "role": "dev", "event_type": "dev_start",
         "issue_number": 70, "created_at": "2026-04-01T11:00:00+00:00"},
        {"project": "proj-g", "role": "dev", "event_type": "dev_done",
         "issue_number": 70, "created_at": "2026-04-01T11:30:00+00:00"},
    ])
    resp = client.get("/api/timeline?project=proj-g&issue=70")
    assert resp.status_code == 200
    totals = resp.json()["totals"]
    assert totals["rework_count"] == 1  # 2 starts - 1 = 1 rework


# (k) totals — total_duration_seconds sums all paired durations
def test_total_duration(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-h", "role": "po", "event_type": "po_start",
         "issue_number": 80, "created_at": "2026-04-01T10:00:00+00:00"},
        {"project": "proj-h", "role": "po", "event_type": "po_done",
         "issue_number": 80, "created_at": "2026-04-01T10:10:00+00:00"},
        {"project": "proj-h", "role": "dev", "event_type": "dev_start",
         "issue_number": 80, "created_at": "2026-04-01T10:20:00+00:00"},
        {"project": "proj-h", "role": "dev", "event_type": "dev_done",
         "issue_number": 80, "created_at": "2026-04-01T10:50:00+00:00"},
    ])
    resp = client.get("/api/timeline?project=proj-h&issue=80")
    assert resp.status_code == 200
    totals = resp.json()["totals"]
    # po: 600s, dev: 1800s
    assert totals["total_duration_seconds"] == 2400

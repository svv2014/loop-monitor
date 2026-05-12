import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

import server
import server.db
import server.routes.issues_cost as issues_cost_module


def _make_client(monkeypatch, tmp_path, gh_meta_fn=None):
    monkeypatch.setattr(server.db, "DB_PATH", str(tmp_path / "test.db"))
    server.db.apply_pending_migrations()
    issues_cost_module._gh_cache.clear()
    if gh_meta_fn is not None:
        monkeypatch.setattr(issues_cost_module, "_fetch_gh_meta", gh_meta_fn)
    return TestClient(server.app)


def _open_meta(project, issue_number):
    return {"title": f"Issue {issue_number}", "state": "open", "priority": None, "body": "", "merged": False}


def _insert_events(db_path: str, events: list) -> None:
    conn = sqlite3.connect(db_path)
    for ev in events:
        conn.execute(
            "INSERT INTO events (project, role, event_type, issue_number, created_at) VALUES (?,?,?,?,?)",
            (ev["project"], ev["role"], ev["event_type"], ev["issue_number"], ev["created_at"]),
        )
    conn.commit()
    conn.close()


# (a) exactly 5 *_start events, one per role → rework_factor == 1.0, actual_runs == 5
def test_happy_path_issue(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    roles = ["po", "dev", "review", "qa", "merge"]
    ts = "2026-04-01T10:00:00+00:00"
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-a", "role": r, "event_type": f"{r}_start", "issue_number": 10, "created_at": ts}
        for r in roles
    ])
    resp = client.get("/api/issues/cost?since=2026-01-01")
    assert resp.status_code == 200
    row = next((r for r in resp.json() if r["issue_number"] == 10 and r["project"] == "proj-a"), None)
    assert row is not None
    assert row["actual_runs"] == 5
    assert row["rework_factor"] == 1.0


# (b) 10 *_start events (rework loop) → rework_factor == 2.0, actual_runs == 10
def test_rework_issue(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    ts = "2026-04-01T11:00:00+00:00"
    events = []
    for _ in range(2):
        for r in ["po", "dev", "review", "qa", "merge"]:
            events.append({"project": "proj-b", "role": r, "event_type": f"{r}_start",
                           "issue_number": 20, "created_at": ts})
    _insert_events(server.db.DB_PATH, events)
    resp = client.get("/api/issues/cost?since=2026-01-01")
    assert resp.status_code == 200
    row = next((r for r in resp.json() if r["issue_number"] == 20 and r["project"] == "proj-b"), None)
    assert row is not None
    assert row["actual_runs"] == 10
    assert row["rework_factor"] == 2.0


# (c) merged/closed issue → stranded_seconds is None
def test_merged_issue_no_stranded(tmp_path, monkeypatch):
    def _merged_meta(project, issue_number):
        return {"title": "Closed", "state": "closed", "priority": None, "body": "", "merged": True}

    client = _make_client(monkeypatch, tmp_path, _merged_meta)
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-c", "role": "dev", "event_type": "dev_start",
         "issue_number": 30, "created_at": "2026-04-01T09:00:00+00:00"},
    ])
    resp = client.get("/api/issues/cost?since=2026-01-01")
    assert resp.status_code == 200
    row = next((r for r in resp.json() if r["issue_number"] == 30), None)
    assert row is not None
    assert row["stranded_seconds"] is None


# (d) open issue with last event ~1h ago → stranded_seconds ≈ 3600
def test_open_issue_stranded(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-d", "role": "dev", "event_type": "dev_start",
         "issue_number": 40, "created_at": one_hour_ago},
    ])
    resp = client.get("/api/issues/cost?since=2026-01-01")
    assert resp.status_code == 200
    row = next((r for r in resp.json() if r["issue_number"] == 40), None)
    assert row is not None
    assert row["stranded_seconds"] is not None
    assert abs(row["stranded_seconds"] - 3600) < 5


# (e) GH API unavailable → 200 with priority=null, title=""
def test_gh_api_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(server.db, "DB_PATH", str(tmp_path / "test.db"))
    server.db.apply_pending_migrations()
    issues_cost_module._gh_cache.clear()

    import subprocess as subprocess_mod

    def _raise(*args, **kwargs):
        raise OSError("gh not found")

    monkeypatch.setattr(subprocess_mod, "run", _raise)

    client = TestClient(server.app)
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-e", "role": "dev", "event_type": "dev_start",
         "issue_number": 50, "created_at": "2026-04-01T10:00:00+00:00"},
    ])
    resp = client.get("/api/issues/cost?since=2026-01-01")
    assert resp.status_code == 200
    row = next((r for r in resp.json() if r["issue_number"] == 50), None)
    assert row is not None
    assert row["priority"] is None
    assert row["title"] == ""


def test_fetch_gh_meta_uses_project_repo_mapping(monkeypatch):
    issues_cost_module._gh_cache.clear()
    calls = []

    def _run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=(
                '{"title":"Mapped","state":"open","body":"",'
                '"labels":["p1-high"],"pull_request":{"merged_at":null}}'
            ),
            stderr="",
        )

    monkeypatch.setattr(issues_cost_module.subprocess, "run", _run)

    meta = issues_cost_module._fetch_gh_meta("ntc", 198)

    assert calls[0][0][2] == "repos/svv2014/NanoTraderCopilot/issues/198"
    assert meta["title"] == "Mapped"
    assert meta["priority"] == "p1-high"
    assert meta["merged"] is False


def test_fetch_gh_meta_unknown_project_returns_default_without_call(monkeypatch):
    issues_cost_module._gh_cache.clear()

    def _run(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called for unknown projects")

    monkeypatch.setattr(issues_cost_module.subprocess, "run", _run)

    meta = issues_cost_module._fetch_gh_meta("unknown-project", 198)

    assert meta == {"title": "", "state": "unknown", "priority": None, "body": "", "merged": False}


# (f) since filter excludes events older than the cutoff
def test_since_filter(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-f", "role": "dev", "event_type": "dev_start",
         "issue_number": 60, "created_at": "2025-01-01T00:00:00+00:00"},
        {"project": "proj-f", "role": "dev", "event_type": "dev_start",
         "issue_number": 61, "created_at": "2026-05-01T00:00:00+00:00"},
    ])
    resp = client.get("/api/issues/cost?since=2026-04-01&project=proj-f")
    assert resp.status_code == 200
    issue_numbers = [r["issue_number"] for r in resp.json()]
    assert 60 not in issue_numbers
    assert 61 in issue_numbers


# (g) limit + offset paginate correctly
def test_limit_offset(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    ts = "2026-04-15T00:00:00+00:00"
    for i in range(5):
        _insert_events(server.db.DB_PATH, [
            {"project": "proj-g", "role": "dev", "event_type": "dev_start",
             "issue_number": 100 + i, "created_at": ts},
        ])
    all_rows = client.get("/api/issues/cost?since=2026-01-01&project=proj-g&limit=5&offset=0").json()
    assert len(all_rows) == 5

    page1 = client.get("/api/issues/cost?since=2026-01-01&project=proj-g&limit=2&offset=0").json()
    page2 = client.get("/api/issues/cost?since=2026-01-01&project=proj-g&limit=2&offset=2").json()
    assert len(page1) == 2
    assert len(page2) == 2
    assert {r["issue_number"] for r in page1}.isdisjoint({r["issue_number"] for r in page2})

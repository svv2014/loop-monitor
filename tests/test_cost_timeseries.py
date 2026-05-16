import sqlite3
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


def _p1_meta(project, issue_number):
    return {"title": f"Issue {issue_number}", "state": "open", "priority": "p1-high", "body": "", "merged": False}


def _insert_events(db_path: str, events: list) -> None:
    conn = sqlite3.connect(db_path)
    for ev in events:
        conn.execute(
            "INSERT INTO events (project, role, event_type, issue_number, created_at) VALUES (?,?,?,?,?)",
            (ev["project"], ev["role"], ev["event_type"], ev["issue_number"], ev["created_at"]),
        )
    conn.commit()
    conn.close()


def _ts(offset_days: int = 0, hour: int = 12) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=offset_days)
    dt = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


# ── response shape ─────────────────────────────────────────────────────────────

def test_timeseries_response_shape(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    resp = client.get("/api/cost/timeseries")
    assert resp.status_code == 200
    data = resp.json()
    assert "window_days" in data
    assert "buckets" in data
    assert isinstance(data["buckets"], list)


def test_timeseries_default_30_buckets(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    resp = client.get("/api/cost/timeseries")
    assert resp.status_code == 200
    data = resp.json()
    assert data["window_days"] == 30
    assert len(data["buckets"]) == 30


def test_timeseries_days_param(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    resp = client.get("/api/cost/timeseries?days=7")
    assert resp.status_code == 200
    data = resp.json()
    assert data["window_days"] == 7
    assert len(data["buckets"]) == 7


def test_timeseries_bucket_schema(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    resp = client.get("/api/cost/timeseries")
    assert resp.status_code == 200
    for bucket in resp.json()["buckets"]:
        assert "date" in bucket
        assert "total_rework_events" in bucket
        assert "by_stage" in bucket
        stage = bucket["by_stage"]
        assert "po_failed" in stage
        assert "dev_rework" in stage
        assert "qa_fail" in stage
        assert "review_reject" in stage
        assert "top_issues" in bucket
        assert isinstance(bucket["top_issues"], list)


def test_timeseries_empty_db_all_zeros(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    resp = client.get("/api/cost/timeseries")
    assert resp.status_code == 200
    for b in resp.json()["buckets"]:
        assert b["total_rework_events"] == 0
        assert b["top_issues"] == []


# ── stage classification ───────────────────────────────────────────────────────

def test_timeseries_po_failed_counted(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    _insert_events(server.db.DB_PATH, [
        {"project": "p", "role": "po", "event_type": "po_failed",
         "issue_number": 1, "created_at": _ts(0)},
        {"project": "p", "role": "po", "event_type": "po_failed",
         "issue_number": 1, "created_at": _ts(0)},
    ])
    resp = client.get("/api/cost/timeseries?days=1")
    assert resp.status_code == 200
    today_bucket = resp.json()["buckets"][0]
    assert today_bucket["by_stage"]["po_failed"] == 2
    assert today_bucket["total_rework_events"] == 2


def test_timeseries_dev_failed_counted_as_dev_rework(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    _insert_events(server.db.DB_PATH, [
        {"project": "p", "role": "dev", "event_type": "dev_failed",
         "issue_number": 2, "created_at": _ts(0)},
    ])
    resp = client.get("/api/cost/timeseries?days=1")
    assert resp.status_code == 200
    today_bucket = resp.json()["buckets"][0]
    assert today_bucket["by_stage"]["dev_rework"] == 1


def test_timeseries_qa_failed_counted(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    _insert_events(server.db.DB_PATH, [
        {"project": "p", "role": "qa", "event_type": "qa_failed",
         "issue_number": 3, "created_at": _ts(0)},
    ])
    resp = client.get("/api/cost/timeseries?days=1")
    assert resp.status_code == 200
    today_bucket = resp.json()["buckets"][0]
    assert today_bucket["by_stage"]["qa_fail"] == 1


def test_timeseries_review_failed_counted_as_review_reject(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    _insert_events(server.db.DB_PATH, [
        {"project": "p", "role": "review", "event_type": "review_failed",
         "issue_number": 4, "created_at": _ts(0)},
    ])
    resp = client.get("/api/cost/timeseries?days=1")
    assert resp.status_code == 200
    today_bucket = resp.json()["buckets"][0]
    assert today_bucket["by_stage"]["review_reject"] == 1


def test_timeseries_start_events_not_counted(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    _insert_events(server.db.DB_PATH, [
        {"project": "p", "role": "dev", "event_type": "dev_start",
         "issue_number": 5, "created_at": _ts(0)},
        {"project": "p", "role": "qa", "event_type": "qa_start",
         "issue_number": 5, "created_at": _ts(0)},
    ])
    resp = client.get("/api/cost/timeseries?days=1")
    assert resp.status_code == 200
    today_bucket = resp.json()["buckets"][0]
    assert today_bucket["total_rework_events"] == 0


# ── top_issues ─────────────────────────────────────────────────────────────────

def test_timeseries_top_issues_capped_at_3(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    events = []
    for issue_num in range(1, 6):
        for _ in range(issue_num):
            events.append({"project": "p", "role": "po", "event_type": "po_failed",
                           "issue_number": issue_num, "created_at": _ts(0)})
    _insert_events(server.db.DB_PATH, events)
    resp = client.get("/api/cost/timeseries?days=1")
    assert resp.status_code == 200
    today_bucket = resp.json()["buckets"][0]
    assert len(today_bucket["top_issues"]) == 3


def test_timeseries_top_issues_sorted_by_rework_events(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    _insert_events(server.db.DB_PATH, [
        {"project": "p", "role": "qa", "event_type": "qa_failed",
         "issue_number": 10, "created_at": _ts(0)},
        {"project": "p", "role": "qa", "event_type": "qa_failed",
         "issue_number": 10, "created_at": _ts(0)},
        {"project": "p", "role": "qa", "event_type": "qa_failed",
         "issue_number": 20, "created_at": _ts(0)},
    ])
    resp = client.get("/api/cost/timeseries?days=1")
    assert resp.status_code == 200
    today_bucket = resp.json()["buckets"][0]
    top = today_bucket["top_issues"]
    assert len(top) >= 1
    assert top[0]["issue_number"] == 10
    assert top[0]["rework_events"] == 2


# ── filters ────────────────────────────────────────────────────────────────────

def test_timeseries_project_filter(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-a", "role": "po", "event_type": "po_failed",
         "issue_number": 1, "created_at": _ts(0)},
        {"project": "proj-b", "role": "po", "event_type": "po_failed",
         "issue_number": 2, "created_at": _ts(0)},
    ])
    resp = client.get("/api/cost/timeseries?days=1&project=proj-a")
    assert resp.status_code == 200
    today_bucket = resp.json()["buckets"][0]
    assert today_bucket["total_rework_events"] == 1
    assert today_bucket["top_issues"][0]["project"] == "proj-a"


def test_timeseries_priority_filter(tmp_path, monkeypatch):
    call_count = {"n": 0}

    def meta_fn(project, issue_number):
        call_count["n"] += 1
        if issue_number == 1:
            return {"title": "t", "state": "open", "priority": "p1-high", "body": "", "merged": False}
        return {"title": "t", "state": "open", "priority": "p2-medium", "body": "", "merged": False}

    client = _make_client(monkeypatch, tmp_path, meta_fn)
    _insert_events(server.db.DB_PATH, [
        {"project": "p", "role": "po", "event_type": "po_failed",
         "issue_number": 1, "created_at": _ts(0)},
        {"project": "p", "role": "po", "event_type": "po_failed",
         "issue_number": 2, "created_at": _ts(0)},
    ])
    resp = client.get("/api/cost/timeseries?days=1&priority=p1-high")
    assert resp.status_code == 200
    today_bucket = resp.json()["buckets"][0]
    assert today_bucket["total_rework_events"] == 1
    assert today_bucket["top_issues"][0]["issue_number"] == 1


# ── issues/cost day filter ─────────────────────────────────────────────────────

def test_issues_cost_day_filter_returns_rework_issues(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    today = _today()
    _insert_events(server.db.DB_PATH, [
        # Issue 1: dev_start today (non-rework) + po_failed today (rework)
        {"project": "p", "role": "po", "event_type": "po_failed",
         "issue_number": 1, "created_at": _ts(0)},
        # Issue 2: only yesterday
        {"project": "p", "role": "po", "event_type": "po_failed",
         "issue_number": 2, "created_at": _ts(1)},
        # Issue 3: dev_start today but no rework
        {"project": "p", "role": "dev", "event_type": "dev_start",
         "issue_number": 3, "created_at": _ts(0)},
    ])
    resp = client.get(f"/api/issues/cost?day={today}")
    assert resp.status_code == 200
    result = resp.json()
    issue_numbers = {r["issue_number"] for r in result}
    assert 1 in issue_numbers
    assert 2 not in issue_numbers
    assert 3 not in issue_numbers

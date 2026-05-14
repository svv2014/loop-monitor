import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

import server
import server.db
import server.routes.issues_cost as issues_cost_module
from server.routes.issues_cost import _linear_trend_slope, _median


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


def _ts(offset_days: int = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=offset_days)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


# ── _median ───────────────────────────────────────────────────────────────────

def test_median_empty():
    assert _median([]) is None


def test_median_single():
    assert _median([3.0]) == 3.0


def test_median_odd():
    assert _median([3.0, 1.0, 2.0]) == 2.0


def test_median_even():
    assert _median([1.0, 2.0, 3.0, 4.0]) == 2.5


def test_median_rounded_to_4dp():
    result = _median([1.0, 2.0])
    assert result == round(1.5, 4)


# ── _linear_trend_slope ───────────────────────────────────────────────────────

def test_slope_single_value():
    assert _linear_trend_slope([5.0]) == 0.0


def test_slope_flat():
    assert _linear_trend_slope([2.0, 2.0, 2.0, 2.0]) == 0.0


def test_slope_strictly_increasing():
    assert _linear_trend_slope([1.0, 2.0, 3.0, 4.0]) > 0


def test_slope_strictly_decreasing():
    assert _linear_trend_slope([4.0, 3.0, 2.0, 1.0]) < 0


# ── GET /api/cost/trend ───────────────────────────────────────────────────────

def test_trend_response_shape(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    resp = client.get("/api/cost/trend")
    assert resp.status_code == 200
    data = resp.json()
    assert "window_days" in data
    assert "today" in data
    assert "median_rework_factor" in data["today"]
    assert "issue_count" in data["today"]
    assert "vs_7d" in data
    assert "vs_30d" in data
    assert "trend" in data
    assert "buckets" in data
    assert isinstance(data["buckets"], list)


def test_trend_default_30_buckets(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    resp = client.get("/api/cost/trend")
    assert resp.status_code == 200
    data = resp.json()
    assert data["window_days"] == 30
    assert len(data["buckets"]) == 30


def test_trend_days_param(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    resp = client.get("/api/cost/trend?days=7")
    assert resp.status_code == 200
    data = resp.json()
    assert data["window_days"] == 7
    assert len(data["buckets"]) == 7


def test_trend_today_median_computed(tmp_path, monkeypatch):
    """10 _start events for one issue today → rf = 10/5 = 2.0."""
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    events = [
        {"project": "p", "role": "dev", "event_type": "dev_start",
         "issue_number": 1, "created_at": _ts(0)}
        for _ in range(10)
    ]
    _insert_events(server.db.DB_PATH, events)
    resp = client.get("/api/cost/trend")
    assert resp.status_code == 200
    data = resp.json()
    assert data["today"]["median_rework_factor"] == 2.0
    assert data["today"]["issue_count"] == 1


def test_trend_project_filter_isolates(tmp_path, monkeypatch):
    """Only proj-a events counted when project=proj-a."""
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    today = _ts(0)
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-a", "role": "dev", "event_type": "dev_start",
         "issue_number": 10, "created_at": today},
        {"project": "proj-b", "role": "dev", "event_type": "dev_start",
         "issue_number": 20, "created_at": today},
        {"project": "proj-b", "role": "dev", "event_type": "dev_start",
         "issue_number": 20, "created_at": today},
    ])
    resp = client.get("/api/cost/trend?project=proj-a")
    assert resp.status_code == 200
    data = resp.json()
    assert data["today"]["issue_count"] == 1
    assert data["today"]["median_rework_factor"] == round(1 / 5, 4)


def test_trend_field_values(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    resp = client.get("/api/cost/trend")
    assert resp.status_code == 200
    assert resp.json()["trend"] in ("improving", "degrading", "stable")


def test_trend_bucket_schema(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    resp = client.get("/api/cost/trend")
    assert resp.status_code == 200
    for bucket in resp.json()["buckets"]:
        assert "date" in bucket
        assert "median_rework_factor" in bucket
        assert "issue_count" in bucket


def test_trend_empty_db_returns_nulls(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path, _open_meta)
    resp = client.get("/api/cost/trend")
    assert resp.status_code == 200
    data = resp.json()
    assert data["today"]["median_rework_factor"] is None
    assert data["vs_7d"] is None
    assert data["vs_30d"] is None
    assert all(b["median_rework_factor"] is None for b in data["buckets"])

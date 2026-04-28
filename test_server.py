import os
import tempfile
import pytest

# Use a temp file so all get_db() calls share state
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)

import server
server.DB_PATH = _db_path
server.init_db()

from fastapi.testclient import TestClient
from server import app

client = TestClient(app)


def test_report_accepted():
    resp = client.post("/api/report", json={
        "project": "proj-a",
        "role": "builder",
        "model": "claude-3",
        "event_type": "started",
    })
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"


def test_verdict_accepted():
    resp = client.post("/api/verdict", json={
        "project": "proj-a",
        "role": "builder",
        "model": "claude-3",
        "points": 10,
        "reason": "good work",
    })
    assert resp.status_code == 202
    assert resp.json() == {"status": "accepted"}


def test_board_returns_list():
    server._insert_verdict(server.VerdictPayload(
        project="proj-b", role="reviewer", model="gpt-4", points=5, reason="ok"
    ))
    resp = client.get("/api/board")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    entry = next((r for r in data if r["project"] == "proj-b"), None)
    assert entry is not None
    assert entry["total_points"] == 5


def test_feed_returns_list():
    server._insert_event(server.ReportPayload(
        project="proj-c", role="tester", event_type="finished"
    ))
    resp = client.get("/api/feed")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) <= 50


def test_status_returns_list():
    resp = client.get("/api/status")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_board_cumulative_scores():
    server._insert_verdict(server.VerdictPayload(
        project="proj-d", role="planner", model="claude-3", points=8, reason="first"
    ))
    server._insert_verdict(server.VerdictPayload(
        project="proj-d", role="planner", model="claude-3", points=7, reason="second"
    ))
    resp = client.get("/api/board")
    data = resp.json()
    entry = next(r for r in data if r["project"] == "proj-d" and r["role"] == "planner")
    assert entry["total_points"] == 15
    assert entry["verdict_count"] == 2


# ── Fixture-based tests for dashboard and /api/verdicts ──

@pytest.fixture()
def isolated_client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DB_PATH", str(tmp_path / "test.db"))
    with TestClient(server.app) as c:
        yield c


def test_get_root_returns_dashboard_html(isolated_client):
    response = isolated_client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Loop Monitor" in response.text


def test_api_verdicts_empty(isolated_client):
    response = isolated_client.get("/api/verdicts")
    assert response.status_code == 200
    assert response.json() == []


def test_api_verdicts_after_post(isolated_client):
    isolated_client.post("/api/verdict", json={
        "project": "test", "role": "builder", "points": 10, "reason": "good work"
    })
    response = isolated_client.get("/api/verdicts")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["role"] == "builder"
    assert data[0]["points"] == 10
    assert data[0]["reason"] == "good work"


# ── issue_history and pipeline_runs tests ──

def test_history_empty(isolated_client):
    response = isolated_client.get("/api/history/proj-x/42")
    assert response.status_code == 200
    assert response.json() == []


def test_history_after_report_with_issue(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-h", role="builder", event_type="started",
        issue_number=10, pr_number=5, model="claude-3"
    ))
    response = isolated_client.get("/api/history/proj-h/10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["issue_number"] == 10
    assert data[0]["pr_number"] == 5
    assert data[0]["role"] == "builder"


def test_history_no_entry_without_issue_number(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-h2", role="planner", event_type="working"
    ))
    response = isolated_client.get("/api/history/proj-h2/99")
    assert response.status_code == 200
    assert response.json() == []


def test_runs_empty(isolated_client):
    response = isolated_client.get("/api/runs")
    assert response.status_code == 200
    assert response.json() == []


def test_runs_created_after_report(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-r", role="builder", event_type="started", issue_number=20
    ))
    response = isolated_client.get("/api/runs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["issue_number"] == 20
    assert data[0]["project"] == "proj-r"


def test_runs_by_project(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-p1", role="builder", event_type="done", issue_number=1
    ))
    server._insert_event(server.ReportPayload(
        project="proj-p2", role="builder", event_type="done", issue_number=2
    ))
    response = isolated_client.get("/api/runs/proj-p1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["project"] == "proj-p1"


def test_stats_empty(isolated_client):
    response = isolated_client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_runs" in data
    assert data["total_runs"] == 0


def test_stats_with_runs(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-s", role="builder", event_type="done", issue_number=30
    ))
    response = isolated_client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_runs"] >= 1
    assert "avg_duration_seconds" in data
    assert "success_rate" in data
    assert "rework_rate" in data


def test_timeline_pr_fallback_no_pipeline_run(isolated_client):
    isolated_client.post("/api/report", json={
        "project": "proj-pr", "role": "reviewer", "event_type": "started", "pr_num": 42
    })
    response = isolated_client.get("/api/stats/timeline/pr/proj-pr/42")
    assert response.status_code == 200
    data = response.json()
    assert data["pr_number"] == 42
    assert data["project"] == "proj-pr"
    assert data["issue_number"] is None
    assert len(data["events"]) > 0


def test_pipeline_run_not_duplicated(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-nd", role="planner", event_type="started", issue_number=50
    ))
    server._insert_event(server.ReportPayload(
        project="proj-nd", role="builder", event_type="done", issue_number=50, pr_number=99
    ))
    response = isolated_client.get("/api/runs/proj-nd")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["pr_number"] == 99


# ── Version negotiation tests ──

def test_version_v1_0_accepted(isolated_client):
    resp = isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
        "core_version": "0.1.0",
    })
    assert resp.status_code == 202


def test_version_v1_5_accepted_unknown_fields_ignored(isolated_client):
    resp = isolated_client.post("/api/report", json={
        "api": "1.5", "project": "p", "role": "dev", "event_type": "dev_done",
        "future_field": "ignored",
    })
    assert resp.status_code == 202


def test_version_v2_rejected_426(isolated_client):
    resp = isolated_client.post("/api/report", json={
        "api": "2.0", "project": "p", "role": "dev", "event_type": "dev_done",
    })
    assert resp.status_code == 426
    body = resp.json()
    assert body["detail"]["error"] == "version_unsupported"
    assert body["detail"]["supported"] == [f"{server.SUPPORTED_API_MAJOR}.x"]


def test_missing_api_accepted_with_warning(isolated_client, caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="server"):
        resp = isolated_client.post("/api/report", json={
            "project": "p", "role": "dev", "event_type": "dev_done",
        })
    assert resp.status_code == 202
    assert any("no 'api' field" in r.message for r in caplog.records)


def test_feed_role_filter(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-filt", role="dev", event_type="dev_done"
    ))
    server._insert_event(server.ReportPayload(
        project="proj-filt", role="qa", event_type="qa_pass"
    ))
    resp = isolated_client.get("/api/feed?role=dev")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(item["role"] == "dev" for item in data)


def test_feed_role_filter_case_insensitive(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-filt2", role="review", event_type="review_done"
    ))
    resp = isolated_client.get("/api/feed?role=REVIEW")
    assert resp.status_code == 200
    data = resp.json()
    assert any(item["event_type"] == "review_done" for item in data)


def test_feed_status_filter_done(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-sf", role="dev", event_type="dev_done"
    ))
    server._insert_event(server.ReportPayload(
        project="proj-sf", role="dev", event_type="dev_start"
    ))
    resp = isolated_client.get("/api/feed?status=done")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(item["status"] == "done" for item in data)


def test_feed_status_filter_fail(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-sf2", role="dev", event_type="dev_failed"
    ))
    server._insert_event(server.ReportPayload(
        project="proj-sf2", role="qa", event_type="qa_fail"
    ))
    server._insert_event(server.ReportPayload(
        project="proj-sf2", role="dev", event_type="dev_done"
    ))
    resp = isolated_client.get("/api/feed?status=fail")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2
    assert all(item["status"] == "fail" for item in data)


def test_feed_unknown_status_returns_empty(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-unk", role="dev", event_type="dev_done"
    ))
    resp = isolated_client.get("/api/feed?status=nonexistent")
    assert resp.status_code == 200
    assert resp.json() == []


def test_feed_status_field_present(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-fd", role="dev", event_type="dev_done"
    ))
    server._insert_event(server.ReportPayload(
        project="proj-fd", role="qa", event_type="qa_pass"
    ))
    resp = isolated_client.get("/api/feed")
    assert resp.status_code == 200
    data = resp.json()
    assert all("status" in item for item in data)
    done_items = [i for i in data if i["event_type"] == "dev_done"]
    assert done_items and done_items[0]["status"] == "done"
    pass_items = [i for i in data if i["event_type"] == "qa_pass"]
    assert pass_items and pass_items[0]["status"] == "pass"


def test_feed_role_and_status_combined(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-comb", role="qa", event_type="qa_pass"
    ))
    server._insert_event(server.ReportPayload(
        project="proj-comb", role="dev", event_type="dev_pass"
    ))
    resp = isolated_client.get("/api/feed?role=qa&status=pass")
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["role"] == "qa" for item in data)
    assert all(item["status"] == "pass" for item in data)


def test_health_core_version_counts(isolated_client):
    isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
        "core_version": "0.1.0",
    })
    isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
        "core_version": "0.1.0",
    })
    isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
        "core_version": "0.2.0",
    })
    resp = isolated_client.get("/api/health")
    assert resp.status_code == 200
    counts = resp.json()["core_version_counts"]
    assert counts["0.1.0"] == 2
    assert counts["0.2.0"] == 1

import json
import sqlite3

import server
import server.db
import server.helpers.github as gh_helper


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
    monkeypatch.setenv("HANDLER_TIMEOUT_DEV", "200")
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
    monkeypatch.setenv("HANDLER_TIMEOUT_DEV", "3600")
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="in-progress", issue_number=13
    ))
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    assert all(it["number"] != 13 for it in data)


def test_action_queue_sorted_by_age_desc(isolated_client, monkeypatch):
    monkeypatch.setenv("HANDLER_TIMEOUT_DEV", "100")
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


def test_action_queue_per_stage_threshold_dev_override(isolated_client, monkeypatch):
    monkeypatch.setenv("HANDLER_TIMEOUT_DEV", "500")
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="in-progress", issue_number=300
    ))
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        "UPDATE events SET created_at = datetime('now', '-600 seconds') WHERE issue_number = 300"
    )
    conn.commit()
    conn.close()
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    timeout_items = [it for it in data if it["reason"] == "timeout" and it["number"] == 300]
    assert len(timeout_items) == 1
    assert timeout_items[0]["threshold_seconds"] == 500


def test_action_queue_needs_qa_past_threshold(isolated_client, monkeypatch):
    monkeypatch.setenv("HANDLER_TIMEOUT_QA", "60")
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="needs-qa", issue_number=301
    ))
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        "UPDATE events SET created_at = datetime('now', '-120 seconds') WHERE issue_number = 301"
    )
    conn.commit()
    conn.close()
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    timeout_items = [it for it in data if it["reason"] == "timeout" and it["number"] == 301]
    assert len(timeout_items) == 1
    assert timeout_items[0]["stage"] == "needs-qa"
    assert timeout_items[0]["threshold_seconds"] == 60


def test_action_queue_needs_qa_under_threshold_excluded(isolated_client, monkeypatch):
    monkeypatch.setenv("HANDLER_TIMEOUT_QA", "3600")
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="needs-qa", issue_number=302
    ))
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    assert all(it["number"] != 302 for it in data)


def test_action_queue_threshold_seconds_field(isolated_client, monkeypatch):
    monkeypatch.setenv("HANDLER_TIMEOUT_QA", "60")
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="needs-qa", issue_number=303
    ))
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="blocked", issue_number=304
    ))
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        "UPDATE events SET created_at = datetime('now', '-120 seconds') WHERE issue_number = 303"
    )
    conn.commit()
    conn.close()
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    timeout_item = next((it for it in data if it["number"] == 303), None)
    stuck_item = next((it for it in data if it["number"] == 304), None)
    assert timeout_item is not None
    assert timeout_item["reason"] == "timeout"
    assert timeout_item["threshold_seconds"] == 60
    assert stuck_item is not None
    assert stuck_item["reason"] == "stuck_label"
    assert stuck_item["threshold_seconds"] is None


# ---------------------------------------------------------------------------
# Failure context endpoint
# ---------------------------------------------------------------------------

_FAILURE_COMMENT = json.dumps([
    {
        "id": 1,
        "body": (
            "PO failed — see details below.\n"
            "<!-- failure-context -->\n"
            "ModuleNotFoundError: No module named 'boba_orchestrator'\n"
            "model: claude-sonnet-4-6\n"
            "run_id: run-abc-123\n"
            "retry_count: 2\n"
            "log_path: /var/log/loop/boba.log\n"
            "<!-- /failure-context -->"
        ),
        "created_at": "2026-05-02T10:00:00Z",
        "html_url": "https://github.com/svv2014/loop/issues/42#issuecomment-1",
    }
])

_NO_FAILURE_COMMENT = json.dumps([
    {
        "id": 2,
        "body": "Some unrelated comment with no marker.",
        "created_at": "2026-05-02T09:00:00Z",
        "html_url": "https://github.com/svv2014/loop/issues/42#issuecomment-2",
    }
])


def _mock_run_gh_with(stdout: str):
    def _fake(*args: str) -> str:
        return stdout
    return _fake


def test_failure_context_no_marker(isolated_client, monkeypatch):
    """Returns empty payload (excerpt=null) when no failure-context comment exists."""
    gh_helper._cache.clear()
    monkeypatch.setattr(gh_helper, "_run_gh", _mock_run_gh_with(_NO_FAILURE_COMMENT))
    resp = isolated_client.get("/api/action_queue/loop/issue/42/failure")
    assert resp.status_code == 200
    data = resp.json()
    assert data["excerpt"] is None
    assert data["model"] is None
    assert data["run_id"] is None
    assert data["retry_count"] == 0
    assert data["log_path"] is None


def test_failure_context_with_marker(isolated_client, monkeypatch):
    """Parses and returns the failure-context block when present."""
    gh_helper._cache.clear()
    monkeypatch.setattr(gh_helper, "_run_gh", _mock_run_gh_with(_FAILURE_COMMENT))
    resp = isolated_client.get("/api/action_queue/loop/issue/42/failure")
    assert resp.status_code == 200
    data = resp.json()
    assert "ModuleNotFoundError" in (data["excerpt"] or "")
    assert data["model"] == "claude-sonnet-4-6"
    assert data["run_id"] == "run-abc-123"
    assert data["retry_count"] == 2
    assert data["log_path"] == "/var/log/loop/boba.log"
    assert data["timestamp"] == "2026-05-02T10:00:00Z"
    assert data["github_comment_url"] is not None


def test_failure_context_malformed_marker(isolated_client, monkeypatch):
    """Malformed block (no closing tag) returns empty payload without raising."""
    gh_helper._cache.clear()
    bad_comment = json.dumps([{
        "id": 3,
        "body": "<!-- failure-context -->\nno closing tag here",
        "created_at": "2026-05-02T11:00:00Z",
        "html_url": "https://github.com/svv2014/loop/issues/42#issuecomment-3",
    }])
    monkeypatch.setattr(gh_helper, "_run_gh", _mock_run_gh_with(bad_comment))
    resp = isolated_client.get("/api/action_queue/loop/issue/42/failure")
    assert resp.status_code == 200
    assert resp.json()["excerpt"] is None


def test_failure_context_unknown_project(isolated_client):
    """Returns 404 for unknown project slug."""
    resp = isolated_client.get("/api/action_queue/no-such-project/issue/1/failure")
    assert resp.status_code == 404


def test_failure_context_invalid_kind(isolated_client):
    """Returns 400 for invalid kind."""
    resp = isolated_client.get("/api/action_queue/loop/ticket/1/failure")
    assert resp.status_code == 400

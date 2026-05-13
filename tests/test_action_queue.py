import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

import server
import server.db
import server.helpers.github as gh_helper


def test_action_queue_empty(isolated_client):
    resp = isolated_client.get("/api/action_queue")
    assert resp.status_code == 200
    assert resp.json() == []


def test_action_queue_blocked_label(isolated_client):
    # dev_failed infers "blocked" which is in STUCK_STAGES
    server._insert_event(server.ReportPayload(
        project="boba-event", role="dev", event_type="dev_failed", issue_number=42,
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
    # needs-clarification is a STUCK_STAGE — use a valid label_transition payload
    # to surface it (payload schema requires target_kind, number, op, source, labels).
    server._insert_event(server.ReportPayload(
        project="loop", role="loop", event_type="label_transition", issue_number=7,
        payload={
            "target_kind": "issue",
            "number": 7,
            "before_labels": [],
            "after_labels": ["needs-clarification"],
            "op": "add",
            "source": "scanner",
        }
    ))
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    assert any(item["reason"] == "stuck_label" and item["stage"] == "needs-clarification" for item in data)


def test_action_queue_timeout_threshold(isolated_client, monkeypatch):
    monkeypatch.setenv("HANDLER_TIMEOUT_DEV", "200")
    # dev_start infers "in-dev"
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="dev_start", issue_number=11
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
    assert timeout_items[0]["stage"] == "in-dev"
    assert timeout_items[0]["age_seconds"] >= 200


def test_action_queue_in_dev_below_threshold_excluded(isolated_client, monkeypatch):
    monkeypatch.setenv("HANDLER_TIMEOUT_DEV", "3600")
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="dev_start", issue_number=13
    ))
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    assert all(it["number"] != 13 for it in data)


def test_action_queue_sorted_by_age_desc(isolated_client, monkeypatch):
    monkeypatch.setenv("HANDLER_TIMEOUT_DEV", "100")
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="dev_failed", issue_number=200
    ))
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="dev_failed", issue_number=201
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
        project="loop", role="dev", event_type="dev_start", issue_number=300
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
    # review_done infers "needs-qa"
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="review_done", issue_number=301
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
        project="loop", role="dev", event_type="review_done", issue_number=302
    ))
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    assert all(it["number"] != 302 for it in data)


def test_action_queue_threshold_seconds_field(isolated_client, monkeypatch):
    monkeypatch.setenv("HANDLER_TIMEOUT_QA", "60")
    # review_done → needs-qa (timeout), dev_failed → blocked (stuck_label)
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="review_done", issue_number=303
    ))
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="dev_failed", issue_number=304
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


# ── New tests for _infer_stage + updated vocabulary (issue #221) ──────────────


def test_infer_stage_dev_start_timeout(isolated_client, monkeypatch):
    """Ticket whose latest event is (role='dev', event_type='dev_start') older than
    the dev threshold should appear with stage='in-dev' and reason='timeout'."""
    monkeypatch.setenv("HANDLER_TIMEOUT_DEV", "100")
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="dev_start", issue_number=400
    ))
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        "UPDATE events SET created_at = datetime('now', '-200 seconds') WHERE issue_number = 400"
    )
    conn.commit()
    conn.close()
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    items = [it for it in data if it["number"] == 400]
    assert len(items) == 1
    assert items[0]["stage"] == "in-dev"
    assert items[0]["reason"] == "timeout"
    assert items[0]["age_seconds"] >= 100


def test_infer_stage_blocked_stuck_label(isolated_client):
    """Ticket mapping to 'blocked' (via dev_failed) is returned with reason='stuck_label'."""
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="dev_failed", issue_number=401,
        detail="build exploded"
    ))
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    items = [it for it in data if it["number"] == 401]
    assert len(items) == 1
    assert items[0]["stage"] == "blocked"
    assert items[0]["reason"] == "stuck_label"


def test_infer_stage_qa_fail_repeated(isolated_client):
    """Ticket with qa_fail event_type and rework_count >= 3 → reason='qa_fail_repeated'."""
    server._insert_event(server.ReportPayload(
        project="loop", role="qa", event_type="qa_fail", issue_number=402
    ))
    # Patch rework_count in issue_history to 3
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        """
        INSERT INTO issue_history (project, issue_number, role, event_type, rework_count)
        VALUES ('loop', 402, 'qa', 'qa_fail', 3)
        """
    )
    conn.commit()
    conn.close()
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    items = [it for it in data if it["number"] == 402]
    assert len(items) == 1
    assert items[0]["stage"] == "qa-fail"
    assert items[0]["reason"] == "qa_fail_repeated"


def test_infer_stage_dev_done_not_returned(isolated_client):
    """Ticket whose latest event is dev_done should NOT appear in the action queue."""
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="dev_done", issue_number=403
    ))
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    assert all(it["number"] != 403 for it in data)


@pytest.mark.xfail(
    reason="label_transition payload schema not yet finalised — see loop#344",
    strict=False,
)
def test_infer_stage_label_transition(isolated_client, monkeypatch):
    """label_transition event with a known stage in after_labels should surface that stage.

    Marked xfail: payload field naming ('after_labels' vs 'label') is still in flux
    and the full pipeline is not wired (loop#344).
    """
    monkeypatch.setenv("HANDLER_TIMEOUT_DEV", "10")
    server._insert_event(server.ReportPayload(
        project="loop", role="loop", event_type="label_transition", issue_number=404,
        payload={
            "target_kind": "issue",
            "number": 404,
            "before_labels": [],
            "after_labels": ["in-dev"],
            "op": "add",
            "source": "scanner",
        }
    ))
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        "UPDATE events SET created_at = datetime('now', '-60 seconds') WHERE issue_number = 404"
    )
    conn.commit()
    conn.close()
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    items = [it for it in data if it["number"] == 404]
    # Expect stage to be inferred from the label_transition payload
    assert len(items) == 1
    assert items[0]["stage"] == "in-dev"
    assert items[0]["reason"] == "timeout"


# ── Failure-context endpoint ──────────────────────────────────────────────────

_COMMENT_WITH_MARKER = json.dumps({
    "excerpt": "ModuleNotFoundError: No module named 'boba_orchestrator'",
    "model": "claude-opus-4-5",
    "run_id": "run-abc123",
    "retry_count": 2,
    "timestamp": "2026-05-02T14:30:00Z",
    "log_path": "/var/log/loop/boba-orchestrator.log",
})

_GH_COMMENT_BODY = (
    "PO failed 2x.\n"
    "<!-- failure-context -->\n"
    + _COMMENT_WITH_MARKER + "\n"
    "<!-- /failure-context -->\n"
)


def _make_gh_response(comments: list[dict]) -> str:
    return json.dumps(comments)


def test_failure_endpoint_no_comment(isolated_client, monkeypatch):
    """Returns 200 with excerpt=null when no failure-context comment exists."""
    gh_helper._FAILURE_CACHE.clear()

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = _make_gh_response([
        {"body": "Just a regular comment", "url": "https://gh/c/1", "created_at": "2026-05-01T10:00:00Z"},
    ])

    with patch("server.helpers.github.subprocess.run", return_value=mock_result):
        resp = isolated_client.get("/api/action_queue/loop/issue/42/failure")

    assert resp.status_code == 200
    data = resp.json()
    assert data["excerpt"] is None
    assert data["retry_count"] == 0
    assert data["model"] is None


def test_failure_endpoint_with_marker(isolated_client, monkeypatch):
    """Returns parsed payload when a failure-context comment exists."""
    gh_helper._FAILURE_CACHE.clear()

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = _make_gh_response([
        {"body": "some old comment", "url": "https://gh/c/1", "created_at": "2026-05-01T10:00:00Z"},
        {"body": _GH_COMMENT_BODY, "url": "https://gh/c/2", "created_at": "2026-05-02T14:30:00Z"},
    ])

    with patch("server.helpers.github.subprocess.run", return_value=mock_result):
        resp = isolated_client.get("/api/action_queue/loop/issue/42/failure")

    assert resp.status_code == 200
    data = resp.json()
    assert data["excerpt"] == "ModuleNotFoundError: No module named 'boba_orchestrator'"
    assert data["model"] == "claude-opus-4-5"
    assert data["run_id"] == "run-abc123"
    assert data["retry_count"] == 2
    assert data["timestamp"] == "2026-05-02T14:30:00Z"
    assert data["log_path"] == "/var/log/loop/boba-orchestrator.log"
    assert data["github_comment_url"] == "https://gh/c/2"


def test_failure_endpoint_malformed_json_in_marker(isolated_client):
    """Returns excerpt=null when the marker block contains invalid JSON."""
    gh_helper._FAILURE_CACHE.clear()

    bad_body = "<!-- failure-context -->\nnot-valid-json\n<!-- /failure-context -->"
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = _make_gh_response([
        {"body": bad_body, "url": "https://gh/c/3", "created_at": "2026-05-02T15:00:00Z"},
    ])

    with patch("server.helpers.github.subprocess.run", return_value=mock_result):
        resp = isolated_client.get("/api/action_queue/loop/issue/99/failure")

    assert resp.status_code == 200
    assert resp.json()["excerpt"] is None


def test_failure_endpoint_unknown_project(isolated_client):
    """Returns empty payload (no GH call) for an unknown project slug."""
    gh_helper._FAILURE_CACHE.clear()

    with patch("server.helpers.github.subprocess.run") as mock_run:
        resp = isolated_client.get("/api/action_queue/nonexistent-project/issue/1/failure")

    assert resp.status_code == 200
    assert resp.json()["excerpt"] is None
    mock_run.assert_not_called()


def test_failure_endpoint_invalid_kind(isolated_client):
    """Returns 400 for kind values other than 'issue' or 'pr'."""
    resp = isolated_client.get("/api/action_queue/loop/comment/42/failure")
    assert resp.status_code == 400

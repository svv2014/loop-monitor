from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from server.app import app
from server.routes import logs as logs_module

client = TestClient(app)


def _enable(monkeypatch):
    monkeypatch.setenv("LOOPMON_EXPOSE_LOGS", "1")


def _patch_logdir(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LOOP_LOG_DIR", str(tmp_path))


def test_unknown_handler_rejected(monkeypatch, tmp_path):
    _enable(monkeypatch)
    _patch_logdir(monkeypatch, tmp_path)
    resp = client.get("/api/logs", params={"handler": "../etc/passwd"})
    assert resp.status_code == 400


def test_literal_filter_matches(monkeypatch, tmp_path):
    _enable(monkeypatch)
    _patch_logdir(monkeypatch, tmp_path)
    log = tmp_path / "loop-scanner.log"
    log.write_text(
        "[2026-05-02 10:00:00] [scanner] hello pa-scanner\n"
        "[2026-05-02 10:00:01] [scanner] unrelated event\n"
        "[2026-05-02 10:00:02] [scanner] another pa-scanner line\n"
    )
    with patch.object(logs_module, "_fd_bytes_for_handler", return_value=None):
        resp = client.get(
            "/api/logs", params={"handler": "scanner", "filter": "pa-scanner", "tail": "200"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["lines"]) == 2
    assert all("pa-scanner" in line["raw"] for line in body["lines"])
    assert body["lines"][0]["ts"] == "2026-05-02 10:00:00"
    assert body["lines"][0]["handler"] == "scanner"


def test_unmatched_lines_get_null_metadata(monkeypatch, tmp_path):
    _enable(monkeypatch)
    _patch_logdir(monkeypatch, tmp_path)
    log = tmp_path / "loop-scanner.log"
    log.write_text("not a structured line\n")
    with patch.object(logs_module, "_fd_bytes_for_handler", return_value=None):
        resp = client.get("/api/logs", params={"handler": "scanner"})
    body = resp.json()
    assert body["lines"][0]["ts"] is None
    assert body["lines"][0]["handler"] is None
    assert body["lines"][0]["raw"] == "not a structured line"


def test_tail_all_capped_at_5mib(monkeypatch, tmp_path):
    _enable(monkeypatch)
    _patch_logdir(monkeypatch, tmp_path)
    log = tmp_path / "loop-scanner.log"
    chunk = ("[2026-05-02 10:00:00] [scanner] " + "x" * 64 + "\n").encode()
    # Write ~6 MiB worth.
    with open(log, "wb") as fh:
        for _ in range(6 * 1024 * 1024 // len(chunk) + 100):
            fh.write(chunk)
    assert log.stat().st_size > logs_module.MAX_TAIL_BYTES
    with patch.object(logs_module, "_fd_bytes_for_handler", return_value=None):
        resp = client.get("/api/logs", params={"handler": "scanner", "tail": "all"})
    body = resp.json()
    total_bytes = sum(len(line["raw"]) + 1 for line in body["lines"])
    assert total_bytes <= logs_module.MAX_TAIL_BYTES


def test_loopback_gate_blocks_non_loopback(monkeypatch, tmp_path):
    """TestClient default client host is 'testclient' — non-loopback."""
    monkeypatch.delenv("LOOPMON_EXPOSE_LOGS", raising=False)
    _patch_logdir(monkeypatch, tmp_path)
    resp = client.get("/api/logs", params={"handler": "scanner"})
    assert resp.status_code == 403
    assert resp.json() == {"error": "logs disabled"}


def test_loopback_gate_allows_loopback(monkeypatch, tmp_path):
    """Simulate loopback by extending the allow-list to include the TestClient host."""
    monkeypatch.delenv("LOOPMON_EXPOSE_LOGS", raising=False)
    _patch_logdir(monkeypatch, tmp_path)
    (tmp_path / "loop-scanner.log").write_text("hi\n")
    with patch.object(
        logs_module, "LOOPBACK_HOSTS", logs_module.LOOPBACK_HOSTS | {"testclient"}
    ):
        with patch.object(logs_module, "_fd_bytes_for_handler", return_value=None):
            resp = client.get("/api/logs", params={"handler": "scanner"})
    assert resp.status_code == 200


def test_loopback_gate_bypassed_when_exposed(monkeypatch, tmp_path):
    """When LOOPMON_EXPOSE_LOGS is set, non-loopback hosts are allowed."""
    monkeypatch.setenv("LOOPMON_EXPOSE_LOGS", "1")
    _patch_logdir(monkeypatch, tmp_path)
    (tmp_path / "loop-scanner.log").write_text("hi\n")
    with patch.object(logs_module, "_fd_bytes_for_handler", return_value=None):
        resp = client.get("/api/logs", params={"handler": "scanner"})
    assert resp.status_code == 200


def test_orphan_helper_detects_divergence(monkeypatch, tmp_path):
    log = tmp_path / "loop-scanner.log"
    log.write_text("small\n")
    with patch.object(logs_module, "_fd_bytes_for_handler", return_value=8 * 1024 * 1024):
        on_disk, fd_bytes, orphaned = logs_module._orphan_status("scanner", log)
    assert on_disk == log.stat().st_size
    assert fd_bytes == 8 * 1024 * 1024
    assert orphaned is True


def test_orphan_helper_below_threshold(monkeypatch, tmp_path):
    log = tmp_path / "loop-scanner.log"
    log.write_text("x" * 1000)
    with patch.object(logs_module, "_fd_bytes_for_handler", return_value=1000 + 1024):
        on_disk, fd_bytes, orphaned = logs_module._orphan_status("scanner", log)
    assert orphaned is False


def test_orphan_helper_no_fd_info(monkeypatch, tmp_path):
    log = tmp_path / "loop-scanner.log"
    log.write_text("x")
    with patch.object(logs_module, "_fd_bytes_for_handler", return_value=None):
        on_disk, fd_bytes, orphaned = logs_module._orphan_status("scanner", log)
    assert fd_bytes is None
    assert orphaned is False

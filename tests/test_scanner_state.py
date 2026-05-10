from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from server.app import app
from server.routes import scanner_state as ss_module

client = TestClient(app)


def _make_subprocess_mock(stdout="", returncode=0):
    mock_result = MagicMock()
    mock_result.stdout = stdout
    mock_result.returncode = returncode
    return mock_result


class TestEndpointNoFilesNoLog:
    """Endpoint with no retry files and no scanner log returns empty retries + null caps."""

    def test_empty_retries_and_null_caps(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOOP_LOG_DIR", str(tmp_path))
        monkeypatch.setenv("LOOP_RETRIES_DIR", str(tmp_path))
        monkeypatch.setattr(
            "server.routes.scanner_state.subprocess.run",
            lambda *a, **kw: _make_subprocess_mock(stdout="", returncode=1),
        )

        resp = client.get("/api/scanner_state")
        assert resp.status_code == 200
        body = resp.json()

        assert body["retries"] == []
        for role in ss_module.ROLES:
            assert body["stages"][role]["cap"] is None
            assert body["stages"][role]["in_flight"] == 0


class TestEndpointRetryFiles:
    """Endpoint with two valid retry files parses both correctly."""

    def test_two_retry_files(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOOP_LOG_DIR", str(tmp_path))
        monkeypatch.setenv("LOOP_RETRIES_DIR", str(tmp_path))
        monkeypatch.setattr(
            "server.routes.scanner_state.subprocess.run",
            lambda *a, **kw: _make_subprocess_mock(stdout="", returncode=1),
        )

        (tmp_path / "loop-po-retries-loop-monitor-issue-137").write_text("1")
        (tmp_path / "loop-dev-retries-my-project-issue-42").write_text("2")

        resp = client.get("/api/scanner_state")
        assert resp.status_code == 200
        retries = resp.json()["retries"]

        assert len(retries) == 2

        po_row = next(r for r in retries if r["stage"] == "po")
        assert po_row["project"] == "loop-monitor"
        assert po_row["kind"] == "issue"
        assert po_row["number"] == 137
        assert po_row["count"] == 1
        assert po_row["max"] == ss_module.RETRY_MAX

        dev_row = next(r for r in retries if r["stage"] == "dev")
        assert dev_row["project"] == "my-project"
        assert dev_row["kind"] == "issue"
        assert dev_row["number"] == 42
        assert dev_row["count"] == 2


class TestMalformedRetryFilename:
    """Malformed retry filename is silently skipped."""

    def test_malformed_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOOP_LOG_DIR", str(tmp_path))
        monkeypatch.setenv("LOOP_RETRIES_DIR", str(tmp_path))
        monkeypatch.setattr(
            "server.routes.scanner_state.subprocess.run",
            lambda *a, **kw: _make_subprocess_mock(stdout="", returncode=1),
        )

        # Malformed: missing required parts
        (tmp_path / "loop-retries-nope").write_text("1")
        # Missing number
        (tmp_path / "loop-po-retries-project-onlykind").write_text("1")
        # Valid one to confirm parsing still works
        (tmp_path / "loop-qa-retries-some-proj-issue-5").write_text("1")

        resp = client.get("/api/scanner_state")
        assert resp.status_code == 200
        retries = resp.json()["retries"]

        assert len(retries) == 1
        assert retries[0]["stage"] == "qa"


class TestScannerLogCapParsing:
    """Scanner log with max=4 (per-tick emit cap) line yields parsed cap."""

    def test_cap_parsed_from_log(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOOP_LOG_DIR", str(tmp_path))
        monkeypatch.setenv("LOOP_RETRIES_DIR", str(tmp_path))
        monkeypatch.setattr(
            "server.routes.scanner_state.subprocess.run",
            lambda *a, **kw: _make_subprocess_mock(stdout="", returncode=1),
        )

        log = tmp_path / "loop-scanner.log"
        log.write_text(
            "[2026-05-09 10:00:00] [scanner] loop-po-handler max=4 (per-tick emit cap)\n"
            "[2026-05-09 10:00:00] [scanner] loop-dev-handler max=4 (per-tick emit cap)\n"
            "[2026-05-09 10:00:00] [scanner] loop-qa-handler max=4 (per-tick emit cap)\n"
            "[2026-05-09 10:00:00] [scanner] loop-reviewer-handler max=4 (per-tick emit cap)\n"
            "[2026-05-09 10:00:00] [scanner] loop-merge-handler max=4 (per-tick emit cap)\n"
        )

        resp = client.get("/api/scanner_state")
        assert resp.status_code == 200
        stages = resp.json()["stages"]

        for role in ss_module.ROLES:
            assert stages[role]["cap"] == 4


class TestHelperReadCaps:
    """Unit tests for _read_caps helper."""

    def test_missing_log_returns_all_none(self, tmp_path):
        caps = ss_module._read_caps(tmp_path / "nonexistent.log")
        assert all(v is None for v in caps.values())

    def test_partial_roles_in_log(self, tmp_path):
        log = tmp_path / "loop-scanner.log"
        log.write_text(
            "[2026-05-09 10:00:00] [scanner] loop-po-handler max=3 (per-tick emit cap)\n"
        )
        caps = ss_module._read_caps(log)
        assert caps["po"] == 3
        assert caps["dev"] is None


class TestHelperReadRetries:
    """Unit tests for _read_retries helper."""

    def test_unreadable_file_skipped(self, tmp_path):
        f = tmp_path / "loop-po-retries-proj-issue-1"
        f.write_text("not-an-int")
        retries = ss_module._read_retries(tmp_path)
        assert retries == []

    def test_valid_file_parsed(self, tmp_path):
        f = tmp_path / "loop-merge-retries-loop-monitor-issue-99"
        f.write_text("2")
        retries = ss_module._read_retries(tmp_path)
        assert len(retries) == 1
        assert retries[0]["stage"] == "merge"
        assert retries[0]["project"] == "loop-monitor"
        assert retries[0]["number"] == 99
        assert retries[0]["count"] == 2


class TestHelperCountInflight:
    """Unit tests for _count_inflight helper."""

    def test_zero_when_pgrep_exits_1(self, monkeypatch):
        monkeypatch.setattr(
            "server.routes.scanner_state.subprocess.run",
            lambda *a, **kw: _make_subprocess_mock(stdout="", returncode=1),
        )
        assert ss_module._count_inflight("po") == 0

    def test_counts_non_empty_lines(self, monkeypatch):
        monkeypatch.setattr(
            "server.routes.scanner_state.subprocess.run",
            lambda *a, **kw: _make_subprocess_mock(stdout="1234\n5678\n", returncode=0),
        )
        assert ss_module._count_inflight("po") == 2

    def test_subprocess_error_returns_zero(self, monkeypatch):
        import subprocess

        def raise_err(*a, **kw):
            raise subprocess.SubprocessError("boom")

        monkeypatch.setattr("server.routes.scanner_state.subprocess.run", raise_err)
        assert ss_module._count_inflight("dev") == 0

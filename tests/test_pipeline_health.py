import json
import time
from unittest.mock import MagicMock

import pytest

import server.routes.health as health_module


@pytest.fixture(autouse=True)
def reset_cache():
    health_module._pipeline_cache["ts"] = 0.0
    health_module._pipeline_cache["payload"] = None
    yield
    health_module._pipeline_cache["ts"] = 0.0
    health_module._pipeline_cache["payload"] = None


def _make_loop_result(stdout: str = "", stderr: str = "", returncode: int = 0):
    r = MagicMock()
    r.stdout = stdout
    r.stderr = stderr
    r.returncode = returncode
    return r


def _loop_ok_payload():
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return json.dumps({
        "scanner": {"last_tick_iso": now, "interval_seconds": 1800, "detail": "ok"},
        "orchestrator": {"last_tick_iso": now, "interval_seconds": 900, "detail": "ok"},
    })


def test_pipeline_health_returns_three_keys(isolated_client, monkeypatch):
    monkeypatch.setattr(
        "server.routes.health.subprocess.run",
        lambda *a, **kw: _make_loop_result(stdout=_loop_ok_payload()),
    )

    class _FakeResp:
        status = 200
        def read(self): return json.dumps({"queue_depth": 0}).encode()
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr("server.routes.health.urllib.request.urlopen", lambda *a, **kw: _FakeResp())

    resp = isolated_client.get("/api/health/pipeline")
    assert resp.status_code == 200
    data = resp.json()
    assert "scanner" in data
    assert "orchestrator" in data
    assert "event_queue" in data


def test_loop_binary_missing_marks_down(isolated_client, monkeypatch):
    def _raise(*a, **kw):
        raise FileNotFoundError("loop not found")

    monkeypatch.setattr("server.routes.health.subprocess.run", _raise)

    class _FakeResp:
        status = 200
        def read(self): return json.dumps({}).encode()
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr("server.routes.health.urllib.request.urlopen", lambda *a, **kw: _FakeResp())

    resp = isolated_client.get("/api/health/pipeline")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scanner"]["status"] == "down"
    assert data["orchestrator"]["status"] == "down"


def test_cache_returns_same_payload_without_reshelling(isolated_client, monkeypatch):
    call_count = {"n": 0}

    def _patched_run(*a, **kw):
        call_count["n"] += 1
        return _make_loop_result(stdout=_loop_ok_payload())

    monkeypatch.setattr("server.routes.health.subprocess.run", _patched_run)

    class _FakeResp:
        status = 200
        def read(self): return json.dumps({}).encode()
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr("server.routes.health.urllib.request.urlopen", lambda *a, **kw: _FakeResp())

    resp1 = isolated_client.get("/api/health/pipeline")
    resp2 = isolated_client.get("/api/health/pipeline")

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()
    assert call_count["n"] == 1, f"subprocess.run called {call_count['n']} times, expected 1 (cache miss)"

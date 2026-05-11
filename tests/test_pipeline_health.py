import json
from unittest.mock import MagicMock

import server.routes.health as health_module


def _reset_cache():
    health_module._PIPELINE_CACHE["ts"] = 0.0
    health_module._PIPELINE_CACHE["payload"] = None


def test_pipeline_health_returns_three_keys(isolated_client, monkeypatch):
    _reset_cache()

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = json.dumps({
            "scanner": {"last_tick_iso": "2026-01-01T00:00:00+00:00", "interval_seconds": 60, "detail": "ok"},
            "orchestrator": {"last_tick_iso": "2026-01-01T00:00:00+00:00", "interval_seconds": 60, "detail": "ok"},
        })
        result.stderr = ""
        return result

    def fake_urlopen(url, timeout=None):
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status = 200
        resp.read.return_value = json.dumps({"status": "ok", "queue_depth": 0}).encode()
        return resp

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    resp = isolated_client.get("/api/health/pipeline")
    assert resp.status_code == 200
    data = resp.json()
    assert "scanner" in data
    assert "orchestrator" in data
    assert "event_queue" in data
    for key in ("scanner", "orchestrator", "event_queue"):
        sub = data[key]
        assert "status" in sub
        assert sub["status"] in ("ok", "stale", "down")
        assert "last_tick_iso" in sub
        assert "interval_seconds" in sub
        assert "detail" in sub


def test_pipeline_health_loop_binary_missing_marks_down(isolated_client, monkeypatch):
    _reset_cache()

    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("loop not found")

    def fake_urlopen(url, timeout=None):
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status = 200
        resp.read.return_value = json.dumps({"status": "ok"}).encode()
        return resp

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    resp = isolated_client.get("/api/health/pipeline")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scanner"]["status"] == "down"
    assert data["orchestrator"]["status"] == "down"
    assert "loop binary not found" in data["scanner"]["detail"]


def test_pipeline_health_cache_returns_same_payload(isolated_client, monkeypatch):
    _reset_cache()

    call_count = {"n": 0}

    def fake_run(cmd, **kwargs):
        call_count["n"] += 1
        result = MagicMock()
        result.returncode = 0
        result.stdout = json.dumps({
            "scanner": {"last_tick_iso": "2026-01-01T00:00:00+00:00", "interval_seconds": 60, "detail": ""},
            "orchestrator": {"last_tick_iso": "2026-01-01T00:00:00+00:00", "interval_seconds": 60, "detail": ""},
        })
        result.stderr = ""
        return result

    def fake_urlopen(url, timeout=None):
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status = 200
        resp.read.return_value = json.dumps({"status": "ok"}).encode()
        return resp

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    resp1 = isolated_client.get("/api/health/pipeline")
    resp2 = isolated_client.get("/api/health/pipeline")

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()
    assert call_count["n"] == 1, "subprocess.run should only be called once within the 30s cache window"

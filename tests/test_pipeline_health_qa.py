"""QA-driven tests for PR #193 — _subsystem_status boundary cases and event-queue degradation.

Covers gaps not exercised by the PR's own test_pipeline_health.py:
- Direct unit tests of _subsystem_status (ok / stale / down thresholds, invalid input)
- Endpoint returns 'stale' and 'down' when loop reports aged last_tick_iso values
- Event-queue non-200 HTTP response marks event_queue as 'down'
"""
import json
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

import server.routes.health as health_module
from server.routes.health import _subsystem_status


@pytest.fixture(autouse=True)
def reset_cache():
    health_module._pipeline_cache["ts"] = 0.0
    health_module._pipeline_cache["payload"] = None
    yield
    health_module._pipeline_cache["ts"] = 0.0
    health_module._pipeline_cache["payload"] = None


# ---------------------------------------------------------------------------
# Direct unit tests for _subsystem_status
# ---------------------------------------------------------------------------

def test_subsystem_status_none_last_tick_is_down():
    assert _subsystem_status(None, 1800) == "down"


def test_subsystem_status_none_interval_is_down():
    now = datetime.now(timezone.utc).isoformat()
    assert _subsystem_status(now, None) == "down"


def test_subsystem_status_zero_interval_is_down():
    now = datetime.now(timezone.utc).isoformat()
    assert _subsystem_status(now, 0) == "down"


def test_subsystem_status_negative_interval_is_down():
    now = datetime.now(timezone.utc).isoformat()
    assert _subsystem_status(now, -60) == "down"


def test_subsystem_status_invalid_iso_is_down():
    assert _subsystem_status("not-a-date", 1800) == "down"


def test_subsystem_status_fresh_tick_is_ok():
    now = datetime.now(timezone.utc).isoformat()
    assert _subsystem_status(now, 1800) == "ok"


def test_subsystem_status_age_just_under_2x_is_ok():
    interval = 100
    age = interval * 2 - 1
    old = datetime.fromtimestamp(time.time() - age, tz=timezone.utc).isoformat()
    assert _subsystem_status(old, interval) == "ok"


def test_subsystem_status_age_just_over_2x_is_stale():
    interval = 100
    age = interval * 2 + 1
    old = datetime.fromtimestamp(time.time() - age, tz=timezone.utc).isoformat()
    assert _subsystem_status(old, interval) == "stale"


def test_subsystem_status_age_just_under_4x_is_stale():
    interval = 100
    age = interval * 4 - 1
    old = datetime.fromtimestamp(time.time() - age, tz=timezone.utc).isoformat()
    assert _subsystem_status(old, interval) == "stale"


def test_subsystem_status_age_just_over_4x_is_down():
    interval = 100
    age = interval * 4 + 1
    old = datetime.fromtimestamp(time.time() - age, tz=timezone.utc).isoformat()
    assert _subsystem_status(old, interval) == "down"


def test_subsystem_status_accepts_Z_suffix():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert _subsystem_status(now, 1800) == "ok"


# ---------------------------------------------------------------------------
# Endpoint integration: stale / down status from aged loop ticks
# ---------------------------------------------------------------------------

def _make_loop_result(stdout="", stderr="", returncode=0):
    r = MagicMock()
    r.stdout = stdout
    r.stderr = stderr
    r.returncode = returncode
    return r


class _FakeOkResp:
    status = 200
    def read(self): return json.dumps({}).encode()
    def __enter__(self): return self
    def __exit__(self, *a): pass


def _aged_payload(scanner_age_s: int, orch_age_s: int) -> str:
    scanner_tick = datetime.fromtimestamp(time.time() - scanner_age_s, tz=timezone.utc).isoformat()
    orch_tick = datetime.fromtimestamp(time.time() - orch_age_s, tz=timezone.utc).isoformat()
    return json.dumps({
        "scanner":      {"last_tick_iso": scanner_tick, "interval_seconds": 1800, "detail": ""},
        "orchestrator": {"last_tick_iso": orch_tick,    "interval_seconds": 900,  "detail": ""},
    })


def test_endpoint_returns_stale_when_scanner_tick_is_old(isolated_client, monkeypatch):
    # age = 2×interval + 60 → stale; within 4×interval so not down
    scanner_age = 1800 * 2 + 60
    orch_age = 10
    monkeypatch.setattr(
        "server.routes.health.subprocess.run",
        lambda *a, **kw: _make_loop_result(stdout=_aged_payload(scanner_age, orch_age)),
    )
    monkeypatch.setattr("server.routes.health.urllib.request.urlopen", lambda *a, **kw: _FakeOkResp())

    resp = isolated_client.get("/api/health/pipeline")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scanner"]["status"] == "stale"
    assert data["orchestrator"]["status"] == "ok"


def test_endpoint_returns_down_when_scanner_tick_very_old(isolated_client, monkeypatch):
    # age > 4×interval → down
    scanner_age = 1800 * 4 + 60
    orch_age = 10
    monkeypatch.setattr(
        "server.routes.health.subprocess.run",
        lambda *a, **kw: _make_loop_result(stdout=_aged_payload(scanner_age, orch_age)),
    )
    monkeypatch.setattr("server.routes.health.urllib.request.urlopen", lambda *a, **kw: _FakeOkResp())

    resp = isolated_client.get("/api/health/pipeline")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scanner"]["status"] == "down"
    assert data["orchestrator"]["status"] == "ok"


# ---------------------------------------------------------------------------
# Event-queue degradation: non-200 and exception paths
# ---------------------------------------------------------------------------

class _FakeNon200Resp:
    status = 503
    def read(self): return b""
    def __enter__(self): return self
    def __exit__(self, *a): pass


def test_event_queue_non200_marks_down(isolated_client, monkeypatch):
    now = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(
        "server.routes.health.subprocess.run",
        lambda *a, **kw: _make_loop_result(stdout=json.dumps({
            "scanner":      {"last_tick_iso": now, "interval_seconds": 1800, "detail": ""},
            "orchestrator": {"last_tick_iso": now, "interval_seconds": 900,  "detail": ""},
        })),
    )
    monkeypatch.setattr("server.routes.health.urllib.request.urlopen", lambda *a, **kw: _FakeNon200Resp())

    resp = isolated_client.get("/api/health/pipeline")
    assert resp.status_code == 200
    data = resp.json()
    assert data["event_queue"]["status"] == "down"
    assert "503" in data["event_queue"]["detail"]


def test_event_queue_connection_error_marks_down(isolated_client, monkeypatch):
    def _raise(*a, **kw):
        raise OSError("Connection refused")

    now = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(
        "server.routes.health.subprocess.run",
        lambda *a, **kw: _make_loop_result(stdout=json.dumps({
            "scanner":      {"last_tick_iso": now, "interval_seconds": 1800, "detail": ""},
            "orchestrator": {"last_tick_iso": now, "interval_seconds": 900,  "detail": ""},
        })),
    )
    monkeypatch.setattr("server.routes.health.urllib.request.urlopen", _raise)

    resp = isolated_client.get("/api/health/pipeline")
    assert resp.status_code == 200
    data = resp.json()
    assert data["event_queue"]["status"] == "down"
    assert "Connection refused" in data["event_queue"]["detail"]

from unittest.mock import patch

from fastapi.testclient import TestClient

import server  # noqa: F401
from server.app import app
from server.routes import claude_usage

client = TestClient(app)


def _reset_cache():
    claude_usage._cache["data"] = None
    claude_usage._cache["fetched_at"] = None


def test_disabled_returns_enabled_false(monkeypatch):
    monkeypatch.delenv("CLAUDE_USAGE_ENABLED", raising=False)
    _reset_cache()
    resp = client.get("/api/claude_usage")
    assert resp.status_code == 200
    assert resp.json() == {"enabled": False}


def test_enabled_without_key_returns_error(monkeypatch):
    monkeypatch.setenv("CLAUDE_USAGE_ENABLED", "true")
    monkeypatch.delenv("ANTHROPIC_ADMIN_KEY", raising=False)
    _reset_cache()
    resp = client.get("/api/claude_usage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert "error" in body


def test_enabled_with_key_returns_shaped_payload(monkeypatch):
    monkeypatch.setenv("CLAUDE_USAGE_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_ADMIN_KEY", "sk-test")
    _reset_cache()

    fake_upstream = {
        "quota_used": 250_000,
        "quota_limit": 1_000_000,
        "reset_at": "2026-05-02T00:00:00Z",
        "cache_read_input_tokens": 30_000,
        "input_tokens": 70_000,
    }
    with patch.object(claude_usage, "_fetch_upstream", return_value=fake_upstream):
        resp = client.get("/api/claude_usage")

    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert body["quota_used"] == 250_000
    assert body["quota_limit"] == 1_000_000
    assert body["quota_pct"] == 25.0
    assert body["reset_at"] == "2026-05-02T00:00:00Z"
    assert body["cache_hit_pct"] == 30.0


def test_cache_avoids_second_upstream_call(monkeypatch):
    monkeypatch.setenv("CLAUDE_USAGE_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_ADMIN_KEY", "sk-test")
    _reset_cache()

    fake_upstream = {"quota_used": 1, "quota_limit": 10, "reset_at": "2026-05-02T00:00:00Z"}
    with patch.object(
        claude_usage, "_fetch_upstream", return_value=fake_upstream
    ) as mocked:
        client.get("/api/claude_usage")
        client.get("/api/claude_usage")
        assert mocked.call_count == 1

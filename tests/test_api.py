"""Tests for /api/report version negotiation and /api/health core_version counter."""

import pytest
from fastapi.testclient import TestClient

from server import app, core_version_counts


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _report(client, **kwargs):
    return client.post("/api/report", json={"event": "dev_done", **kwargs})


def test_v1_0_accepted(client):
    resp = _report(client, api="1.0")
    assert resp.status_code == 201
    assert resp.json()["ok"] is True


def test_v1_5_unknown_fields_ignored(client):
    """api=1.5 with extra unknown fields must be accepted (extra='ignore')."""
    resp = _report(client, api="1.5", future_field="whatever", another_unknown=42)
    assert resp.status_code == 201
    assert resp.json()["ok"] is True


def test_v2_0_rejected_426(client):
    resp = _report(client, api="2.0")
    assert resp.status_code == 426
    body = resp.json()
    assert body == {"error": "version_unsupported", "supported": ["1.x"]}


def test_missing_api_warned_and_accepted(client, caplog):
    with caplog.at_level("WARNING", logger="server"):
        resp = _report(client)  # no api field
    assert resp.status_code == 201
    assert resp.json()["ok"] is True
    assert any("Missing 'api'" in r.message for r in caplog.records)


def test_health_exposes_core_version_counts(client):
    core_version_counts.clear()
    _report(client, api="1.0", core_version="0.1.0")
    _report(client, api="1.0", core_version="0.1.0")
    _report(client, api="1.0", core_version="0.2.0")
    resp = client.get("/api/health")
    assert resp.status_code == 200
    counts = resp.json()["core_version_counts"]
    assert counts["0.1.0"] == 2
    assert counts["0.2.0"] == 1

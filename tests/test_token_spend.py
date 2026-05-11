import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

import server
import server.db


def _make_client(monkeypatch, tmp_path):
    monkeypatch.setattr(server.db, "DB_PATH", str(tmp_path / "test.db"))
    server.db.apply_pending_migrations()
    return TestClient(server.app)


def _insert_events(db_path: str, events: list) -> None:
    conn = sqlite3.connect(db_path)
    for ev in events:
        conn.execute(
            "INSERT INTO events (project, role, event_type, created_at) VALUES (?,?,?,?)",
            (ev["project"], ev["role"], ev["event_type"], ev["created_at"]),
        )
    conn.commit()
    conn.close()


def test_empty_db_returns_zero_chart_and_projects(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    resp = client.get("/api/token_spend")
    assert resp.status_code == 200
    body = resp.json()
    assert "chart" in body
    assert "projects" in body
    assert "config" in body
    assert len(body["chart"]) == 7
    assert body["projects"] == []
    for day in body["chart"]:
        assert "date" in day
        assert "label" in day
        for role in ["po", "dev", "qa", "reviewer", "merge", "judge"]:
            assert role in day
            assert day[role] == 0.0


def test_events_appear_in_chart(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    today = datetime.now(timezone.utc).date().isoformat()
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-a", "role": "dev", "event_type": "dev_start", "created_at": f"{today}T10:00:00+00:00"},
        {"project": "proj-a", "role": "dev", "event_type": "dev_start", "created_at": f"{today}T11:00:00+00:00"},
        {"project": "proj-a", "role": "qa",  "event_type": "qa_start",  "created_at": f"{today}T12:00:00+00:00"},
    ])
    resp = client.get("/api/token_spend")
    assert resp.status_code == 200
    body = resp.json()
    today_entry = next(e for e in body["chart"] if e["date"] == today)
    # 2 dev events → cost > 0
    assert today_entry["dev"] > 0
    assert today_entry["dev_events"] == 2
    # 1 qa event
    assert today_entry["qa"] > 0
    assert today_entry["qa_events"] == 1
    # no po events
    assert today_entry["po"] == 0.0


def test_project_totals_in_table(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    old = (now - timedelta(days=15)).date().isoformat()
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-x", "role": "dev", "event_type": "dev_start", "created_at": f"{today}T08:00:00+00:00"},
        {"project": "proj-x", "role": "po",  "event_type": "po_start",  "created_at": f"{old}T08:00:00+00:00"},
    ])
    resp = client.get("/api/token_spend")
    assert resp.status_code == 200
    projects = resp.json()["projects"]
    row = next((p for p in projects if p["project"] == "proj-x"), None)
    assert row is not None
    assert row["today_events"] == 1
    assert row["month_events"] == 2
    assert row["week_events"] == 1
    # month cost > week cost (more events)
    assert row["month_cost_usd"] > row["week_cost_usd"]


def test_config_env_vars_applied(tmp_path, monkeypatch):
    monkeypatch.setenv("TOKEN_COST_PER_1M_INPUT", "6.0")
    monkeypatch.setenv("TOKEN_COST_PER_1M_OUTPUT", "30.0")
    monkeypatch.setenv("TOKEN_EST_INPUT_PER_EVENT", "100000")
    monkeypatch.setenv("TOKEN_EST_OUTPUT_PER_EVENT", "20000")
    client = _make_client(monkeypatch, tmp_path)
    today = datetime.now(timezone.utc).date().isoformat()
    _insert_events(server.db.DB_PATH, [
        {"project": "p", "role": "dev", "event_type": "dev_start", "created_at": f"{today}T10:00:00+00:00"},
    ])
    resp = client.get("/api/token_spend")
    assert resp.status_code == 200
    body = resp.json()
    cfg = body["config"]
    assert cfg["cost_per_1m_input"] == 6.0
    assert cfg["cost_per_1m_output"] == 30.0
    assert cfg["est_input_per_event"] == 100_000
    assert cfg["est_output_per_event"] == 20_000
    # 1 dev event: (100000/1e6)*6 + (20000/1e6)*30 = 0.6 + 0.6 = 1.2
    today_entry = next(e for e in body["chart"] if e["date"] == today)
    assert abs(today_entry["dev"] - 1.2) < 0.001


def test_input_output_tokens_in_chart(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    today = datetime.now(timezone.utc).date().isoformat()
    _insert_events(server.db.DB_PATH, [
        {"project": "p", "role": "po", "event_type": "po_start", "created_at": f"{today}T10:00:00+00:00"},
    ])
    resp = client.get("/api/token_spend")
    assert resp.status_code == 200
    today_entry = next(e for e in resp.json()["chart"] if e["date"] == today)
    assert today_entry["po_input_tokens"] == 50_000
    assert today_entry["po_output_tokens"] == 10_000


def test_input_output_tokens_in_projects(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    today = datetime.now(timezone.utc).date().isoformat()
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-tok", "role": "dev", "event_type": "dev_start", "created_at": f"{today}T10:00:00+00:00"},
        {"project": "proj-tok", "role": "qa",  "event_type": "qa_start",  "created_at": f"{today}T11:00:00+00:00"},
    ])
    resp = client.get("/api/token_spend")
    assert resp.status_code == 200
    row = next(p for p in resp.json()["projects"] if p["project"] == "proj-tok")
    # 2 events today → 2 × 50000 = 100000 input tokens
    assert row["today_input_tokens"] == 100_000
    assert row["today_output_tokens"] == 20_000

import os
import sqlite3

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
            "INSERT INTO events (project, role, event_type, issue_number, created_at) VALUES (?,?,?,?,?)",
            (ev["project"], ev["role"], ev["event_type"], ev["issue_number"], ev["created_at"]),
        )
    conn.commit()
    conn.close()


def test_empty_db_returns_empty_rows(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    resp = client.get("/api/token_spend")
    assert resp.status_code == 200
    data = resp.json()
    assert data["rows"] == []
    assert "config" in data


def test_returns_correct_structure(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-a", "role": "dev", "event_type": "dev_start",
         "issue_number": 1, "created_at": "2026-05-13T10:00:00+00:00"},
    ])
    resp = client.get("/api/token_spend")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["rows"]) == 1
    row = data["rows"][0]
    assert row["role"] == "dev"
    assert row["project"] == "proj-a"
    assert row["event_count"] == 1
    assert "input_tokens" in row
    assert "output_tokens" in row
    assert "cost_usd" in row
    assert "date" in row


def test_token_calculation_defaults(tmp_path, monkeypatch):
    # 1 event, default 5000 tpe, 0.8 input ratio, $3/1M in, $15/1M out
    monkeypatch.delenv("LOOPMON_TOKENS_PER_EVENT", raising=False)
    monkeypatch.delenv("LOOPMON_INPUT_RATIO", raising=False)
    monkeypatch.delenv("LOOPMON_COST_PER_1M_INPUT", raising=False)
    monkeypatch.delenv("LOOPMON_COST_PER_1M_OUTPUT", raising=False)
    client = _make_client(monkeypatch, tmp_path)
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-a", "role": "qa", "event_type": "qa_start",
         "issue_number": 1, "created_at": "2026-05-13T10:00:00+00:00"},
    ])
    resp = client.get("/api/token_spend")
    row = resp.json()["rows"][0]
    assert row["input_tokens"] == 4000   # 5000 * 0.8
    assert row["output_tokens"] == 1000  # 5000 * 0.2
    expected_cost = (4000 / 1_000_000 * 3.0) + (1000 / 1_000_000 * 15.0)
    assert abs(row["cost_usd"] - expected_cost) < 1e-8


def test_configurable_tokens_per_event(tmp_path, monkeypatch):
    monkeypatch.setenv("LOOPMON_TOKENS_PER_EVENT", "10000")
    monkeypatch.delenv("LOOPMON_INPUT_RATIO", raising=False)
    monkeypatch.delenv("LOOPMON_COST_PER_1M_INPUT", raising=False)
    monkeypatch.delenv("LOOPMON_COST_PER_1M_OUTPUT", raising=False)
    client = _make_client(monkeypatch, tmp_path)
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-a", "role": "po", "event_type": "po_start",
         "issue_number": 1, "created_at": "2026-05-13T10:00:00+00:00"},
    ])
    resp = client.get("/api/token_spend")
    row = resp.json()["rows"][0]
    assert row["input_tokens"] == 8000   # 10000 * 0.8
    assert row["output_tokens"] == 2000  # 10000 * 0.2
    cfg = resp.json()["config"]
    assert cfg["tokens_per_event"] == 10000


def test_configurable_cost_env_vars(tmp_path, monkeypatch):
    monkeypatch.delenv("LOOPMON_TOKENS_PER_EVENT", raising=False)
    monkeypatch.delenv("LOOPMON_INPUT_RATIO", raising=False)
    monkeypatch.setenv("LOOPMON_COST_PER_1M_INPUT", "6.0")
    monkeypatch.setenv("LOOPMON_COST_PER_1M_OUTPUT", "30.0")
    client = _make_client(monkeypatch, tmp_path)
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-b", "role": "dev", "event_type": "dev_start",
         "issue_number": 2, "created_at": "2026-05-13T10:00:00+00:00"},
    ])
    resp = client.get("/api/token_spend")
    cfg = resp.json()["config"]
    assert cfg["cost_per_1m_input"] == 6.0
    assert cfg["cost_per_1m_output"] == 30.0
    row = resp.json()["rows"][0]
    expected_cost = (4000 / 1_000_000 * 6.0) + (1000 / 1_000_000 * 30.0)
    assert abs(row["cost_usd"] - expected_cost) < 1e-8


def test_per_role_grouping(tmp_path, monkeypatch):
    monkeypatch.delenv("LOOPMON_TOKENS_PER_EVENT", raising=False)
    client = _make_client(monkeypatch, tmp_path)
    for role in ("po", "dev", "qa"):
        _insert_events(server.db.DB_PATH, [
            {"project": "proj-a", "role": role, "event_type": f"{role}_start",
             "issue_number": 1, "created_at": "2026-05-13T10:00:00+00:00"},
        ])
    resp = client.get("/api/token_spend")
    rows = resp.json()["rows"]
    roles_returned = {r["role"] for r in rows}
    assert {"po", "dev", "qa"} == roles_returned


def test_only_returns_last_30_days(tmp_path, monkeypatch):
    monkeypatch.delenv("LOOPMON_TOKENS_PER_EVENT", raising=False)
    client = _make_client(monkeypatch, tmp_path)
    _insert_events(server.db.DB_PATH, [
        {"project": "proj-a", "role": "dev", "event_type": "dev_start",
         "issue_number": 1, "created_at": "2025-01-01T10:00:00+00:00"},  # old
        {"project": "proj-a", "role": "qa", "event_type": "qa_start",
         "issue_number": 2, "created_at": "2026-05-13T10:00:00+00:00"},  # recent
    ])
    resp = client.get("/api/token_spend")
    rows = resp.json()["rows"]
    assert all(r["date"] >= "2026-04-13" for r in rows)
    roles = {r["role"] for r in rows}
    assert "dev" not in roles  # old event excluded
    assert "qa" in roles

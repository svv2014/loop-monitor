import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

import server
import server.db


def _make_client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setattr(server.db, "DB_PATH", str(tmp_path / "test.db"))
    server.db.apply_pending_migrations()
    return TestClient(server.app)


def _insert_events(db_path: str, events: list) -> None:
    conn = sqlite3.connect(db_path)
    for ev in events:
        conn.execute(
            "INSERT INTO events (project, role, event_type, issue_number, created_at) VALUES (?,?,?,?,?)",
            (ev["project"], ev["role"], ev["event_type"], ev.get("issue_number"), ev["created_at"]),
        )
    conn.commit()
    conn.close()


def _insert_verdicts(db_path: str, verdicts: list) -> None:
    conn = sqlite3.connect(db_path)
    for v in verdicts:
        conn.execute(
            "INSERT INTO verdicts (project, role, points, created_at) VALUES (?,?,?,?)",
            (v["project"], v["role"], v["points"], v["created_at"]),
        )
    conn.commit()
    conn.close()


RECENT = "2026-05-01T12:00:00+00:00"


def test_empty_db_returns_zeros(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    resp = client.get("/api/analytics/quality?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdicts"] == {"clean": 0, "light_rework": 0, "heavy_rework": 0, "blocked": 0}
    assert data["qa_pass_rate"] == 0.0
    assert data["qa_pass_rate_daily"] == []
    assert len(data["stage_failure"]) == 5
    for sf in data["stage_failure"]:
        assert sf["fail_rate"] == 0.0
        assert sf["sample"] == 0
    assert data["rework_dist"]["p50"] == 0.0
    assert data["failure_types"] == {
        "po_failed": 0, "dev_failed": 0, "qa_fail": 0,
        "review_failed": 0, "merge_failed": 0,
    }


def test_verdict_mix_categorisation(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    _insert_verdicts(server.db.DB_PATH, [
        {"project": "p", "role": "judge", "points": 10, "created_at": RECENT},  # clean
        {"project": "p", "role": "judge", "points": 5,  "created_at": RECENT},  # light_rework
        {"project": "p", "role": "judge", "points": 2,  "created_at": RECENT},  # heavy_rework
        {"project": "p", "role": "judge", "points": 0,  "created_at": RECENT},  # blocked
        {"project": "p", "role": "judge", "points": -1, "created_at": RECENT},  # blocked
    ])
    resp = client.get("/api/analytics/quality?days=30")
    assert resp.status_code == 200
    v = resp.json()["verdicts"]
    assert v["clean"] == 1
    assert v["light_rework"] == 1
    assert v["heavy_rework"] == 1
    assert v["blocked"] == 2


def test_qa_pass_rate(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    _insert_events(server.db.DB_PATH, [
        {"project": "p", "role": "qa", "event_type": "qa_start",  "issue_number": 1, "created_at": RECENT},
        {"project": "p", "role": "qa", "event_type": "qa_start",  "issue_number": 2, "created_at": RECENT},
        {"project": "p", "role": "qa", "event_type": "qa_start",  "issue_number": 3, "created_at": RECENT},
        {"project": "p", "role": "qa", "event_type": "qa_start",  "issue_number": 4, "created_at": RECENT},
        {"project": "p", "role": "qa", "event_type": "qa_failed", "issue_number": 1, "created_at": RECENT},
    ])
    resp = client.get("/api/analytics/quality?days=30")
    assert resp.status_code == 200
    data = resp.json()
    # 1 fail out of 4 starts → 75% pass rate
    assert abs(data["qa_pass_rate"] - 0.75) < 0.001


def test_stage_failure_rate(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    _insert_events(server.db.DB_PATH, [
        {"project": "p", "role": "dev", "event_type": "dev_start",  "issue_number": 1, "created_at": RECENT},
        {"project": "p", "role": "dev", "event_type": "dev_start",  "issue_number": 2, "created_at": RECENT},
        {"project": "p", "role": "dev", "event_type": "dev_failed", "issue_number": 1, "created_at": RECENT},
    ])
    resp = client.get("/api/analytics/quality?days=30")
    assert resp.status_code == 200
    sf = {s["stage"]: s for s in resp.json()["stage_failure"]}
    assert sf["dev"]["sample"] == 2
    assert abs(sf["dev"]["fail_rate"] - 0.5) < 0.001
    assert sf["po"]["sample"] == 0
    assert sf["po"]["fail_rate"] == 0.0


def test_rework_dist_percentiles(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    # Insert 4 issues: 5, 10, 15, 20 actual_runs → rework factors 1.0, 2.0, 3.0, 4.0
    # With 4 elements, int(p*(n-1)): p50→idx1=2.0, p75→idx2=3.0, p95→idx2=3.0
    for issue, starts in [(1, 5), (2, 10), (3, 15), (4, 20)]:
        for _ in range(starts):
            _insert_events(server.db.DB_PATH, [
                {"project": "p", "role": "dev", "event_type": "dev_start",
                 "issue_number": issue, "created_at": RECENT},
            ])
    resp = client.get("/api/analytics/quality?days=30")
    assert resp.status_code == 200
    rd = resp.json()["rework_dist"]
    assert rd["p50"] == 2.0
    assert rd["p75"] == 3.0
    assert rd["p95"] == 3.0


def test_failure_types_counts(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    _insert_events(server.db.DB_PATH, [
        {"project": "p", "role": "po",     "event_type": "po_failed",     "issue_number": 1, "created_at": RECENT},
        {"project": "p", "role": "dev",    "event_type": "dev_failed",    "issue_number": 1, "created_at": RECENT},
        {"project": "p", "role": "dev",    "event_type": "dev_failed",    "issue_number": 2, "created_at": RECENT},
        {"project": "p", "role": "qa",     "event_type": "qa_failed",     "issue_number": 1, "created_at": RECENT},
        {"project": "p", "role": "qa",     "event_type": "qa_fail",       "issue_number": 2, "created_at": RECENT},
        {"project": "p", "role": "review", "event_type": "review_failed", "issue_number": 1, "created_at": RECENT},
        {"project": "p", "role": "merge",  "event_type": "merge_failed",  "issue_number": 1, "created_at": RECENT},
    ])
    resp = client.get("/api/analytics/quality?days=30")
    assert resp.status_code == 200
    ft = resp.json()["failure_types"]
    assert ft["po_failed"] == 1
    assert ft["dev_failed"] == 2
    assert ft["qa_fail"] == 2       # qa_failed + qa_fail
    assert ft["review_failed"] == 1
    assert ft["merge_failed"] == 1


def test_days_filter_excludes_old_events(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    old_ts = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    _insert_events(server.db.DB_PATH, [
        {"project": "p", "role": "dev", "event_type": "dev_failed", "issue_number": 1, "created_at": old_ts},
    ])
    _insert_verdicts(server.db.DB_PATH, [
        {"project": "p", "role": "judge", "points": 10, "created_at": old_ts},
    ])
    resp = client.get("/api/analytics/quality?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert data["failure_types"]["dev_failed"] == 0
    assert data["verdicts"]["clean"] == 0


def test_qa_pass_rate_daily_grouping(tmp_path, monkeypatch):
    client = _make_client(monkeypatch, tmp_path)
    day1 = "2026-05-10T10:00:00+00:00"
    day2 = "2026-05-11T10:00:00+00:00"
    _insert_events(server.db.DB_PATH, [
        {"project": "p", "role": "qa", "event_type": "qa_start",  "issue_number": 1, "created_at": day1},
        {"project": "p", "role": "qa", "event_type": "qa_start",  "issue_number": 2, "created_at": day1},
        {"project": "p", "role": "qa", "event_type": "qa_failed", "issue_number": 1, "created_at": day1},
        {"project": "p", "role": "qa", "event_type": "qa_start",  "issue_number": 3, "created_at": day2},
    ])
    resp = client.get("/api/analytics/quality?days=30")
    assert resp.status_code == 200
    daily = {d["date"]: d["rate"] for d in resp.json()["qa_pass_rate_daily"]}
    assert "2026-05-10" in daily
    assert abs(daily["2026-05-10"] - 0.5) < 0.001
    assert "2026-05-11" in daily
    assert abs(daily["2026-05-11"] - 1.0) < 0.001

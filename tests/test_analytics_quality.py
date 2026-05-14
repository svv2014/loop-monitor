import sqlite3

import pytest

import server.db


def _insert_event(conn, project, role, event_type, issue_number=None, created_at="2026-01-10T12:00:00"):
    conn.execute(
        """INSERT INTO events (project, role, event_type, issue_number, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (project, role, event_type, issue_number, created_at),
    )


def test_quality_empty(isolated_client):
    resp = isolated_client.get("/api/analytics/quality?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdicts"] == {"clean": 0, "light_rework": 0, "heavy_rework": 0, "blocked": 0}
    assert data["qa_pass_rate"] is None
    assert data["stage_failure"] == []
    assert data["rework_dist"]["p50"] is None
    assert data["rework_dist"]["buckets"] == [
        {"label": "<=1x", "count": 0},
        {"label": "1-2x", "count": 0},
        {"label": "2-4x", "count": 0},
        {"label": ">4x",  "count": 0},
    ]
    assert data["failure_types"] == {
        "po_failed": 0, "dev_failed": 0, "qa_fail": 0,
        "review_failed": 0, "merge_failed": 0,
    }


def test_quality_failure_types(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.row_factory = sqlite3.Row

    _insert_event(conn, "proj", "po",     "po_failed",     created_at="2026-01-10T10:00:00")
    _insert_event(conn, "proj", "dev",    "dev_failed",    created_at="2026-01-10T10:00:00")
    _insert_event(conn, "proj", "dev",    "dev_failed",    created_at="2026-01-10T10:00:00")
    _insert_event(conn, "proj", "qa",     "qa_failed",     created_at="2026-01-10T10:00:00")
    _insert_event(conn, "proj", "review", "review_failed", created_at="2026-01-10T10:00:00")
    _insert_event(conn, "proj", "merge",  "merge_failed",  created_at="2026-01-10T10:00:00")
    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/analytics/quality?days=365")
    assert resp.status_code == 200
    ft = resp.json()["failure_types"]
    assert ft["po_failed"] == 1
    assert ft["dev_failed"] == 2
    assert ft["qa_fail"] == 1
    assert ft["review_failed"] == 1
    assert ft["merge_failed"] == 1


def test_quality_stage_failure_rate(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.row_factory = sqlite3.Row

    # dev: 4 starts, 2 failures → 50%
    for _ in range(4):
        _insert_event(conn, "proj", "dev", "dev_start", created_at="2026-01-10T10:00:00")
    for _ in range(2):
        _insert_event(conn, "proj", "dev", "dev_failed", created_at="2026-01-10T10:00:00")

    # qa: 5 starts, 1 failure → 20%
    for _ in range(5):
        _insert_event(conn, "proj", "qa", "qa_start", created_at="2026-01-10T10:00:00")
    _insert_event(conn, "proj", "qa", "qa_failed", created_at="2026-01-10T10:00:00")

    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/analytics/quality?days=365")
    assert resp.status_code == 200
    sf = {s["stage"]: s for s in resp.json()["stage_failure"]}

    assert "dev" in sf
    assert sf["dev"]["fail_rate"] == pytest.approx(0.5, rel=0.01)
    assert sf["dev"]["sample"] == 4

    assert "qa" in sf
    assert sf["qa"]["fail_rate"] == pytest.approx(0.2, rel=0.01)
    assert sf["qa"]["sample"] == 5


def test_quality_qa_pass_rate(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.row_factory = sqlite3.Row

    # 3 qa_pass + 1 qa_failed → 75% pass rate
    for _ in range(3):
        _insert_event(conn, "proj", "qa", "qa_pass", created_at="2026-01-10T10:00:00")
    _insert_event(conn, "proj", "qa", "qa_failed", created_at="2026-01-10T10:00:00")

    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/analytics/quality?days=365")
    assert resp.status_code == 200
    data = resp.json()
    assert data["qa_pass_rate"] == pytest.approx(0.75, rel=0.01)


def test_quality_rework_dist_and_verdicts(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.row_factory = sqlite3.Row

    # issue 1: 5 starts → rf = 5/5 = 1.0 → clean (<=1.0)
    for _ in range(5):
        _insert_event(conn, "proj", "dev", "dev_start", issue_number=1, created_at="2026-01-10T10:00:00")

    # issue 2: 8 starts → rf = 8/5 = 1.6 → light_rework (1<rf<=2)
    for _ in range(8):
        _insert_event(conn, "proj", "dev", "dev_start", issue_number=2, created_at="2026-01-10T10:00:00")

    # issue 3: 15 starts → rf = 15/5 = 3.0 → heavy_rework (2<rf<=4)
    for _ in range(15):
        _insert_event(conn, "proj", "dev", "dev_start", issue_number=3, created_at="2026-01-10T10:00:00")

    # issue 4: 25 starts → rf = 25/5 = 5.0 → blocked (>4)
    for _ in range(25):
        _insert_event(conn, "proj", "dev", "dev_start", issue_number=4, created_at="2026-01-10T10:00:00")

    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/analytics/quality?days=365")
    assert resp.status_code == 200
    data = resp.json()

    assert data["verdicts"]["clean"] == 1
    assert data["verdicts"]["light_rework"] == 1
    assert data["verdicts"]["heavy_rework"] == 1
    assert data["verdicts"]["blocked"] == 1

    rd = data["rework_dist"]
    assert rd["p50"] is not None
    assert rd["p75"] is not None
    assert rd["p95"] is not None
    assert len(rd["buckets"]) == 4
    assert rd["buckets"][0]["label"] == "<=1x"
    assert rd["buckets"][0]["count"] == 1
    assert rd["buckets"][3]["label"] == ">4x"
    assert rd["buckets"][3]["count"] == 1


def test_quality_days_filter(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.row_factory = sqlite3.Row

    # Old events (>60 days) — should be excluded
    _insert_event(conn, "proj", "qa", "qa_failed", created_at="2024-01-01T00:00:00")
    _insert_event(conn, "proj", "qa", "qa_pass",   created_at="2024-01-01T00:00:00")

    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/analytics/quality?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert data["qa_pass_rate"] is None
    assert data["failure_types"]["qa_fail"] == 0


def test_quality_qa_pass_rate_daily_shape(isolated_client):
    resp = isolated_client.get("/api/analytics/quality?days=7")
    assert resp.status_code == 200
    daily = resp.json()["qa_pass_rate_daily"]
    assert len(daily) == 7
    for entry in daily:
        assert "date" in entry
        assert "rate" in entry

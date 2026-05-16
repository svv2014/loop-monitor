import sqlite3
from datetime import datetime, timedelta, timezone

import server.db


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hours_ago_iso(hours: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def _insert_event(
    conn: sqlite3.Connection,
    project: str,
    event_type: str,
    issue_number: int | None,
    created_at: str | None = None,
):
    conn.execute(
        """
        INSERT INTO events (project, role, event_type, issue_number, created_at)
        VALUES (?, 'dev', ?, ?, ?)
        """,
        (project, event_type, issue_number, created_at or _now_iso()),
    )
    conn.commit()


def test_anomalies_no_events_returns_empty(isolated_client):
    resp = isolated_client.get("/api/anomalies?project=loop&window_hours=24&threshold=2")

    assert resp.status_code == 200
    assert resp.json() == []


def test_anomalies_returns_issue_over_threshold(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert_event(conn, "loop", "label_transition", 42)
    _insert_event(conn, "loop", "label_transition", 42)
    _insert_event(conn, "loop", "reconcile_check", 42)
    conn.close()

    resp = isolated_client.get("/api/anomalies?project=loop&window_hours=24&threshold=2")

    assert resp.status_code == 200
    assert resp.json() == [{"issue_number": 42, "touches": 3}]


def test_anomalies_excludes_issue_below_threshold(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert_event(conn, "loop", "label_transition", 42)
    conn.close()

    resp = isolated_client.get("/api/anomalies?project=loop&window_hours=24&threshold=2")

    assert resp.status_code == 200
    assert resp.json() == []


def test_anomalies_excludes_events_outside_window(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert_event(conn, "loop", "label_transition", 42, created_at=_hours_ago_iso(48))
    _insert_event(conn, "loop", "reconcile_check", 42, created_at=_hours_ago_iso(48))
    conn.close()

    resp = isolated_client.get("/api/anomalies?project=loop&window_hours=24&threshold=2")

    assert resp.status_code == 200
    assert resp.json() == []


def test_anomalies_ignores_other_event_types(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert_event(conn, "loop", "dev_start", 42)
    _insert_event(conn, "loop", "dev_done", 42)
    conn.close()

    resp = isolated_client.get("/api/anomalies?project=loop&window_hours=24&threshold=2")

    assert resp.status_code == 200
    assert resp.json() == []


def test_anomalies_ignores_events_without_issue_number(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert_event(conn, "loop", "label_transition", None)
    _insert_event(conn, "loop", "reconcile_check", None)
    conn.close()

    resp = isolated_client.get("/api/anomalies?project=loop&window_hours=24&threshold=2")

    assert resp.status_code == 200
    assert resp.json() == []


def test_anomalies_unknown_project_returns_empty(isolated_client):
    resp = isolated_client.get("/api/anomalies?project=unknown&window_hours=24&threshold=1")

    assert resp.status_code == 200
    assert resp.json() == []


def test_anomalies_sorts_by_touches_desc(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert_event(conn, "loop", "label_transition", 2)
    _insert_event(conn, "loop", "reconcile_check", 2)
    _insert_event(conn, "loop", "label_transition", 1)
    _insert_event(conn, "loop", "reconcile_check", 1)
    _insert_event(conn, "loop", "label_transition", 1)
    conn.close()

    resp = isolated_client.get("/api/anomalies?project=loop&window_hours=24&threshold=2")

    assert resp.status_code == 200
    assert resp.json() == [
        {"issue_number": 1, "touches": 3},
        {"issue_number": 2, "touches": 2},
    ]


def test_anomalies_missing_params_return_400(isolated_client):
    for path in (
        "/api/anomalies",
        "/api/anomalies?window_hours=24&threshold=2",
        "/api/anomalies?project=loop&threshold=2",
        "/api/anomalies?project=loop&window_hours=24",
    ):
        resp = isolated_client.get(path)
        assert resp.status_code == 400


def test_anomalies_invalid_numeric_params_return_400(isolated_client):
    for path in (
        "/api/anomalies?project=loop&window_hours=abc&threshold=2",
        "/api/anomalies?project=loop&window_hours=24&threshold=abc",
        "/api/anomalies?project=loop&window_hours=0&threshold=2",
        "/api/anomalies?project=loop&window_hours=24&threshold=0",
    ):
        resp = isolated_client.get(path)
        assert resp.status_code == 400

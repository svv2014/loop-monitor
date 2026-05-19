import sqlite3
from datetime import datetime, timedelta, timezone

import server.db


def _ts(hours_ago: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def _insert_event(
    conn: sqlite3.Connection,
    project: str,
    event_type: str,
    issue_number: int | None,
    created_at: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO events (project, role, event_type, issue_number, created_at)
        VALUES (?, 'scanner', ?, ?, ?)
        """,
        (project, event_type, issue_number, created_at or _ts()),
    )
    conn.commit()


def test_anomalies_empty_for_unknown_project(isolated_client):
    response = isolated_client.get("/api/anomalies?project=unknown&window_hours=1&threshold=2")

    assert response.status_code == 200
    assert response.json() == []


def test_anomalies_returns_issue_over_threshold(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert_event(conn, "proj", "label_transition", 42)
    _insert_event(conn, "proj", "reconcile_check", 42)
    _insert_event(conn, "proj", "label_transition", 42)
    conn.close()

    response = isolated_client.get("/api/anomalies?project=proj&window_hours=1&threshold=3")

    assert response.status_code == 200
    assert response.json() == [{"issue_number": 42, "touches": 3}]


def test_anomalies_excludes_issue_below_threshold(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert_event(conn, "proj", "label_transition", 41)
    _insert_event(conn, "proj", "reconcile_check", 41)
    conn.close()

    response = isolated_client.get("/api/anomalies?project=proj&window_hours=1&threshold=3")

    assert response.status_code == 200
    assert response.json() == []


def test_anomalies_excludes_events_outside_window(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert_event(conn, "proj", "label_transition", 7, _ts(hours_ago=3))
    _insert_event(conn, "proj", "reconcile_check", 7, _ts(hours_ago=3))
    conn.close()

    response = isolated_client.get("/api/anomalies?project=proj&window_hours=1&threshold=2")

    assert response.status_code == 200
    assert response.json() == []


def test_anomalies_ignores_other_event_types(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    _insert_event(conn, "proj", "dev_start", 99)
    _insert_event(conn, "proj", "dev_done", 99)
    _insert_event(conn, "proj", "qa_fail", 99)
    conn.close()

    response = isolated_client.get("/api/anomalies?project=proj&window_hours=1&threshold=2")

    assert response.status_code == 200
    assert response.json() == []


def test_anomalies_ignores_pr_only_rows(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        """
        INSERT INTO events (project, role, event_type, pr_number, created_at)
        VALUES ('proj', 'scanner', 'label_transition', 10, ?)
        """,
        (_ts(),),
    )
    conn.execute(
        """
        INSERT INTO events (project, role, event_type, pr_number, created_at)
        VALUES ('proj', 'scanner', 'reconcile_check', 10, ?)
        """,
        (_ts(),),
    )
    conn.commit()
    conn.close()

    response = isolated_client.get("/api/anomalies?project=proj&window_hours=1&threshold=2")

    assert response.status_code == 200
    assert response.json() == []


def test_anomalies_returns_400_for_missing_or_invalid_params(isolated_client):
    assert isolated_client.get("/api/anomalies").status_code == 400
    assert isolated_client.get("/api/anomalies?project=proj&threshold=2").status_code == 400
    assert isolated_client.get("/api/anomalies?project=proj&window_hours=1").status_code == 400
    assert isolated_client.get("/api/anomalies?project=proj&window_hours=nope&threshold=2").status_code == 400
    assert isolated_client.get("/api/anomalies?project=proj&window_hours=1&threshold=nope").status_code == 400

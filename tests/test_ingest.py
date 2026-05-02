import logging
import sqlite3

import server
import server.db


def test_report_accepted(shared_client):
    resp = shared_client.post("/api/report", json={
        "project": "proj-a",
        "role": "builder",
        "model": "claude-3",
        "event_type": "started",
    })
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"
    assert "monitor_version" in resp.json()


def test_verdict_accepted(shared_client):
    resp = shared_client.post("/api/verdict", json={
        "project": "proj-a",
        "role": "builder",
        "model": "claude-3",
        "points": 10,
        "reason": "good work",
    })
    assert resp.status_code == 202
    assert resp.json() == {"status": "accepted"}


def test_version_v1_0_accepted(isolated_client):
    resp = isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
        "core_version": "0.1.0",
    })
    assert resp.status_code == 202


def test_version_v1_5_accepted_unknown_fields_ignored(isolated_client):
    resp = isolated_client.post("/api/report", json={
        "api": "1.5", "project": "p", "role": "dev", "event_type": "dev_done",
        "future_field": "ignored",
    })
    assert resp.status_code == 202


def test_version_v2_rejected_426(isolated_client):
    resp = isolated_client.post("/api/report", json={
        "api": "2.0", "project": "p", "role": "dev", "event_type": "dev_done",
    })
    assert resp.status_code == 426
    body = resp.json()
    assert body["detail"]["error"] == "version_unsupported"
    assert body["detail"]["supported"] == [f"{server.SUPPORTED_API_MAJOR}.x"]


def test_missing_api_accepted_with_warning(isolated_client, caplog):
    with caplog.at_level(logging.WARNING, logger="server"):
        resp = isolated_client.post("/api/report", json={
            "project": "p", "role": "dev", "event_type": "dev_done",
        })
    assert resp.status_code == 202
    assert any("no 'api' field" in r.message for r in caplog.records)


def test_loop_id_persisted(isolated_client):
    import time
    isolated_client.post("/api/report", json={
        "project": "proj-li", "role": "dev", "event_type": "dev_start",
        "loop_id": "my-loop",
    })
    time.sleep(0.05)  # background task
    conn = sqlite3.connect(server.db.DB_PATH)
    row = conn.execute(
        "SELECT loop_id FROM events WHERE project='proj-li' AND loop_id='my-loop'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "my-loop"


def test_loop_id_null_when_absent(isolated_client):
    import time
    isolated_client.post("/api/report", json={
        "project": "proj-li2", "role": "dev", "event_type": "dev_start",
    })
    time.sleep(0.05)  # background task
    conn = sqlite3.connect(server.db.DB_PATH)
    row = conn.execute(
        "SELECT loop_id FROM events WHERE project='proj-li2'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] is None


def test_concurrent_reports_both_persisted(shared_client):
    """Concurrent POST /api/report writes must both persist (WAL + busy_timeout)."""
    import threading

    project = "proj-concurrent"
    results: list[int] = []
    lock = threading.Lock()

    def fire(role: str):
        resp = shared_client.post("/api/report", json={
            "project": project,
            "role": role,
            "model": "claude-3",
            "event_type": "started",
        })
        with lock:
            results.append(resp.status_code)

    t1 = threading.Thread(target=fire, args=("builder",))
    t2 = threading.Thread(target=fire, args=("reviewer",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert sorted(results) == [202, 202]
    feed = shared_client.get("/api/feed").json()
    roles = {e["role"] for e in feed if e["project"] == project}
    assert {"builder", "reviewer"}.issubset(roles)

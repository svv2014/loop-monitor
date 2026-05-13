import sqlite3

import server
import server.db


def test_feed_returns_list(shared_client):
    server._insert_event(server.ReportPayload(
        project="proj-c", role="tester", event_type="finished"
    ))
    resp = shared_client.get("/api/feed")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) <= 50


def test_feed_age_seconds(isolated_client):
    """Each feed item includes age_seconds computed server-side."""
    isolated_client.post("/api/report", json={
        "project": "proj-age", "role": "builder", "event_type": "started",
    })
    resp = isolated_client.get("/api/feed")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    item = next((i for i in data if i["project"] == "proj-age"), None)
    assert item is not None
    assert "age_seconds" in item
    assert isinstance(item["age_seconds"], int)
    assert item["age_seconds"] >= 0


def test_feed_loop_id_filter(isolated_client):
    now = "2026-01-01T00:00:00+00:00"
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.executemany(
        "INSERT INTO events (project, role, event_type, created_at, loop_id) VALUES (?, ?, ?, ?, ?)",
        [
            ("p", "dev", "ev_x", now, "loop-x"),
            ("p", "dev", "ev_y", now, "loop-y"),
            ("p", "dev", "ev_none", now, None),
        ],
    )
    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/feed?loop_id=loop-x")
    assert resp.status_code == 200
    data = resp.json()
    proj_events = [r["event_type"] for r in data if r["project"] == "p"]
    assert proj_events == ["ev_x"]

    resp_all = isolated_client.get("/api/feed")
    assert resp_all.status_code == 200
    all_types = {r["event_type"] for r in resp_all.json() if r["project"] == "p"}
    assert {"ev_x", "ev_y", "ev_none"}.issubset(all_types)


def test_feed_role_filter(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-rf", role="dev", event_type="dev_done"
    ))
    server._insert_event(server.ReportPayload(
        project="proj-rf", role="qa", event_type="qa_pass"
    ))
    resp = isolated_client.get("/api/feed?role=dev")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(item["role"] == "dev" for item in data)


def test_feed_role_filter_case_insensitive(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-rf2", role="review", event_type="review_done"
    ))
    resp = isolated_client.get("/api/feed?role=REVIEW")
    assert resp.status_code == 200
    data = resp.json()
    assert any(item["event_type"] == "review_done" for item in data)


def test_feed_status_filter_done(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-sf", role="dev", event_type="dev_done"
    ))
    server._insert_event(server.ReportPayload(
        project="proj-sf", role="dev", event_type="dev_start"
    ))
    resp = isolated_client.get("/api/feed?status=done")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(item["status"] == "done" for item in data)


def test_feed_status_filter_fail_covers_failed(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-sf2", role="dev", event_type="dev_failed"
    ))
    server._insert_event(server.ReportPayload(
        project="proj-sf2", role="qa", event_type="qa_fail"
    ))
    server._insert_event(server.ReportPayload(
        project="proj-sf2", role="dev", event_type="dev_done"
    ))
    resp = isolated_client.get("/api/feed?status=fail")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2
    assert all(item["status"] == "fail" for item in data)


def test_feed_unknown_status_returns_empty(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-unk", role="dev", event_type="dev_done"
    ))
    resp = isolated_client.get("/api/feed?status=nonexistent")
    assert resp.status_code == 200
    assert resp.json() == []


def test_feed_status_field_derived(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-fd", role="dev", event_type="dev_done"
    ))
    server._insert_event(server.ReportPayload(
        project="proj-fd", role="qa", event_type="qa_pass"
    ))
    resp = isolated_client.get("/api/feed")
    assert resp.status_code == 200
    data = resp.json()
    assert all("status" in item for item in data)
    done_items = [i for i in data if i["event_type"] == "dev_done"]
    assert done_items and done_items[0]["status"] == "done"
    pass_items = [i for i in data if i["event_type"] == "qa_pass"]
    assert pass_items and pass_items[0]["status"] == "pass"


def test_feed_role_and_status_combined(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-comb", role="qa", event_type="qa_pass"
    ))
    server._insert_event(server.ReportPayload(
        project="proj-comb", role="dev", event_type="dev_pass"
    ))
    resp = isolated_client.get("/api/feed?role=qa&status=pass")
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["role"] == "qa" for item in data)
    assert all(item["status"] == "pass" for item in data)


def test_feed_role_filter_preserves_loop_id(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-loop", role="dev", event_type="dev_done", loop_id="loop-1"
    ))
    server._insert_event(server.ReportPayload(
        project="proj-loop", role="qa", event_type="qa_pass", loop_id="loop-1"
    ))
    resp = isolated_client.get("/api/feed?loop_id=loop-1&role=dev")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(item["role"] == "dev" for item in data)


def test_feed_remaps_legacy_judge_rows_and_filters_as_done(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        """INSERT INTO events
           (project, role, event_type, issue_number, created_at)
           VALUES (?, ?, ?, ?, datetime('now'))""",
        ("proj-judge", "dev", "judge", 213),
    )
    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/feed?role=judge&status=done")
    assert resp.status_code == 200
    item = next((i for i in resp.json() if i["project"] == "proj-judge"), None)

    assert item is not None
    assert item["role"] == "judge"
    assert item["event_type"] == "judge_done"
    assert item["status"] == "done"


def test_history_includes_legacy_judge_rows_with_null_duration(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        """INSERT INTO events
           (project, role, event_type, issue_number, created_at)
           VALUES (?, ?, ?, ?, datetime('now'))""",
        ("proj-history-judge", "dev", "judge", 213),
    )
    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/history")
    assert resp.status_code == 200
    item = next((i for i in resp.json() if i["project"] == "proj-history-judge"), None)

    assert item is not None
    assert item["role"] == "judge"
    assert item["event_type"] == "judge_done"
    assert item["duration_seconds"] is None

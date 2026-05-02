import os
import tempfile

import pytest

# Use a temp file so all get_db() calls share state
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)

import server  # noqa: E402
import server.db  # noqa: E402

server.db.DB_PATH = _db_path
server.apply_pending_migrations()

from fastapi.testclient import TestClient  # noqa: E402,I001
from server import app  # noqa: E402,I001

client = TestClient(app)


def test_report_accepted():
    resp = client.post("/api/report", json={
        "project": "proj-a",
        "role": "builder",
        "model": "claude-3",
        "event_type": "started",
    })
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"
    assert "monitor_version" in resp.json()


def test_verdict_accepted():
    resp = client.post("/api/verdict", json={
        "project": "proj-a",
        "role": "builder",
        "model": "claude-3",
        "points": 10,
        "reason": "good work",
    })
    assert resp.status_code == 202
    assert resp.json() == {"status": "accepted"}


def test_board_returns_list():
    server._insert_verdict(server.VerdictPayload(
        project="proj-b", role="reviewer", model="gpt-4", points=5, reason="ok"
    ))
    resp = client.get("/api/board")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    entry = next((r for r in data if r["project"] == "proj-b"), None)
    assert entry is not None
    assert entry["total_points"] == 5


def test_feed_returns_list():
    server._insert_event(server.ReportPayload(
        project="proj-c", role="tester", event_type="finished"
    ))
    resp = client.get("/api/feed")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) <= 50


def test_status_returns_list():
    resp = client.get("/api/status")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_board_cumulative_scores():
    server._insert_verdict(server.VerdictPayload(
        project="proj-d", role="planner", model="claude-3", points=8, reason="first"
    ))
    server._insert_verdict(server.VerdictPayload(
        project="proj-d", role="planner", model="claude-3", points=7, reason="second"
    ))
    resp = client.get("/api/board")
    data = resp.json()
    entry = next(r for r in data if r["project"] == "proj-d" and r["role"] == "planner")
    assert entry["total_points"] == 15
    assert entry["verdict_count"] == 2


# ── Fixture-based tests for dashboard and /api/verdicts ──

@pytest.fixture()
def isolated_client(tmp_path, monkeypatch):
    monkeypatch.setattr(server.db, "DB_PATH", str(tmp_path / "test.db"))
    with TestClient(server.app) as c:
        yield c


def test_get_root_returns_dashboard_html(isolated_client):
    response = isolated_client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Loop Monitor" in response.text


def test_api_verdicts_empty(isolated_client):
    response = isolated_client.get("/api/verdicts")
    assert response.status_code == 200
    assert response.json() == []


def test_api_verdicts_after_post(isolated_client):
    isolated_client.post("/api/verdict", json={
        "project": "test", "role": "builder", "points": 10, "reason": "good work"
    })
    response = isolated_client.get("/api/verdicts")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["role"] == "builder"
    assert data[0]["points"] == 10
    assert data[0]["reason"] == "good work"


# ── issue_history and pipeline_runs tests ──

def test_history_empty(isolated_client):
    response = isolated_client.get("/api/history/proj-x/42")
    assert response.status_code == 200
    data = response.json()
    assert data["events"] == []
    assert data["run"] is None


def test_history_after_report_with_issue(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-h", role="builder", event_type="started",
        issue_number=10, pr_number=5, model="claude-3"
    ))
    response = isolated_client.get("/api/history/proj-h/10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 1
    assert data["events"][0]["issue_number"] == 10
    assert data["events"][0]["pr_number"] == 5
    assert data["events"][0]["role"] == "builder"
    assert "run" in data


def test_history_no_entry_without_issue_number(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-h2", role="planner", event_type="working"
    ))
    response = isolated_client.get("/api/history/proj-h2/99")
    assert response.status_code == 200
    data = response.json()
    assert data["events"] == []
    assert data["run"] is None


def test_finished_event_sets_lifecycle(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-f", role="dev", event_type="dev_start", issue_number=77
    ))
    server._insert_event(server.ReportPayload(
        project="proj-f", role="dev", event_type="finished", issue_number=77,
        detail="merged"
    ))
    response = isolated_client.get("/api/history/proj-f/77")
    assert response.status_code == 200
    data = response.json()
    assert data["run"] is not None
    assert data["run"]["outcome"] == "merged"
    assert data["run"]["issue_lifetime_seconds"] is not None
    assert data["run"]["issue_lifetime_seconds"] >= 0


def test_runs_empty(isolated_client):
    response = isolated_client.get("/api/runs")
    assert response.status_code == 200
    assert response.json() == []


def test_runs_created_after_report(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-r", role="builder", event_type="started", issue_number=20
    ))
    response = isolated_client.get("/api/runs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["issue_number"] == 20
    assert data[0]["project"] == "proj-r"


def test_runs_by_project(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-p1", role="builder", event_type="done", issue_number=1
    ))
    server._insert_event(server.ReportPayload(
        project="proj-p2", role="builder", event_type="done", issue_number=2
    ))
    response = isolated_client.get("/api/runs/proj-p1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["project"] == "proj-p1"


def test_stats_empty(isolated_client):
    response = isolated_client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_runs" in data
    assert data["total_runs"] == 0


def test_stats_with_runs(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-s", role="builder", event_type="done", issue_number=30
    ))
    response = isolated_client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_runs"] >= 1
    assert "avg_duration_seconds" in data
    assert "success_rate" in data
    assert "rework_rate" in data


def test_timeline_pr_fallback_no_pipeline_run(isolated_client):
    isolated_client.post("/api/report", json={
        "project": "proj-pr", "role": "reviewer", "event_type": "started", "pr_num": 42
    })
    response = isolated_client.get("/api/stats/timeline/pr/proj-pr/42")
    assert response.status_code == 200
    data = response.json()
    assert data["pr_number"] == 42
    assert data["project"] == "proj-pr"
    assert data["issue_number"] is None
    assert len(data["events"]) > 0


def test_pipeline_run_not_duplicated(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-nd", role="planner", event_type="started", issue_number=50
    ))
    server._insert_event(server.ReportPayload(
        project="proj-nd", role="builder", event_type="done", issue_number=50, pr_number=99
    ))
    response = isolated_client.get("/api/runs/proj-nd")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["pr_number"] == 99


# ── Version negotiation tests ──

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
    import logging
    with caplog.at_level(logging.WARNING, logger="server"):
        resp = isolated_client.post("/api/report", json={
            "project": "p", "role": "dev", "event_type": "dev_done",
        })
    assert resp.status_code == 202
    assert any("no 'api' field" in r.message for r in caplog.records)


def test_loop_id_persisted(isolated_client):
    import sqlite3
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
    import sqlite3
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


def test_health_core_version_counts(isolated_client):
    isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
        "core_version": "0.1.0",
    })
    isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
        "core_version": "0.1.0",
    })
    isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
        "core_version": "0.2.0",
    })
    resp = isolated_client.get("/api/health")
    assert resp.status_code == 200
    counts = resp.json()["core_version_counts"]
    assert counts["0.1.0"] == 2
    assert counts["0.2.0"] == 1


# ── /api/loops and health loop_ids tests ──

def test_loops_empty_db(isolated_client):
    resp = isolated_client.get("/api/loops")
    assert resp.status_code == 200
    assert resp.json() == []


def test_loops_with_data(isolated_client):
    import time
    isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
        "loop_id": "loop-1", "core_version": "0.1.0",
    })
    isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
        "loop_id": "loop-1", "core_version": "0.2.0",
    })
    isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
        "core_version": "0.1.0",
    })
    time.sleep(0.1)  # background tasks

    resp = isolated_client.get("/api/loops")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2

    unknown = next(r for r in data if r["loop_id"] == "(unknown)")
    assert unknown["event_count"] == 1
    assert unknown["core_versions"] == ["0.1.0"]

    loop1 = next(r for r in data if r["loop_id"] == "loop-1")
    assert loop1["event_count"] == 2
    assert sorted(loop1["core_versions"]) == ["0.1.0", "0.2.0"]
    assert "last_seen" in loop1


def test_health_loop_ids_field(isolated_client):
    import time
    isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
        "loop_id": "loop-a",
    })
    isolated_client.post("/api/report", json={
        "api": "1.0", "project": "p", "role": "dev", "event_type": "dev_done",
    })
    time.sleep(0.1)  # background tasks

    resp = isolated_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "loop_ids" in data
    assert "(unknown)" in data["loop_ids"]
    assert "loop-a" in data["loop_ids"]


def test_health_loop_ids_empty_db(isolated_client):
    resp = isolated_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "loop_ids" in data
    assert data["loop_ids"] == []


# ── Timeline cumulative_seconds and feed age_seconds tests ──

def test_timeline_cumulative_seconds(isolated_client):
    """cumulative_seconds on each event is elapsed from the first event."""
    # Insert start then done events with a known gap via _insert_event
    # Use direct DB insertion with controlled timestamps for determinism
    import sqlite3

    import server.db as _srv_db
    conn = sqlite3.connect(_srv_db.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "INSERT INTO events (project, role, event_type, issue_number, created_at) VALUES (?,?,?,?,?)",
        ("proj-cum", "builder", "build_start", 77, "2024-01-01T10:00:00+0000"),
    )
    conn.execute(
        "INSERT INTO events (project, role, event_type, issue_number, created_at) VALUES (?,?,?,?,?)",
        ("proj-cum", "builder", "build_done", 77, "2024-01-01T10:05:00+0000"),
    )
    conn.execute(
        "INSERT INTO events (project, role, event_type, issue_number, created_at) VALUES (?,?,?,?,?)",
        ("proj-cum", "tester", "test_start", 77, "2024-01-01T10:06:00+0000"),
    )
    conn.execute(
        "INSERT INTO events (project, role, event_type, issue_number, created_at) VALUES (?,?,?,?,?)",
        ("proj-cum", "tester", "test_done", 77, "2024-01-01T10:08:00+0000"),
    )
    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/stats/timeline/proj-cum/77")
    assert resp.status_code == 200
    data = resp.json()
    events = data["events"]
    assert len(events) == 2

    build_ev = next(e for e in events if e["role"] == "builder")
    test_ev  = next(e for e in events if e["role"] == "tester")

    # build_done at +5m from first event → cumulative 300s
    assert build_ev["cumulative_seconds"] == 300
    # test_done at +8m from first event → cumulative 480s
    assert test_ev["cumulative_seconds"] == 480

    # total_elapsed_seconds = 8m = 480s
    assert data["total_elapsed_seconds"] == 480


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


# ── cycle_times tests ──

def test_cycle_times_empty(isolated_client):
    """Returns null fields when no completed runs exist for the slug."""
    resp = isolated_client.get("/api/projects/no-such-project/cycle_times")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"total_duration": None, "issue_lifetime": None, "pr_lifetime": None}


def test_cycle_times_with_data(isolated_client):
    """Median and P90 are computed correctly from pipeline_runs rows."""
    import sqlite3
    conn = sqlite3.connect(server.db.DB_PATH)
    # Insert 10 rows with total_duration_seconds = 10, 20, ..., 100 (ordered by id)
    for i in range(1, 11):
        conn.execute(
            """INSERT INTO pipeline_runs
               (project, issue_number, total_duration_seconds, created_at)
               VALUES (?, ?, ?, datetime('now'))""",
            ("proj-ct", i, i * 10),
        )
    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/projects/proj-ct/cycle_times")
    assert resp.status_code == 200
    data = resp.json()

    td = data["total_duration"]
    assert td is not None
    assert td["sample_size"] == 10
    # sorted: [10,20,30,40,50,60,70,80,90,100]; floor(0.5*10)=5 → index 5 → 60
    assert td["median_seconds"] == 60
    # floor(0.9*10)=9 → index 9 → 100
    assert td["p90_seconds"] == 100
    # most_recent is the last inserted row
    assert td["most_recent_seconds"] == 100

    # issue_lifetime and pr_lifetime are null because columns not set
    assert data["issue_lifetime"] is None
    assert data["pr_lifetime"] is None


# ── /api/events_graph tests ──

def test_events_graph_empty_db(isolated_client):
    resp = isolated_client.get("/api/events_graph")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"window_hours": 24, "buckets": []}


def test_events_graph_with_data(isolated_client):
    import sqlite3
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        "INSERT INTO events (project, role, event_type, created_at) VALUES (?,?,?,?)",
        ("proj-g", "po", "po_done", "2026-04-28T10:00:00"),
    )
    conn.execute(
        "INSERT INTO events (project, role, event_type, created_at) VALUES (?,?,?,?)",
        ("proj-g", "po", "po_done", "2026-04-28T10:30:00"),
    )
    conn.execute(
        "INSERT INTO events (project, role, event_type, created_at) VALUES (?,?,?,?)",
        ("proj-g", "dev", "dev_done", "2026-04-28T11:00:00"),
    )
    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/events_graph?window=168")
    assert resp.status_code == 200
    data = resp.json()
    assert data["window_hours"] == 168
    buckets = data["buckets"]
    assert isinstance(buckets, list)
    po_bucket = next((b for b in buckets if b["role"] == "po" and b["hour"] == "2026-04-28T10:00:00"), None)
    assert po_bucket is not None
    assert po_bucket["count"] == 2
    dev_bucket = next((b for b in buckets if b["role"] == "dev"), None)
    assert dev_bucket is not None
    assert dev_bucket["count"] == 1


def test_events_graph_window_param(isolated_client):
    resp = isolated_client.get("/api/events_graph?window=48")
    assert resp.status_code == 200
    data = resp.json()
    assert data["window_hours"] == 48


def test_events_graph_window_clamped_to_max(isolated_client):
    resp = isolated_client.get("/api/events_graph?window=9999")
    assert resp.status_code == 200
    data = resp.json()
    assert data["window_hours"] == 168


def test_events_graph_default_window(isolated_client):
    resp = isolated_client.get("/api/events_graph")
    assert resp.status_code == 200
    data = resp.json()
    assert data["window_hours"] == 24


# ── ?loop_id filtering on /api/feed and /api/history ──

def test_feed_loop_id_filter(isolated_client):
    import sqlite3
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


def test_history_loop_id_filter(isolated_client):
    import sqlite3
    now = "2026-01-01T00:00:00+00:00"
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.executemany(
        "INSERT INTO events (project, role, event_type, created_at, loop_id) VALUES (?, ?, ?, ?, ?)",
        [
            ("ph", "dev", "build_done", now, "loop-alpha"),
            ("ph", "dev", "build_done", now, "loop-beta"),
        ],
    )
    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/history?loop_id=loop-alpha")
    assert resp.status_code == 200
    proj_rows = [r for r in resp.json() if r["project"] == "ph"]
    assert len(proj_rows) == 1

    resp_all = isolated_client.get("/api/history")
    assert resp_all.status_code == 200
    all_proj = [r for r in resp_all.json() if r["project"] == "ph"]
    assert len(all_proj) == 2


# ── Migration tests ──

def test_fresh_db_applies_all_migrations(tmp_path, monkeypatch):
    import sqlite3
    db_path = str(tmp_path / "fresh.db")
    monkeypatch.setattr(server.db, "DB_PATH", db_path)
    server.apply_pending_migrations()
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT version_id FROM schema_migrations ORDER BY version_id").fetchall()
    conn.close()
    version_ids = [r[0] for r in rows]
    assert version_ids == ["0001_initial", "0002_add_loop_id", "0003_add_pipeline_run_cols"]
    # Verify columns exist
    conn = sqlite3.connect(db_path)
    event_cols = {r[1] for r in conn.execute("PRAGMA table_info(events)")}
    run_cols = {r[1] for r in conn.execute("PRAGMA table_info(pipeline_runs)")}
    conn.close()
    assert "loop_id" in event_cols
    assert "core_version" in event_cols
    assert "issue_lifetime_seconds" in run_cols
    assert "pr_lifetime_seconds" in run_cols


def test_apply_pending_migrations_idempotent(tmp_path, monkeypatch):
    import sqlite3
    db_path = str(tmp_path / "idempotent.db")
    monkeypatch.setattr(server.db, "DB_PATH", db_path)
    server.apply_pending_migrations()
    server.apply_pending_migrations()
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT version_id FROM schema_migrations ORDER BY version_id").fetchall()
    conn.close()
    version_ids = [r[0] for r in rows]
    assert version_ids == ["0001_initial", "0002_add_loop_id", "0003_add_pipeline_run_cols"]


# ── Feed role/status filter tests ──

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


# ── Action queue tests ──

def test_action_queue_empty(isolated_client):
    resp = isolated_client.get("/api/action_queue")
    assert resp.status_code == 200
    assert resp.json() == []


def test_action_queue_blocked_label(isolated_client):
    server._insert_event(server.ReportPayload(
        project="boba-event", role="dev", event_type="blocked", issue_number=42,
        detail="needs human"
    ))
    resp = isolated_client.get("/api/action_queue")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["project"] == "boba-event"
    assert data[0]["kind"] == "issue"
    assert data[0]["number"] == 42
    assert data[0]["stage"] == "blocked"
    assert data[0]["reason"] == "stuck_label"
    assert data[0]["github_url"].endswith("/issues/42")


def test_action_queue_needs_clarification(isolated_client):
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="needs-clarification", issue_number=7
    ))
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    assert any(item["reason"] == "stuck_label" and item["stage"] == "needs-clarification" for item in data)


def test_action_queue_timeout_threshold(isolated_client, monkeypatch):
    monkeypatch.setenv("HANDLER_TIMEOUT", "100")  # threshold = 200
    import sqlite3
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="in-progress", issue_number=11
    ))
    # backdate created_at to 300s ago — exceeds 200s threshold
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        "UPDATE events SET created_at = datetime('now', '-300 seconds') WHERE issue_number = 11"
    )
    conn.commit()
    conn.close()
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    timeout_items = [it for it in data if it["reason"] == "timeout" and it["number"] == 11]
    assert len(timeout_items) == 1
    assert timeout_items[0]["stage"] == "in-progress"
    assert timeout_items[0]["age_seconds"] >= 200


def test_action_queue_in_progress_below_threshold_excluded(isolated_client, monkeypatch):
    monkeypatch.setenv("HANDLER_TIMEOUT", "3600")
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="in-progress", issue_number=13
    ))
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    assert all(it["number"] != 13 for it in data)


def test_action_queue_sorted_by_age_desc(isolated_client, monkeypatch):
    monkeypatch.setenv("HANDLER_TIMEOUT", "100")
    import sqlite3
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="blocked", issue_number=200
    ))
    server._insert_event(server.ReportPayload(
        project="loop", role="dev", event_type="blocked", issue_number=201
    ))
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        "UPDATE events SET created_at = datetime('now', '-9000 seconds') WHERE issue_number = 200"
    )
    conn.commit()
    conn.close()
    resp = isolated_client.get("/api/action_queue")
    data = resp.json()
    nums = [it["number"] for it in data if it["number"] in (200, 201)]
    assert nums == [200, 201]


def test_concurrent_reports_both_persisted():
    """Concurrent POST /api/report writes must both persist (WAL + busy_timeout)."""
    import threading

    project = "proj-concurrent"
    results: list[int] = []
    lock = threading.Lock()

    def fire(role: str):
        resp = client.post("/api/report", json={
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
    feed = client.get("/api/feed").json()
    roles = {e["role"] for e in feed if e["project"] == project}
    assert {"builder", "reviewer"}.issubset(roles)

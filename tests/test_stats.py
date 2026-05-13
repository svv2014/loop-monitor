import sqlite3

import server
import server.db


def test_status_returns_list(shared_client):
    resp = shared_client.get("/api/status")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


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


def test_timeline_cumulative_seconds(isolated_client):
    """cumulative_seconds on each event is elapsed from the first event."""
    conn = sqlite3.connect(server.db.DB_PATH)
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


def test_cycle_times_empty(isolated_client):
    """Returns null fields when no completed runs exist for the slug."""
    resp = isolated_client.get("/api/projects/no-such-project/cycle_times")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"total_duration": None, "issue_lifetime": None, "pr_lifetime": None}


def test_cycle_times_with_data(isolated_client):
    """Median and P90 are computed correctly from pipeline_runs rows."""
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


def test_status_legacy_judge_remapped(isolated_client):
    """Legacy (role='dev', event_type='judge') row surfaces as role='judge', event_type='judge_done' via /api/status."""
    server._insert_event(server.ReportPayload(
        project="proj-sj-legacy", role="dev", event_type="judge"
    ))
    resp = isolated_client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    item = next((i for i in data if i["project"] == "proj-sj-legacy"), None)
    assert item is not None
    assert item["role"] == "judge"
    assert item["event_type"] == "judge_done"


def test_status_new_judge_unchanged(isolated_client):
    """New-style (role='judge', event_type='judge_done') row passes through /api/status unchanged."""
    server._insert_event(server.ReportPayload(
        project="proj-sj-new", role="judge", event_type="judge_done"
    ))
    resp = isolated_client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    item = next((i for i in data if i["project"] == "proj-sj-new"), None)
    assert item is not None
    assert item["role"] == "judge"
    assert item["event_type"] == "judge_done"

import sqlite3

import server
import server.db


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


def test_history_loop_id_filter(isolated_client):
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

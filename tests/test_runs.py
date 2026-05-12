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
    data = response.json()
    assert data["runs"] == []
    assert data["total"] == 0
    assert data["limit"] == 200


def test_runs_created_after_report(isolated_client):
    server._insert_event(server.ReportPayload(
        project="proj-r", role="builder", event_type="started", issue_number=20
    ))
    response = isolated_client.get("/api/runs")
    assert response.status_code == 200
    data = response.json()
    assert len(data["runs"]) == 1
    assert data["runs"][0]["issue_number"] == 20
    assert data["runs"][0]["project"] == "proj-r"
    assert data["total"] == 1


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
    assert len(data["runs"]) == 1
    assert data["runs"][0]["project"] == "proj-p1"
    assert data["total"] == 1


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
    assert len(data["runs"]) == 1
    assert data["runs"][0]["pr_number"] == 99


def test_runs_default_cap(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    n = 210
    conn.executemany(
        """INSERT INTO pipeline_runs (project, issue_number, created_at)
           VALUES (?, ?, '2026-01-01T00:00:00+00:00')""",
        [("proj-cap", i) for i in range(1, n + 1)],
    )
    conn.commit()
    conn.close()

    response = isolated_client.get("/api/runs/proj-cap")
    assert response.status_code == 200
    data = response.json()
    assert len(data["runs"]) == 200
    assert data["total"] == n
    assert data["limit"] == 200


def test_runs_custom_limit_clamped(isolated_client):
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.executemany(
        """INSERT INTO pipeline_runs (project, issue_number, created_at)
           VALUES (?, ?, '2026-01-01T00:00:00+00:00')""",
        [("proj-clamp", i) for i in range(1, 6)],
    )
    conn.commit()
    conn.close()

    resp_low = isolated_client.get("/api/runs/proj-clamp?limit=0")
    assert resp_low.json()["limit"] == 1

    resp_high = isolated_client.get("/api/runs/proj-clamp?limit=9999")
    assert resp_high.json()["limit"] == 1000


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


def test_prs_unknown_slug_returns_empty(isolated_client):
    resp = isolated_client.get("/api/projects/no-such-project/prs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_prs_lists_open_pipeline_runs(isolated_client):
    server._insert_event(server.ReportPayload(
        project="ppl", role="dev", event_type="dev_start",
        issue_number=101, pr_number=201,
    ))
    server._insert_event(server.ReportPayload(
        project="ppl", role="reviewer", event_type="rework_start",
        issue_number=101, pr_number=201,
    ))
    resp = isolated_client.get("/api/projects/ppl/prs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    pr = data[0]
    assert pr["pr_number"] == 201
    assert pr["last_event"] == "rework_start"
    assert pr["stage"] == "needs-rework"
    assert pr["is_finished"] is False
    assert pr["github_url"].endswith("/pull/201")
    assert pr["time_in_stage_seconds"] is not None
    assert pr["retry_count"] == 0


def test_prs_excludes_finished_by_default(isolated_client):
    server._insert_event(server.ReportPayload(
        project="ppl", role="dev", event_type="dev_start",
        issue_number=110, pr_number=210,
    ))
    server._insert_event(server.ReportPayload(
        project="ppl", role="dev", event_type="dev_start",
        issue_number=111, pr_number=211,
    ))
    server._insert_event(server.ReportPayload(
        project="ppl", role="merge", event_type="finished",
        issue_number=111, pr_number=211, detail="merged",
    ))

    open_only = isolated_client.get("/api/projects/ppl/prs").json()
    pr_nums = {p["pr_number"] for p in open_only}
    assert 210 in pr_nums
    assert 211 not in pr_nums

    all_prs = isolated_client.get("/api/projects/ppl/prs?include_finished=true").json()
    pr_nums_all = {p["pr_number"] for p in all_prs}
    assert 210 in pr_nums_all
    assert 211 in pr_nums_all
    finished_pr = next(p for p in all_prs if p["pr_number"] == 211)
    assert finished_pr["is_finished"] is True

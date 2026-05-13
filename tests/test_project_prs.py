"""Tests for GET /api/projects/{slug}/prs — N+1 fix verification."""
import sqlite3

import server
import server.db


def _select_count(db_path: str) -> tuple[list[str], sqlite3.Connection]:
    """Open a traced connection to db_path; return (queries_list, conn)."""
    queries: list[str] = []
    conn = sqlite3.connect(db_path)
    conn.set_trace_callback(lambda s: queries.append(s) if s.strip().upper().startswith("SELECT") else None)
    return queries, conn


def test_prs_query_count_constant(isolated_client, monkeypatch):
    """Endpoint must issue ≤2 SELECT queries regardless of open-PR count."""
    for i in range(1, 6):
        server._insert_event(server.ReportPayload(
            project="ppl", role="dev", event_type="dev_start",
            issue_number=300 + i, pr_number=400 + i,
        ))
        server._insert_event(server.ReportPayload(
            project="ppl", role="reviewer", event_type="review_start",
            issue_number=300 + i, pr_number=400 + i,
        ))

    queries: list[str] = []

    original_get_db = server.db.get_db

    def traced_get_db():
        conn = original_get_db()
        conn.set_trace_callback(lambda s: queries.append(s) if s.strip().upper().startswith("SELECT") else None)
        return conn

    monkeypatch.setattr(server.db, "get_db", traced_get_db)

    resp = isolated_client.get("/api/projects/ppl/prs")
    assert resp.status_code == 200
    assert len(resp.json()) == 5
    assert len(queries) <= 2, f"Expected ≤2 SELECT queries for 5 PRs, got {len(queries)}: {queries}"


def test_prs_no_events_returns_none_fields(isolated_client):
    """A PR run with no matching events should have None for event-derived fields."""
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.execute(
        "INSERT INTO pipeline_runs (project, issue_number, pr_number, title, rework_count) VALUES (?,?,?,?,?)",
        ("loop", 500, 600, "No events PR", 0),
    )
    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/projects/loop/prs")
    assert resp.status_code == 200
    items = [p for p in resp.json() if p["pr_number"] == 600]
    assert len(items) == 1
    pr = items[0]
    assert pr["stage"] is None
    assert pr["last_event"] is None
    assert pr["last_event_at"] is None
    assert pr["time_in_stage_seconds"] is None
    assert pr["branch"] is None
    assert pr["is_draft"] is None
    assert pr["is_finished"] is False


def test_prs_most_recent_event_selected(isolated_client):
    """When multiple events exist the one with the highest id is used."""
    server._insert_event(server.ReportPayload(
        project="ppl", role="dev", event_type="dev_start",
        issue_number=700, pr_number=800,
    ))
    server._insert_event(server.ReportPayload(
        project="ppl", role="dev", event_type="dev_done",
        issue_number=700, pr_number=800,
    ))
    server._insert_event(server.ReportPayload(
        project="ppl", role="reviewer", event_type="review_start",
        issue_number=700, pr_number=800,
    ))

    resp = isolated_client.get("/api/projects/ppl/prs")
    assert resp.status_code == 200
    items = [p for p in resp.json() if p["pr_number"] == 800]
    assert len(items) == 1
    assert items[0]["last_event"] == "review_start"
    assert items[0]["stage"] == "in-review"

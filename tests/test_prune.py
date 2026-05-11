import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import server
import server.db
from scripts.prune import run


def _ts(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


@pytest.fixture()
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    old_db = server.db.DB_PATH
    server.db.DB_PATH = path
    server.apply_pending_migrations()
    server.db.DB_PATH = old_db
    return path


def _conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _insert_event(conn, project="p", issue_number=None, days_ago=1.0):
    conn.execute(
        "INSERT INTO events (project, role, event_type, created_at) VALUES (?, 'builder', 'started', ?)",
        (project, _ts(days_ago)),
    )
    conn.commit()


def _insert_verdict(conn, project="p", days_ago=1.0):
    conn.execute(
        "INSERT INTO verdicts (project, role, points, created_at) VALUES (?, 'builder', 1, ?)",
        (project, _ts(days_ago)),
    )
    conn.commit()


def _insert_pipeline_run(conn, project="p", issue_number=1, completed=True, days_ago=1.0):
    completed_at = _ts(days_ago) if completed else None
    conn.execute(
        "INSERT INTO pipeline_runs (project, issue_number, created_at, completed_at) VALUES (?, ?, ?, ?)",
        (project, issue_number, _ts(days_ago), completed_at),
    )
    conn.commit()


def _insert_score(conn, project="p", days_ago=1.0):
    conn.execute(
        "INSERT INTO scores (project, role, model, total_points, verdict_count, updated_at)"
        " VALUES (?, 'builder', NULL, 0, 0, ?)",
        (project, _ts(days_ago)),
    )
    conn.commit()


def _insert_issue_history(conn, project="p", days_ago=1.0):
    conn.execute(
        "INSERT INTO issue_history (project, issue_number, role, event_type, created_at)"
        " VALUES (?, 1, 'builder', 'started', ?)",
        (project, _ts(days_ago)),
    )
    conn.commit()


def test_right_rows_deleted_by_age(db_path, monkeypatch):
    monkeypatch.setenv("RETAIN_EVENTS_DAYS", "90")
    monkeypatch.setenv("RETAIN_VERDICTS_DAYS", "365")

    conn = _conn(db_path)
    # old event (120 days ago) — should be pruned
    _insert_event(conn, days_ago=120)
    # recent event (10 days ago) — should be kept
    _insert_event(conn, days_ago=10)
    conn.close()

    run(db_path=db_path, dry_run=False)

    conn = _conn(db_path)
    count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert count == 1, f"Expected 1 event to remain, got {count}"
    remaining_age = conn.execute(
        "SELECT created_at FROM events"
    ).fetchone()[0]
    # The kept row should be more recent than 90 days ago
    kept_dt = datetime.fromisoformat(remaining_age)
    assert kept_dt > datetime.now(timezone.utc) - timedelta(days=90)
    conn.close()


def test_inflight_events_not_pruned(db_path, monkeypatch):
    monkeypatch.setenv("RETAIN_EVENTS_DAYS", "30")

    conn = _conn(db_path)
    # Old event with issue_number tied to an in-progress pipeline run
    conn.execute(
        "INSERT INTO events (project, role, event_type, issue_number, created_at)"
        " VALUES ('p', 'builder', 'started', 42, ?)",
        (_ts(60),),
    )
    conn.commit()
    # Pipeline run for that issue is NOT completed (in-flight)
    _insert_pipeline_run(conn, project="p", issue_number=42, completed=False, days_ago=5)
    conn.close()

    run(db_path=db_path, dry_run=False)

    conn = _conn(db_path)
    count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert count == 1, "In-flight event must not be pruned"
    conn.close()


def test_completed_issue_events_pruned(db_path, monkeypatch):
    monkeypatch.setenv("RETAIN_EVENTS_DAYS", "30")

    conn = _conn(db_path)
    # Old event with issue_number tied to a completed pipeline run
    conn.execute(
        "INSERT INTO events (project, role, event_type, issue_number, created_at)"
        " VALUES ('p', 'builder', 'started', 99, ?)",
        (_ts(60),),
    )
    conn.commit()
    # Pipeline run completed
    _insert_pipeline_run(conn, project="p", issue_number=99, completed=True, days_ago=55)
    conn.close()

    run(db_path=db_path, dry_run=False)

    conn = _conn(db_path)
    count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert count == 0, "Old event for completed issue should be pruned"
    conn.close()


def test_all_tables_pruned(db_path, monkeypatch):
    monkeypatch.setenv("RETAIN_EVENTS_DAYS", "30")
    monkeypatch.setenv("RETAIN_VERDICTS_DAYS", "30")
    monkeypatch.setenv("RETAIN_SCORES_DAYS", "30")
    monkeypatch.setenv("RETAIN_ISSUE_HISTORY_DAYS", "30")
    monkeypatch.setenv("RETAIN_PIPELINE_RUNS_DAYS", "30")

    conn = _conn(db_path)
    _insert_event(conn, days_ago=60)
    _insert_verdict(conn, days_ago=60)
    _insert_score(conn, days_ago=60)
    _insert_issue_history(conn, days_ago=60)
    _insert_pipeline_run(conn, days_ago=60, completed=True)
    conn.close()

    run(db_path=db_path, dry_run=False)

    conn = _conn(db_path)
    for table in ("events", "verdicts", "scores", "issue_history", "pipeline_runs"):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert count == 0, f"Table {table} should be empty after pruning"
    conn.close()


def test_idempotent(db_path, monkeypatch):
    monkeypatch.setenv("RETAIN_EVENTS_DAYS", "30")

    conn = _conn(db_path)
    _insert_event(conn, days_ago=60)
    conn.close()

    run(db_path=db_path, dry_run=False)
    run(db_path=db_path, dry_run=False)

    conn = _conn(db_path)
    count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert count == 0
    conn.close()


def test_dry_run_shows_counts_without_mutating(db_path, monkeypatch, capsys):
    monkeypatch.setenv("RETAIN_EVENTS_DAYS", "30")

    conn = _conn(db_path)
    _insert_event(conn, days_ago=60)
    _insert_event(conn, days_ago=60)
    conn.close()

    run(db_path=db_path, dry_run=True)

    captured = capsys.readouterr()
    assert "dry-run" in captured.out
    assert "events=2" in captured.out

    conn = _conn(db_path)
    count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert count == 2, "Dry-run must not delete rows"
    conn.close()


def test_recent_rows_kept(db_path, monkeypatch):
    monkeypatch.setenv("RETAIN_EVENTS_DAYS", "90")
    monkeypatch.setenv("RETAIN_VERDICTS_DAYS", "365")

    conn = _conn(db_path)
    _insert_event(conn, days_ago=10)
    _insert_verdict(conn, days_ago=10)
    conn.close()

    run(db_path=db_path, dry_run=False)

    conn = _conn(db_path)
    assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM verdicts").fetchone()[0] == 1
    conn.close()


def test_prune_preserves_in_flight(db_path, monkeypatch):
    monkeypatch.setenv("RETAIN_ISSUE_HISTORY_DAYS", "0")
    monkeypatch.setenv("RETAIN_PIPELINE_RUNS_DAYS", "0")
    monkeypatch.setenv("RETAIN_EVENTS_DAYS", "0")
    monkeypatch.setenv("RETAIN_VERDICTS_DAYS", "0")
    monkeypatch.setenv("RETAIN_SCORES_DAYS", "0")

    conn = _conn(db_path)
    # completed run (safe to delete) and in-flight run (must survive)
    _insert_pipeline_run(conn, project="loop-monitor", issue_number=100, completed=True, days_ago=10)
    _insert_pipeline_run(conn, project="loop-monitor", issue_number=200, completed=False, days_ago=10)
    # matching issue_history rows
    conn.execute(
        "INSERT INTO issue_history (project, issue_number, role, event_type, created_at)"
        " VALUES ('loop-monitor', 100, 'builder', 'started', ?)",
        (_ts(10),),
    )
    conn.execute(
        "INSERT INTO issue_history (project, issue_number, role, event_type, created_at)"
        " VALUES ('loop-monitor', 200, 'builder', 'started', ?)",
        (_ts(10),),
    )
    conn.commit()
    conn.close()

    run(db_path=db_path, dry_run=False)

    conn = _conn(db_path)
    runs = conn.execute(
        "SELECT issue_number FROM pipeline_runs ORDER BY issue_number"
    ).fetchall()
    history = conn.execute(
        "SELECT issue_number FROM issue_history ORDER BY issue_number"
    ).fetchall()
    conn.close()

    assert [r[0] for r in runs] == [200], "in-flight pipeline_runs row must survive"
    assert [r[0] for r in history] == [200], "issue_history for in-flight run must survive"

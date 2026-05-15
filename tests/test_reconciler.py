import json
import os
import sqlite3
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.reconciler import emit_issue_closed_events


def _make_db(tmp_path) -> sqlite3.Connection:
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            role TEXT NOT NULL,
            model TEXT,
            event_type TEXT NOT NULL,
            issue_number INTEGER,
            pr_number INTEGER,
            detail TEXT,
            payload TEXT,
            core_version TEXT,
            loop_id TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _insert(conn, project, event_type, issue_number):
    conn.execute(
        "INSERT INTO events (project, role, event_type, issue_number, created_at)"
        " VALUES (?, 'dev', ?, ?, datetime('now'))",
        (project, event_type, issue_number),
    )
    conn.commit()


def _make_gh_closed_side_effect(closed: list[int]):
    def _side_effect(cmd, **kwargs):
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = json.dumps(closed)
        return mock
    return _side_effect


def test_emit_issue_closed_inserts_event(tmp_path):
    """Reconciler inserts issue_closed when gh reports the candidate as CLOSED."""
    conn = _make_db(tmp_path)
    _insert(conn, "myproject", "dev_done", 42)

    with patch("scripts.reconciler.subprocess.run",
               side_effect=_make_gh_closed_side_effect([42, 99])):
        emit_issue_closed_events(conn, {"myproject": "example-org/myproject"})

    rows = conn.execute(
        "SELECT event_type, issue_number FROM events"
        " WHERE project = 'myproject' AND event_type = 'issue_closed'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["issue_number"] == 42


def test_emit_issue_closed_skips_already_terminal(tmp_path):
    """Reconciler does not insert issue_closed when merge_done already exists."""
    conn = _make_db(tmp_path)
    _insert(conn, "myproject", "dev_done", 10)
    _insert(conn, "myproject", "merge_done", 10)

    with patch("scripts.reconciler.subprocess.run") as mock_run:
        emit_issue_closed_events(conn, {"myproject": "example-org/myproject"})

    mock_run.assert_not_called()
    rows = conn.execute(
        "SELECT COUNT(*) AS cnt FROM events"
        " WHERE project = 'myproject' AND event_type = 'issue_closed'"
    ).fetchone()
    assert rows["cnt"] == 0


def test_emit_issue_closed_gh_failure_skips_project(tmp_path):
    """When gh call fails, no issue_closed events are inserted."""
    conn = _make_db(tmp_path)
    _insert(conn, "proj", "dev_done", 7)

    fail_mock = MagicMock()
    fail_mock.returncode = 1
    fail_mock.stdout = ""
    with patch("scripts.reconciler.subprocess.run", return_value=fail_mock):
        emit_issue_closed_events(conn, {"proj": "example-org/proj"})

    rows = conn.execute(
        "SELECT COUNT(*) AS cnt FROM events WHERE event_type = 'issue_closed'"
    ).fetchone()
    assert rows["cnt"] == 0


def test_emit_issue_closed_open_issue_not_inserted(tmp_path):
    """Candidate issue that gh reports as open (not in closed list) is not touched."""
    conn = _make_db(tmp_path)
    _insert(conn, "proj", "dev_done", 5)

    with patch("scripts.reconciler.subprocess.run",
               side_effect=_make_gh_closed_side_effect([99, 100])):
        emit_issue_closed_events(conn, {"proj": "example-org/proj"})

    rows = conn.execute(
        "SELECT COUNT(*) AS cnt FROM events WHERE event_type = 'issue_closed'"
    ).fetchone()
    assert rows["cnt"] == 0


def test_emit_issue_closed_no_candidates_skips_gh(tmp_path):
    """When all issues already have terminal events, gh is never called."""
    conn = _make_db(tmp_path)
    _insert(conn, "proj", "dev_done", 3)
    _insert(conn, "proj", "issue_closed", 3)

    with patch("scripts.reconciler.subprocess.run") as mock_run:
        emit_issue_closed_events(conn, {"proj": "example-org/proj"})

    mock_run.assert_not_called()

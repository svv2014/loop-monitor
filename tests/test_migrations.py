import sqlite3

import pytest

import server
import server.db


def test_fresh_db_applies_all_migrations(tmp_path, monkeypatch):
    db_path = str(tmp_path / "fresh.db")
    monkeypatch.setattr(server.db, "DB_PATH", db_path)
    server.apply_pending_migrations()
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT version_id FROM schema_migrations ORDER BY version_id").fetchall()
    conn.close()
    version_ids = [r[0] for r in rows]
    assert version_ids == ["0001_initial", "0002_add_loop_id", "0003_add_pipeline_run_cols"]
    conn = sqlite3.connect(db_path)
    event_cols = {r[1] for r in conn.execute("PRAGMA table_info(events)")}
    run_cols = {r[1] for r in conn.execute("PRAGMA table_info(pipeline_runs)")}
    conn.close()
    assert "loop_id" in event_cols
    assert "core_version" in event_cols
    assert "issue_lifetime_seconds" in run_cols
    assert "pr_lifetime_seconds" in run_cols


def test_apply_pending_migrations_idempotent(tmp_path, monkeypatch):
    db_path = str(tmp_path / "idempotent.db")
    monkeypatch.setattr(server.db, "DB_PATH", db_path)
    server.apply_pending_migrations()
    server.apply_pending_migrations()
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT version_id FROM schema_migrations ORDER BY version_id").fetchall()
    conn.close()
    version_ids = [r[0] for r in rows]
    assert version_ids == ["0001_initial", "0002_add_loop_id", "0003_add_pipeline_run_cols"]


def test_migration_rolls_back_on_mid_script_failure(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(server.db, "DB_PATH", str(db_path))

    fake_migration_sql = """
        CREATE TABLE rollback_target (id INTEGER PRIMARY KEY);
        CREATE INDEX rollback_idx ON rollback_target(id);
        THIS IS NOT VALID SQL;
    """
    monkeypatch.setattr(server.db, "MIGRATIONS", [("9999_test_rollback", fake_migration_sql)])
    monkeypatch.setattr(server.db, "_migration_already_applied", lambda c, v: False)

    with pytest.raises(sqlite3.OperationalError):
        server.db.apply_pending_migrations()

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='rollback_target'"
    ).fetchone()
    assert row is None, "DDL should have been rolled back"
    applied = conn.execute(
        "SELECT version_id FROM schema_migrations WHERE version_id='9999_test_rollback'"
    ).fetchone()
    assert applied is None, "schema_migrations should not have the failed version"
    conn.close()

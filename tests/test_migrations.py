import sqlite3

import server


def test_fresh_db_applies_all_migrations(tmp_path, monkeypatch):
    db_path = str(tmp_path / "fresh.db")
    monkeypatch.setattr(server, "DB_PATH", db_path)
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
    monkeypatch.setattr(server, "DB_PATH", db_path)
    server.apply_pending_migrations()
    server.apply_pending_migrations()
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT version_id FROM schema_migrations ORDER BY version_id").fetchall()
    conn.close()
    version_ids = [r[0] for r in rows]
    assert version_ids == ["0001_initial", "0002_add_loop_id", "0003_add_pipeline_run_cols"]

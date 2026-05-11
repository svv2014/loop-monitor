import sqlite3

from fastapi.testclient import TestClient

import server
import server.db
from server.app import app


def test_no_connection_leak_on_handler_error(monkeypatch, tmp_path):
    monkeypatch.setattr(server.db, "DB_PATH", str(tmp_path / "test.db"))
    server.apply_pending_migrations()

    open_count = {"n": 0}
    real_get_db = server.db.get_db

    class TrackingConnection:
        def __init__(self, real_conn: sqlite3.Connection):
            self._conn = real_conn
            open_count["n"] += 1

        def execute(self, sql: str, *args, **kwargs):
            if "scores" in sql:
                raise sqlite3.OperationalError("injected error")
            return self._conn.execute(sql, *args, **kwargs)

        def close(self):
            open_count["n"] -= 1
            self._conn.close()

        def __getattr__(self, name: str):
            return getattr(self._conn, name)

    def patched_get_db():
        return TrackingConnection(real_get_db())  # type: ignore[return-value]

    monkeypatch.setattr(server.db, "get_db", patched_get_db)

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/board")

    assert resp.status_code >= 500
    assert open_count["n"] == 0, f"Expected 0 open connections, got {open_count['n']}"

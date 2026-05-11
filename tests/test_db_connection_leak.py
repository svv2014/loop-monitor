import sqlite3

from fastapi.testclient import TestClient

import server
import server.db


def test_no_connection_leak_on_handler_error(tmp_path, monkeypatch):
    monkeypatch.setattr(server.db, "DB_PATH", str(tmp_path / "test.db"))
    server.apply_pending_migrations()

    open_count = {"n": 0}
    execute_calls = {"n": 0}
    real_get_db = server.db.get_db

    def tracking_get_db():
        conn = real_get_db()
        open_count["n"] += 1

        class _Tracked:
            """Proxy around sqlite3.Connection that tracks open/close and injects one error."""

            def close(self_inner):
                open_count["n"] -= 1
                conn.close()

            def execute(self_inner, *args, **kwargs):
                execute_calls["n"] += 1
                if execute_calls["n"] == 1:
                    raise sqlite3.OperationalError("injected error")
                return conn.execute(*args, **kwargs)

            def __getattr__(self_inner, name):
                return getattr(conn, name)

        return _Tracked()

    monkeypatch.setattr(server.db, "get_db", tracking_get_db)

    with TestClient(server.app, raise_server_exceptions=False) as client:
        response = client.get("/api/board")

    assert response.status_code >= 400
    assert open_count["n"] == 0, f"Leaked {open_count['n']} connection(s)"

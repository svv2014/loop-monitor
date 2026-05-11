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

    class _ConnProxy:
        """Wraps a real sqlite3.Connection to track open/close lifecycle."""

        def __init__(self, conn: sqlite3.Connection) -> None:
            object.__setattr__(self, "_conn", conn)
            open_count["n"] += 1

        def close(self) -> None:
            open_count["n"] -= 1
            object.__getattribute__(self, "_conn").close()

        def execute(self, sql: str, *args, **kwargs):
            if "scores" in sql and "ORDER BY" in sql:
                raise sqlite3.OperationalError("injected error for leak test")
            return object.__getattribute__(self, "_conn").execute(sql, *args, **kwargs)

        def __getattr__(self, name: str):
            return getattr(object.__getattribute__(self, "_conn"), name)

        def __setattr__(self, name: str, value) -> None:
            setattr(object.__getattribute__(self, "_conn"), name, value)

    def tracking_get_db() -> _ConnProxy:
        return _ConnProxy(real_get_db())

    monkeypatch.setattr(server.db, "get_db", tracking_get_db)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/board")

    assert response.status_code >= 400
    assert open_count["n"] == 0, (
        f"Connection leak detected: {open_count['n']} unclosed connection(s)"
    )

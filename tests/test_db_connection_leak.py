import sqlite3

import pytest
from fastapi.testclient import TestClient

import server
import server.db


def test_no_connection_leak_on_handler_error(tmp_path, monkeypatch):
    monkeypatch.setattr(server.db, "DB_PATH", str(tmp_path / "test.db"))
    server.apply_pending_migrations()

    open_count: dict = {"n": 0}
    real_get_db = server.db.get_db

    class TrackingConn:
        """Pure-Python wrapper — tracks open/close and injects an execute error."""

        def __init__(self) -> None:
            self._real = real_get_db()
            open_count["n"] += 1

        def close(self) -> None:
            open_count["n"] -= 1
            self._real.close()

        def execute(self, sql: str, *args, **kwargs):
            raise sqlite3.OperationalError("injected error")

        def __getattr__(self, name: str):
            return getattr(self._real, name)

    monkeypatch.setattr(server.db, "get_db", TrackingConn)

    with TestClient(server.app, raise_server_exceptions=False) as client:
        response = client.get("/api/board")

    assert response.status_code >= 400
    assert open_count["n"] == 0, f"Expected 0 open connections, got {open_count['n']}"

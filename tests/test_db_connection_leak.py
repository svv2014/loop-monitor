import sqlite3

import pytest
from fastapi.testclient import TestClient

import server
import server.db


@pytest.fixture()
def leak_client(tmp_path, monkeypatch):
    monkeypatch.setattr(server.db, "DB_PATH", str(tmp_path / "test.db"))
    server.apply_pending_migrations()
    with TestClient(server.app, raise_server_exceptions=False) as c:
        yield c


class _ConnProxy:
    """Wraps a sqlite3.Connection to track open/close counts."""

    def __init__(self, conn, open_count):
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_open_count", open_count)

    def close(self):
        object.__getattribute__(self, "_open_count")["n"] -= 1
        object.__getattribute__(self, "_conn").close()

    def execute(self, sql, *args, **kwargs):
        # Let PRAGMA calls through (used by get_db setup); raise on real queries
        if not sql.strip().upper().startswith("PRAGMA"):
            raise sqlite3.OperationalError("injected error for leak test")
        return object.__getattribute__(self, "_conn").execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_conn"), name)

    def __setattr__(self, name, value):
        setattr(object.__getattribute__(self, "_conn"), name, value)


def test_no_connection_leak_on_handler_error(leak_client, monkeypatch):
    open_count = {"n": 0}
    real_connect = sqlite3.connect

    def tracking_connect(*a, **kw):
        conn = real_connect(*a, **kw)
        open_count["n"] += 1
        return _ConnProxy(conn, open_count)

    monkeypatch.setattr("server.db.sqlite3.connect", tracking_connect)

    resp = leak_client.get("/api/board")
    assert resp.status_code >= 400
    assert open_count["n"] == 0, f"Connection leak: {open_count['n']} connection(s) still open"

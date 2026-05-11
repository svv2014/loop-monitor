import sqlite3

from fastapi.testclient import TestClient

from server.app import app


class _FailOnQueryConnection:
    """Proxy that lets PRAGMA calls through but raises on the first real query."""

    def __init__(self, conn, counter):
        self._conn = conn
        self._counter = counter
        self._counter["n"] += 1

    def execute(self, sql, *args, **kwargs):
        if not str(sql).strip().upper().startswith("PRAGMA"):
            raise sqlite3.OperationalError("injected error")
        return self._conn.execute(sql, *args, **kwargs)

    def close(self):
        self._counter["n"] -= 1
        self._conn.close()

    def __setattr__(self, name, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._conn, name, value)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def test_no_connection_leak_on_handler_error(monkeypatch):
    open_count = {"n": 0}
    real_connect = sqlite3.connect

    def tracking_connect(*a, **kw):
        conn = real_connect(*a, **kw)
        return _FailOnQueryConnection(conn, open_count)

    monkeypatch.setattr("server.db.sqlite3.connect", tracking_connect)

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/board")

    assert response.status_code >= 400
    assert open_count["n"] == 0, f"Leaked {open_count['n']} connection(s)"

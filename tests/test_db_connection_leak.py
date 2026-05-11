import sqlite3
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import server
import server.db
from server.app import app


def test_no_connection_leak_on_handler_error(monkeypatch, tmp_path):
    monkeypatch.setattr(server.db, "DB_PATH", str(tmp_path / "test.db"))
    server.db.apply_pending_migrations()
    # Prevent lifespan from re-running migrations while get_db is mocked.
    monkeypatch.setattr(server.db, "apply_pending_migrations", lambda: None)

    mock_conn = MagicMock(spec=sqlite3.Connection)
    mock_conn.execute.side_effect = sqlite3.OperationalError("forced error for leak test")
    monkeypatch.setattr(server.db, "get_db", lambda: mock_conn)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/board")

    assert response.status_code >= 400
    mock_conn.close.assert_called_once()

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402
import server.db  # noqa: E402


@pytest.fixture(scope="session")
def shared_client(tmp_path_factory):
    db_path = str(tmp_path_factory.mktemp("shared") / "test.db")
    server.db.DB_PATH = db_path
    server.apply_pending_migrations()
    with TestClient(server.app) as c:
        yield c


@pytest.fixture()
def isolated_client(tmp_path, monkeypatch):
    monkeypatch.setattr(server.db, "DB_PATH", str(tmp_path / "test.db"))
    server.apply_pending_migrations()
    with TestClient(server.app) as c:
        yield c

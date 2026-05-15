import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402
import server.db  # noqa: E402
import server.routes.action_queue as _aq  # noqa: E402


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
    # Default: make gh open-set calls fail so the filter passes items through
    # conservatively. LM-309 open-set tests patch subprocess.run themselves
    # (via unittest.mock.patch) which overrides this mock for their block.
    _fail = MagicMock()
    _fail.returncode = 1
    _subprocess_mock = MagicMock()
    _subprocess_mock.run.return_value = _fail
    monkeypatch.setattr(_aq, "subprocess", _subprocess_mock)
    _aq._OPEN_SET_CACHE.clear()
    with TestClient(server.app) as c:
        yield c

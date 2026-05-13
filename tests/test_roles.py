"""Tests for the role-vocabulary loader."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from textwrap import dedent


def _reload_roles_with_config(monkeypatch, config_path: Path | None) -> list:
    if config_path is None:
        monkeypatch.delenv("LOOP_MONITOR_ROLES_CONFIG", raising=False)
    else:
        monkeypatch.setenv("LOOP_MONITOR_ROLES_CONFIG", str(config_path))
    sys.modules.pop("server.roles", None)
    mod = importlib.import_module("server.roles")
    return mod.ROLES


def test_loads_well_formed_yaml(tmp_path, monkeypatch):
    cfg = tmp_path / "roles.yaml"
    cfg.write_text(dedent("""\
        roles:
          - id: lint
            label: Lint
            color: cyan
          - id: build
            label: Build
            color: blue
    """))
    roles = _reload_roles_with_config(monkeypatch, cfg)
    assert roles == [
        {"id": "lint",  "label": "Lint",  "color": "cyan"},
        {"id": "build", "label": "Build", "color": "blue"},
    ]


def test_invalid_color_falls_back_to_gray(tmp_path, monkeypatch):
    cfg = tmp_path / "roles.yaml"
    cfg.write_text(dedent("""\
        roles:
          - id: test
            label: Test
            color: chartreuse
    """))
    roles = _reload_roles_with_config(monkeypatch, cfg)
    assert roles == [{"id": "test", "label": "Test", "color": "gray"}]


def test_duplicate_ids_kept_first(tmp_path, monkeypatch):
    cfg = tmp_path / "roles.yaml"
    cfg.write_text(dedent("""\
        roles:
          - id: dev
            label: First
            color: blue
          - id: dev
            label: Second
            color: pink
    """))
    roles = _reload_roles_with_config(monkeypatch, cfg)
    assert len(roles) == 1
    assert roles[0]["label"] == "First"


def test_missing_id_skipped(tmp_path, monkeypatch):
    cfg = tmp_path / "roles.yaml"
    cfg.write_text(dedent("""\
        roles:
          - label: NoId
            color: red
          - id: ok
            label: OK
            color: green
    """))
    roles = _reload_roles_with_config(monkeypatch, cfg)
    assert [r["id"] for r in roles] == ["ok"]


def test_missing_file_returns_defaults(tmp_path, monkeypatch):
    nonexistent = tmp_path / "absent.yaml"
    roles = _reload_roles_with_config(monkeypatch, nonexistent)
    # Built-in Loop defaults: po, dev, qa, reviewer, merge, judge
    ids = [r["id"] for r in roles]
    assert ids == ["po", "dev", "qa", "reviewer", "merge", "judge"]


def test_label_defaults_to_id(tmp_path, monkeypatch):
    cfg = tmp_path / "roles.yaml"
    cfg.write_text(dedent("""\
        roles:
          - id: solo
            color: violet
    """))
    roles = _reload_roles_with_config(monkeypatch, cfg)
    assert roles == [{"id": "solo", "label": "solo", "color": "violet"}]


def test_config_endpoint_shape():
    """Smoke-test that /api/config/roles returns the right shape."""
    from server.routes.config import get_roles
    result = get_roles()
    assert "roles" in result
    assert isinstance(result["roles"], list)
    for r in result["roles"]:
        assert {"id", "label", "color"} <= r.keys()

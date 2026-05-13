"""Tests for the project registry loader.

Note: these tests exercise the loader through env-var overrides so they do
not depend on any operator-local `config/projects.yaml` that may or may not
exist on the host running them.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from textwrap import dedent


def _reload_constants_with_config(monkeypatch, config_path: Path | None) -> dict[str, str]:
    if config_path is None:
        monkeypatch.delenv("LOOP_MONITOR_PROJECTS_CONFIG", raising=False)
    else:
        monkeypatch.setenv("LOOP_MONITOR_PROJECTS_CONFIG", str(config_path))
    sys.modules.pop("server.constants", None)
    mod = importlib.import_module("server.constants")
    return mod.PROJECTS


def test_loads_well_formed_yaml(tmp_path, monkeypatch):
    cfg = tmp_path / "projects.yaml"
    cfg.write_text(dedent("""\
        projects:
          example:   org/example
          docs-site: org/docs-site
    """))
    projects = _reload_constants_with_config(monkeypatch, cfg)
    assert projects == {"example": "org/example", "docs-site": "org/docs-site"}


def test_skips_malformed_entries(tmp_path, monkeypatch):
    cfg = tmp_path / "projects.yaml"
    cfg.write_text(dedent("""\
        projects:
          good:    org/good
          no-slash: not-a-repo
          two/slashes: org/sub/repo
    """))
    projects = _reload_constants_with_config(monkeypatch, cfg)
    assert projects == {"good": "org/good"}


def test_missing_file_yields_empty(tmp_path, monkeypatch):
    nonexistent = tmp_path / "absent.yaml"
    projects = _reload_constants_with_config(monkeypatch, nonexistent)
    assert projects == {}


def test_owner_repo_shape():
    """If projects are loaded from the host's actual config, validate shape."""
    from server.constants import PROJECTS
    pattern = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    for slug, repo in PROJECTS.items():
        assert pattern.match(repo), f"{slug!r} value {repo!r} is not owner/repo"

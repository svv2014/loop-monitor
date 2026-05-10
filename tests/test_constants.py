import re

from server.constants import PROJECTS


def test_projects_include_loop_emitted_slugs():
    assert "boba-orchestrator" in PROJECTS
    assert "loop-monitor" in PROJECTS
    assert "suprun" in PROJECTS


def test_projects_drop_legacy_bounty_alias():
    assert "bounty" not in PROJECTS


def test_projects_values_use_owner_repo_shape():
    owner_repo = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    assert all(owner_repo.match(repo) for repo in PROJECTS.values())


def test_loop_monitor_slug_maps_to_loop_monitor_repo():
    assert PROJECTS["loop-monitor"] == "svv2014/loop-monitor"

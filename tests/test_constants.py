import re

from server.constants import PROJECTS


def test_new_slugs_present():
    for slug in ('loop-monitor', 'boba-orchestrator', 'suprun'):
        assert slug in PROJECTS, f"missing slug: {slug}"


def test_bounty_key_absent():
    assert 'bounty' not in PROJECTS


def test_all_values_owner_repo_shape():
    pattern = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
    for slug, repo in PROJECTS.items():
        assert pattern.match(repo), f"{slug!r} value {repo!r} is not owner/repo"


def test_loop_monitor_maps_correctly():
    assert PROJECTS['loop-monitor'] == 'svv2014/loop-monitor'

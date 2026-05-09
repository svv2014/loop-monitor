"""Visual regression test for the ProjectDetail screen.

Requires the Playwright visual-diff harness from #113 to be in place.
Run with: pytest tests/visual/ -k project_detail

The harness must:
  - Start the Vite dev server (or serve the built web/ output)
  - Navigate to /#project=<fixture_project_id>
  - Mask timestamps, durations, and SHAs per the harness mask rules
  - Compare against design/reference-screenshots/project-pr-monitor.png (≤ 0.5% diff)
"""
import os
import pathlib

import pytest

REFERENCE_DIR = pathlib.Path(__file__).parents[2] / "design" / "reference-screenshots"
FIXTURE_PROJECT = os.getenv("LM_FIXTURE_PROJECT", "svv2014/loop-monitor")
DIFF_THRESHOLD = 0.005  # 0.5%


@pytest.fixture
def project_detail_url(base_url: str) -> str:
    """URL that opens the ProjectDetail screen with fixture data."""
    project_encoded = FIXTURE_PROJECT.replace("/", "%2F")
    return f"{base_url}/#project={project_encoded}"


@pytest.mark.visual
def test_project_detail_kpi_strip(page, project_detail_url, assert_snapshot):
    """KPI strip (Status / Total points / Active workers / Events 24h / Open issues)."""
    page.goto(project_detail_url)
    page.wait_for_selector("[data-testid='project-detail']", timeout=10_000)

    # Mask dynamic values: numbers in KPI cells, timestamps
    assert_snapshot(
        page.locator("[data-testid='project-detail']"),
        name="project_detail_full",
        threshold=DIFF_THRESHOLD,
        mask_selectors=[".num", ".muted.mono"],
    )


@pytest.mark.visual
def test_project_pr_monitor(page, project_detail_url, assert_snapshot):
    """PR Monitor sub-panel matches reference screenshot (≤ 0.5% diff)."""
    page.goto(project_detail_url)
    page.wait_for_selector("[data-testid='project-detail']", timeout=10_000)

    reference = REFERENCE_DIR / "project-pr-monitor.png"

    assert_snapshot(
        page.locator(".panel").filter(has_text="PR Monitor"),
        name="project_pr_monitor",
        threshold=DIFF_THRESHOLD,
        reference=reference if reference.exists() else None,
        mask_selectors=[".num", ".mono"],
    )


@pytest.mark.visual
def test_hash_routing(page, base_url):
    """Navigating to #project=<id> renders the ProjectDetail screen."""
    project_encoded = FIXTURE_PROJECT.replace("/", "%2F")
    page.goto(f"{base_url}/#project={project_encoded}")
    page.wait_for_selector("[data-testid='project-detail']", timeout=10_000)
    assert page.url.endswith(f"#project={project_encoded}")


@pytest.mark.visual
def test_hash_back_navigation(page, base_url):
    """Back navigation from ProjectDetail returns to overview and clears hash."""
    project_encoded = FIXTURE_PROJECT.replace("/", "%2F")
    page.goto(f"{base_url}/#project={project_encoded}")
    page.wait_for_selector("[data-testid='project-detail']", timeout=10_000)

    page.click("button:has-text('← Overview')")
    page.wait_for_function("!window.location.hash || window.location.hash === '#'")


@pytest.mark.visual
def test_project_switcher_updates_hash(page, base_url, all_project_ids):
    """Changing the project selector updates location.hash."""
    if len(all_project_ids) < 2:
        pytest.skip("Need at least 2 projects to test switcher")

    first, second = all_project_ids[:2]
    page.goto(f"{base_url}/#project={first}")
    page.wait_for_selector("[data-testid='project-detail']", timeout=10_000)

    page.select_option("select[aria-label='Switch project']", second)
    page.wait_for_function(
        f"window.location.hash.includes('{second}')",
        timeout=3_000,
    )

"""Visual regression tests for the ProjectDetail screen.

Requires the Playwright visual-diff harness from #113.
Run with: pytest tests/visual/ -k project_detail

Fixture project is controlled by the LM_FIXTURE_PROJECT env var.
The harness must serve the Vite build at base_url and supply:
  - assert_snapshot(locator, name, threshold, mask_selectors)
  - base_url fixture
"""
import os
import pathlib

import pytest

REFERENCE_DIR = pathlib.Path(__file__).parents[2] / "design" / "reference-screenshots"
FIXTURE_PROJECT = os.getenv("LM_FIXTURE_PROJECT", "svv2014/loop-monitor")
DIFF_THRESHOLD = 0.005  # 0.5 %


def _project_url(base_url: str) -> str:
    encoded = FIXTURE_PROJECT.replace("/", "%2F")
    return f"{base_url}/#project={encoded}"


@pytest.mark.visual
def test_project_detail_renders(page, base_url: str) -> None:
    """ProjectDetail screen renders when hash is #project=<id>."""
    page.goto(_project_url(base_url))
    page.wait_for_selector("[data-testid='project-detail']", timeout=10_000)


@pytest.mark.visual
def test_project_detail_full(page, base_url: str, assert_snapshot) -> None:  # type: ignore[no-untyped-def]
    """Full ProjectDetail snapshot — ≤ 0.5 % diff against reference."""
    page.goto(_project_url(base_url))
    page.wait_for_selector("[data-testid='project-detail']", timeout=10_000)
    assert_snapshot(
        page.locator("[data-testid='project-detail']"),
        name="project_detail_full",
        threshold=DIFF_THRESHOLD,
        mask_selectors=[".num", ".muted.mono"],
    )


@pytest.mark.visual
def test_project_pr_monitor(page, base_url: str, assert_snapshot) -> None:  # type: ignore[no-untyped-def]
    """PR Monitor sub-panel matches reference screenshot (≤ 0.5 % diff)."""
    page.goto(_project_url(base_url))
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
def test_hash_routing(page, base_url: str) -> None:
    """Navigating to #project=<id> renders ProjectDetail; hash is preserved."""
    encoded = FIXTURE_PROJECT.replace("/", "%2F")
    page.goto(_project_url(base_url))
    page.wait_for_selector("[data-testid='project-detail']", timeout=10_000)
    assert f"#project={encoded}" in page.url


@pytest.mark.visual
def test_hash_back_navigation(page, base_url: str) -> None:
    """Clicking ← Overview clears the hash and hides ProjectDetail."""
    page.goto(_project_url(base_url))
    page.wait_for_selector("[data-testid='project-detail']", timeout=10_000)
    page.click("button:has-text('← Overview')")
    page.wait_for_function("!window.location.hash || window.location.hash === '#'")
    assert page.locator("[data-testid='project-detail']").count() == 0


@pytest.mark.visual
def test_project_switcher_updates_hash(page, base_url: str, all_project_ids: list[str]) -> None:
    """Changing the project selector updates location.hash."""
    if len(all_project_ids) < 2:
        pytest.skip("Need ≥ 2 projects to test the project switcher")
    first, second = all_project_ids[:2]
    page.goto(f"{base_url}/#project={first}")
    page.wait_for_selector("[data-testid='project-detail']", timeout=10_000)
    page.select_option("select[aria-label='Switch project']", second)
    page.wait_for_function(f"window.location.hash.includes('{second}')", timeout=3_000)

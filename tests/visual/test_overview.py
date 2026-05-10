"""
Visual-diff tests for the Overview screen (Charts + ClaudeUsage panels).

These tests require the Playwright-based visual-diff harness from #113.
They are marked as 'visual' so the standard pytest run skips them unless
the harness is available (playwright must be installed and the dev server running).
"""
import pytest


@pytest.mark.skip(reason="visual-diff harness (#113) not yet merged — pending Phase 4 completion")
def test_overview_charts_visual():
    """Overview screen with Charts panel renders within 0.5% pixel diff of baseline."""
    pass


@pytest.mark.skip(reason="visual-diff harness (#113) not yet merged — pending Phase 4 completion")
def test_overview_claude_usage_visual():
    """Claude Usage panel renders quota bar at correct width."""
    pass

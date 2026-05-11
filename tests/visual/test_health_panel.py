"""
Visual-diff tests for the HealthPanel component.

Requires the Playwright-based visual-diff harness from #113.
Run against ?fixtures=1 so output is byte-deterministic.
"""
import pytest


@pytest.mark.skip(reason="visual-diff harness (#113) not yet merged — pending Phase 4 completion")
def test_health_panel_visual():
    """HealthPanel renders within 0.5% pixel diff of baseline (design/reference-screenshots/health-panel.png)."""
    pass

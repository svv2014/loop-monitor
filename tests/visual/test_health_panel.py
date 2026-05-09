"""
Visual-diff test for HealthPanel — depends on the screenshot harness from #113.

This file is a stub. Enable once #113's harness is merged and
design/reference-screenshots/health-panel.png is captured.
"""
import pytest


@pytest.mark.skip(reason="visual-diff harness (#113) not yet merged")
def test_health_panel_visual_diff():
    """
    Load HealthPanel at /?fixtures=1, capture a screenshot, and assert
    pixel-diff against design/reference-screenshots/health-panel.png is ≤ 0.5%.
    Implement using the harness API from #113.
    """
    pass

"""Visual regression test: React Overview screen vs frozen reference screenshot.

Requires the React app to be built and served. Skips automatically if
playwright is not installed or REACT_APP_URL is not set.

Run manually:
    cd web && npm run build
    python -m http.server 5173 --directory static/dist &
    pytest tests/visual/test_overview.py -v
"""
from io import BytesIO
from pathlib import Path

import os
import pytest

pytest.importorskip("playwright", reason="playwright not installed — skipping visual tests")

from PIL import Image, ImageChops  # noqa: E402
import numpy as np  # noqa: E402

from tests.visual.conftest import FREEZE_AND_MASK_JS  # noqa: E402

REPO_ROOT = Path(__file__).parents[2]
REFERENCE_DIR = REPO_ROOT / "design" / "reference-screenshots"
ARTIFACTS_DIR = Path(__file__).parent / "_artifacts"

DIFF_THRESHOLD = 0.005  # 0.5%

REACT_APP_URL = os.environ.get("REACT_APP_URL", "")


def _pixel_diff_ratio(ref: Image.Image, current: Image.Image) -> tuple[float, Image.Image]:
    ref_rgb = ref.convert("RGB")
    cur_rgb = current.convert("RGB")
    diff = ImageChops.difference(ref_rgb, cur_rgb)
    arr = np.array(diff, dtype=np.uint8)
    mismatched = int(np.any(arr > 10, axis=2).sum())
    total = arr.shape[0] * arr.shape[1]
    return mismatched / total, diff


@pytest.mark.skipif(not REACT_APP_URL, reason="REACT_APP_URL not set — skipping React app visual test")
def test_overview_react(page) -> None:
    """Overview screen of the React app must match the frozen prototype reference."""
    ref_path = REFERENCE_DIR / "overview.png"
    if not ref_path.exists():
        pytest.skip(f"Reference screenshot missing: {ref_path}")

    url = f"{REACT_APP_URL.rstrip('/')}/?fixtures=1"
    page.goto(url, wait_until="networkidle", timeout=60_000)
    page.wait_for_timeout(1200)

    page.evaluate(FREEZE_AND_MASK_JS)
    page.wait_for_timeout(100)

    screenshot_bytes = page.screenshot(
        clip={"x": 0, "y": 0, "width": 1440, "height": 900},
    )
    current = Image.open(BytesIO(screenshot_bytes))
    ref = Image.open(ref_path)

    ratio, diff_img = _pixel_diff_ratio(ref, current)

    if ratio > DIFF_THRESHOLD:
        ARTIFACTS_DIR.mkdir(exist_ok=True)
        diff_path = ARTIFACTS_DIR / "overview.react.diff.png"
        diff_img.save(str(diff_path))
        pytest.fail(
            f"[overview-react] pixel diff {ratio:.4%} exceeds threshold {DIFF_THRESHOLD:.4%}. "
            f"Diff saved to {diff_path}"
        )

"""Visual regression tests: prototype screens vs frozen reference screenshots.

Skipped automatically if playwright is not installed.
Run: pytest tests/visual/ -v
"""
from io import BytesIO
from pathlib import Path

import pytest

pytest.importorskip("playwright", reason="playwright not installed — skipping visual tests")

from PIL import Image, ImageChops  # noqa: E402 (after importorskip guard)
import numpy as np  # noqa: E402

from tests.visual.conftest import FREEZE_AND_MASK_JS  # noqa: E402

REPO_ROOT = Path(__file__).parents[2]
REFERENCE_DIR = REPO_ROOT / "design" / "reference-screenshots"
ARTIFACTS_DIR = Path(__file__).parent / "_artifacts"
PROTOTYPE_PATH = REPO_ROOT / "design" / "new-design" / "Pipeline Monitor.html"

DIFF_THRESHOLD = 0.005  # 0.5% of total pixels

SCREENS = [
    pytest.param("overview", "1", id="overview"),
    pytest.param("queue",    "2", id="queue"),
    pytest.param("project",  "3", id="project"),
    pytest.param("worker",   "4", id="worker"),
]


def _pixel_diff_ratio(ref: Image.Image, current: Image.Image) -> tuple[float, Image.Image]:
    """Return (mismatch_ratio, diff_image). Pixels differing by > 10 on any channel count."""
    ref_rgb = ref.convert("RGB")
    cur_rgb = current.convert("RGB")
    diff = ImageChops.difference(ref_rgb, cur_rgb)
    arr = np.array(diff, dtype=np.uint8)
    mismatched = int(np.any(arr > 10, axis=2).sum())
    total = arr.shape[0] * arr.shape[1]
    return mismatched / total, diff


@pytest.mark.parametrize("screen,key", SCREENS)
def test_screen_visual(page, screen: str, key: str) -> None:
    ref_path = REFERENCE_DIR / f"{screen}.png"
    if not ref_path.exists():
        pytest.skip(f"Reference screenshot missing: {ref_path}. Run: python tests/visual/capture_references.py")

    prototype_url = PROTOTYPE_PATH.as_uri()
    page.goto(prototype_url, wait_until="networkidle", timeout=60_000)
    page.wait_for_timeout(1200)

    page.keyboard.press(key)
    page.wait_for_timeout(600)
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
        diff_path = ARTIFACTS_DIR / f"{screen}.diff.png"
        diff_img.save(str(diff_path))
        pytest.fail(
            f"[{screen}] pixel diff {ratio:.4%} exceeds threshold {DIFF_THRESHOLD:.4%}. "
            f"Diff saved to {diff_path}"
        )

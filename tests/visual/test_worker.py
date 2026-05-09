"""Visual regression test: WorkerDetail React screen vs reference screenshot.

Requires:
  - playwright installed  (pip install playwright && playwright install chromium)
  - Vite dev server running: cd web && npm run dev
  - Reference screenshot at design/reference-screenshots/worker.png

Run:
  cd web && npm run dev &
  pytest tests/visual/test_worker.py -v

Skipped automatically if playwright is not installed or the dev server is unreachable.
"""
from io import BytesIO
from pathlib import Path

import pytest

pytest.importorskip("playwright", reason="playwright not installed — skipping visual tests")

from PIL import Image, ImageChops  # noqa: E402
import numpy as np  # noqa: E402

from tests.visual.conftest import mask_vr_regions  # noqa: E402

REPO_ROOT = Path(__file__).parents[2]
REFERENCE_DIR = REPO_ROOT / "design" / "reference-screenshots"
ARTIFACTS_DIR = Path(__file__).parent / "_artifacts"

DEV_SERVER_URL = "http://localhost:5173/v2?fixtures=1"
DIFF_THRESHOLD = 0.005  # 0.5%


def _pixel_diff_ratio(ref: Image.Image, current: Image.Image) -> tuple[float, Image.Image]:
    ref_rgb = ref.convert("RGB")
    cur_rgb = current.convert("RGB")
    diff = ImageChops.difference(ref_rgb, cur_rgb)
    arr = np.array(diff, dtype=np.uint8)
    mismatched = int(np.any(arr > 10, axis=2).sum())
    total = arr.shape[0] * arr.shape[1]
    return mismatched / total, diff


def test_worker_screen_visual(page) -> None:
    ref_path = REFERENCE_DIR / "worker.png"
    if not ref_path.exists():
        pytest.skip(
            f"Reference screenshot missing: {ref_path}. "
            "Run: python tests/visual/capture_references.py"
        )

    try:
        page.goto(DEV_SERVER_URL, wait_until="networkidle", timeout=15_000)
    except Exception as exc:
        pytest.skip(f"Vite dev server not reachable at {DEV_SERVER_URL}: {exc}")

    # Wait for fixtures to hydrate
    page.wait_for_timeout(1200)

    # Navigate to workers screen via keyboard shortcut 4
    page.keyboard.press("4")
    page.wait_for_timeout(600)

    mask_vr_regions(page)
    page.wait_for_timeout(100)

    screenshot_bytes = page.screenshot(
        clip={"x": 0, "y": 0, "width": 1440, "height": 900},
    )
    current = Image.open(BytesIO(screenshot_bytes))
    ref = Image.open(ref_path)

    ratio, diff_img = _pixel_diff_ratio(ref, current)

    if ratio > DIFF_THRESHOLD:
        ARTIFACTS_DIR.mkdir(exist_ok=True)
        diff_path = ARTIFACTS_DIR / "worker.diff.png"
        diff_img.save(str(diff_path))
        pytest.fail(
            f"[worker] pixel diff {ratio:.4%} exceeds threshold {DIFF_THRESHOLD:.4%}. "
            f"Diff saved to {diff_path}"
        )

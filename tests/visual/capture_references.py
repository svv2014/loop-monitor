#!/usr/bin/env python3
"""One-shot CLI: capture reference screenshots from the frozen prototype.

Usage:
    python tests/visual/capture_references.py

Writes 4 PNGs into design/reference-screenshots/:
    overview.png, queue.png, project.png, worker.png

Re-running overwrites existing files (idempotent).
Requires: playwright (sync API), chromium browser installed.
    playwright install chromium
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
REFERENCE_DIR = REPO_ROOT / "design" / "reference-screenshots"
PROTOTYPE_PATH = REPO_ROOT / "design" / "new-design" / "Pipeline Monitor.html"
VIEWPORT = {"width": 1440, "height": 900}

# Screens: (filename_stem, keyboard_key_to_navigate, settle_ms)
SCREENS = [
    ("overview", "1", 800),
    ("queue",    "2", 600),
    ("project",  "3", 600),
    ("worker",   "4", 600),
]

FREEZE_AND_MASK_JS = """
() => {
    const maxId = setTimeout(() => {}, 0);
    for (let i = 0; i <= maxId; i++) {
        clearTimeout(i);
        clearInterval(i);
    }
    const s = document.createElement('style');
    s.textContent = '*, *::before, *::after { animation-play-state: paused !important; transition: none !important; }';
    document.head.appendChild(s);

    document.querySelectorAll('.topbar .right span').forEach(el => {
        if (/\\d{2}:\\d{2}:\\d{2}/.test(el.textContent)) {
            el.setAttribute('data-vr-mask', 'true');
        }
    });
    document.querySelectorAll('.topbar .right span').forEach(el => {
        if (/\\/min/.test(el.textContent)) {
            el.setAttribute('data-vr-mask', 'true');
        }
    });
    document.querySelectorAll('.dot').forEach(el => {
        el.setAttribute('data-vr-mask', 'true');
    });
    document.querySelectorAll('[class*="fresh"], [data-fresh]').forEach(el => {
        el.setAttribute('data-vr-mask', 'true');
    });
    document.querySelectorAll('[data-vr-mask="true"]').forEach(el => {
        Object.assign(el.style, {
            color: 'transparent',
            background: '#000000',
            boxShadow: 'none',
            opacity: '1',
        });
    });
}
"""


def capture(out_dir: Path = REFERENCE_DIR) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "ERROR: playwright is not installed. Run: pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(1)

    if not PROTOTYPE_PATH.exists():
        print(f"ERROR: prototype not found at {PROTOTYPE_PATH}", file=sys.stderr)
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    prototype_url = PROTOTYPE_PATH.as_uri()

    with sync_playwright() as pw:
        # --allow-file-access-from-files: Babel (text/babel scripts) loads .jsx via XHR
        # from file:// origin; without this flag Chromium blocks the requests (CORS null origin).
        browser = pw.chromium.launch(headless=True, args=["--allow-file-access-from-files"])
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()

        print(f"Loading prototype: {prototype_url}")
        # Use networkidle so CDN scripts (React/Babel) fully load
        page.goto(prototype_url, wait_until="networkidle", timeout=60_000)
        # Wait for React to mount; the live event simulator fires every 2 000 ms so
        # 1 200 ms is safely before the first event — freeze immediately after to get
        # a deterministic initial state for every screen.
        page.wait_for_timeout(1200)
        page.evaluate(FREEZE_AND_MASK_JS)

        for stem, key, _ in SCREENS:
            print(f"  Capturing {stem}.png …", end=" ", flush=True)
            # Navigate to the target screen via keyboard shortcut (timers already frozen)
            page.keyboard.press(key)
            page.wait_for_timeout(300)
            out_path = out_dir / f"{stem}.png"
            clip = {"x": 0, "y": 0, "width": VIEWPORT["width"], "height": VIEWPORT["height"]}
            page.screenshot(path=str(out_path), clip=clip)
            print(f"saved → {out_path.relative_to(REPO_ROOT)}")

        context.close()
        browser.close()

    print("Done. Commit design/reference-screenshots/ to lock the baseline.")


if __name__ == "__main__":
    capture()

# Visual Regression Suite

Playwright-Python pixel-diff tests that gate UI-migration PRs against frozen reference
screenshots of the prototype at `design/new-design/`.

## Pixel-diff library choice

This suite uses **Pillow** (`PIL.ImageChops.difference`) instead of `pixelmatch`.
Rationale: Pillow is a common dependency with no native extensions, making it easy to
install in all environments. A pixel is counted as "different" when any RGB channel
differs by more than 10 (out of 255), which tolerates minor anti-aliasing variance
while catching real layout regressions. The 0.5% threshold matches the ADR.

## Prerequisites

```bash
pip install -r requirements-dev.txt
playwright install chromium
```

> **Note on `--allow-file-access-from-files`:** The prototype loads its `.jsx` source files
> via Babel's XHR loader. When opened as a `file://` URL, Chromium blocks those requests
> (null CORS origin). Both the capture script and the pytest fixture pass
> `--allow-file-access-from-files` to Chromium to allow this. The flag is safe for testing
> purposes and has no effect on production code.

## Capturing / refreshing reference screenshots

Run this once (or whenever the frozen prototype changes) and commit the results:

```bash
python tests/visual/capture_references.py
git add design/reference-screenshots/
git commit -m "chore: refresh visual regression baselines"
```

The script opens `design/new-design/Pipeline Monitor.html` headlessly at 1440×900,
navigates to each of the 4 screens, applies masking, and writes:

| File | Screen |
|------|--------|
| `design/reference-screenshots/overview.png` | Overview (key `1`) |
| `design/reference-screenshots/queue.png`    | Queue (key `2`) |
| `design/reference-screenshots/project.png`  | Project detail (key `3`) |
| `design/reference-screenshots/worker.png`   | Worker detail (key `4`) |

## Running the suite

```bash
pytest tests/visual/ -v
```

Tests are **skipped automatically** when `playwright` is not installed, so running
`pytest tests/` on a standard dev machine without Playwright browsers installed does
not fail.

## Mask regions

The following dynamic regions are masked (overwritten with solid black `#000000`)
before each screenshot, ensuring diffs are stable across renders:

| Region | Selector / Detection |
|--------|----------------------|
| Live clock (`HH:MM:SS`) | `.topbar .right span` whose text matches `\d{2}:\d{2}:\d{2}` |
| Events-per-minute counter | `.topbar .right span` whose text contains `/min` |
| Pulse `.dot` animations | `.dot` |
| Fresh-row flash | `[class*="fresh"], [data-fresh]` |

All CSS animations are paused and all JS timers are cleared before screenshotting so
the page is fully static at capture time.

## Failure artifacts

When a test fails, diff images are saved to `tests/visual/_artifacts/<screen>.diff.png`.
This directory is `.gitignore`d and is uploaded as a CI artifact on failure.

## CI integration

The workflow `.github/workflows/visual-diff.yml` runs these tests on pull requests
labeled `ui-migration`. It uploads `tests/visual/_artifacts/` as the `visual-diff`
artifact when any test fails.

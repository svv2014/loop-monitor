pytest_plugins = []

try:
    import playwright  # noqa: F401
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

import pytest

VIEWPORT = {"width": 1440, "height": 900}


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    # --allow-file-access-from-files: Babel loads .jsx via XHR from file:// origin;
    # without this flag Chromium blocks those requests (CORS null origin).
    return {**browser_type_launch_args, "headless": True, "args": ["--allow-file-access-from-files"]}


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": VIEWPORT}


# JS injected before every screenshot: freezes timers/animations and marks VR regions.
FREEZE_AND_MASK_JS = """
() => {
    // Stop all timers so live-data and clocks freeze
    const maxId = setTimeout(() => {}, 0);
    for (let i = 0; i <= maxId; i++) {
        clearTimeout(i);
        clearInterval(i);
    }

    // Pause CSS animations (pulse dots, row-flash)
    const s = document.createElement('style');
    s.textContent = '*, *::before, *::after { animation-play-state: paused !important; transition: none !important; }';
    document.head.appendChild(s);

    // Mark live clock spans
    document.querySelectorAll('.topbar .right span').forEach(el => {
        if (/\\d{2}:\\d{2}:\\d{2}/.test(el.textContent)) {
            el.setAttribute('data-vr-mask', 'true');
        }
    });
    // Mark event-rate counter (changes every render)
    document.querySelectorAll('.topbar .right span').forEach(el => {
        if (/\\/min/.test(el.textContent)) {
            el.setAttribute('data-vr-mask', 'true');
        }
    });
    // Mark pulse dots
    document.querySelectorAll('.dot').forEach(el => {
        el.setAttribute('data-vr-mask', 'true');
    });
    // Mark fresh-row elements
    document.querySelectorAll('[class*="fresh"], [data-fresh]').forEach(el => {
        el.setAttribute('data-vr-mask', 'true');
    });

    // Overwrite masked regions with opaque black so diffs are stable
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


def mask_vr_regions(page) -> None:
    """Apply FREEZE_AND_MASK_JS to the loaded page."""
    page.evaluate(FREEZE_AND_MASK_JS)

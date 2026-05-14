from scripts.dashboard import (
    _since,
    _event_glyph,
    _hbar,
    _colorize,
    _role_color,
    render_feed_items,
    render_leaderboard_items,
    render_banner,
    CARD_INNER,
    NARROW_COLS,
    _V,
    _H,
    _TL,
    _TR,
    _BL,
    _BR,
    _LT,
    _RT,
)


# ── _since ────────────────────────────────────────────────────────────────────

def test_since_seconds_minutes_hours_days():
    assert _since({"age_seconds": 5}) == "5s"
    assert _since({"age_seconds": 120}) == "2m"
    assert _since({"age_seconds": 3700}) == "1h"
    assert _since({"age_seconds": 90000}) == "1d"


def test_since_unknown():
    assert _since({}) == "?"


def test_since_falls_back_to_created_at():
    out = _since({"created_at": "2026-04-30T12:00:00+00:00"})
    assert out and out != "?"


# ── _event_glyph ──────────────────────────────────────────────────────────────

def test_event_glyph_known_suffixes():
    assert _event_glyph("dev_done") == "✓"
    assert _event_glyph("dev_fail") == "✗"
    assert _event_glyph("dev_start") == "◉"
    assert _event_glyph("qa_pass") == "✓"
    assert _event_glyph("qa_skip") == "→"


def test_event_glyph_judge():
    assert _event_glyph("judge") == "★"


def test_event_glyph_unknown_returns_bullet():
    assert _event_glyph("something_unknown") == "•"
    assert _event_glyph("") == "•"
    assert _event_glyph(None) == "•"


# ── _hbar ─────────────────────────────────────────────────────────────────────

def test_hbar_default_corners():
    bar = _hbar(10)
    assert bar.startswith(_TL)
    assert bar.endswith(_TR)
    assert len(bar) == 10  # Unicode chars are single code-points


def test_hbar_custom_corners():
    bar = _hbar(6, _LT, _RT)
    assert bar.startswith(_LT)
    assert bar.endswith(_RT)
    assert _H * 4 in bar


# ── _colorize ─────────────────────────────────────────────────────────────────

def test_colorize_with_color():
    out = _colorize("\x1b[34m", "hello", True)
    assert "\x1b[34m" in out
    assert "hello" in out
    assert "\x1b[0m" in out


def test_colorize_without_color():
    out = _colorize("\x1b[34m", "hello", False)
    assert out == "hello"


# ── _role_color ───────────────────────────────────────────────────────────────

def test_role_color_known_roles():
    assert _role_color("dev") == "\x1b[34m"
    assert _role_color("judge") == "\x1b[35m"
    assert _role_color("qa") == "\x1b[36m"
    assert _role_color("builder") == "\x1b[32m"


def test_role_color_unknown_returns_default():
    assert _role_color("unknown") == "\x1b[37m"
    assert _role_color("") == "\x1b[37m"
    assert _role_color(None) == "\x1b[37m"


# ── render_feed_items ─────────────────────────────────────────────────────────

def test_render_feed_items_empty():
    assert render_feed_items([]) == []


def test_render_feed_items_truncates_to_8():
    rows = [{"role": "dev", "event_type": "dev_done", "issue_number": i} for i in range(12)]
    items = render_feed_items(rows)
    assert len(items) == 8


def test_render_feed_items_includes_role_and_glyph():
    rows = [{"role": "builder", "event_type": "dev_start", "issue_number": 42}]
    items = render_feed_items(rows)
    assert len(items) == 1
    line, role = items[0]
    assert role == "builder"
    assert "◉" in line
    assert "builder" in line
    assert "#42" in line


def test_render_feed_items_pr_number():
    rows = [{"role": "qa", "event_type": "qa_pass", "pr_number": 99}]
    items = render_feed_items(rows)
    line, _ = items[0]
    assert "PR99" in line


# ── render_leaderboard_items ──────────────────────────────────────────────────

def test_render_leaderboard_empty():
    lines = render_leaderboard_items([])
    assert lines == ["  No scores yet."]


def test_render_leaderboard_top_5():
    board = [{"role": f"r{i}", "total_points": 100 - i * 10} for i in range(10)]
    lines = render_leaderboard_items(board)
    assert len(lines) == 5
    assert "1." in lines[0]
    assert "r0" in lines[0]


def test_render_leaderboard_handles_none_points():
    board = [{"role": "dev", "total_points": None}]
    lines = render_leaderboard_items(board)
    assert "0" in lines[0]


# ── render_banner ─────────────────────────────────────────────────────────────

def test_render_banner_structure():
    lines = render_banner("http://localhost:18792", 80, False)
    assert len(lines) == 5
    # top border
    assert lines[0].startswith(_TL)
    assert lines[0].endswith(_TR)
    # divider at bottom
    assert lines[4].startswith(_LT)
    assert lines[4].endswith(_RT)


def test_render_banner_contains_title_and_url():
    lines = render_banner("http://localhost:18792", 80, False)
    combined = "\n".join(lines)
    assert "LOOP MONITOR" in combined
    assert "localhost:18792" in combined


def test_render_banner_contains_utc_and_local():
    lines = render_banner("http://testhost", 80, False)
    combined = "\n".join(lines)
    assert "UTC" in combined
    assert "Local" in combined


def test_render_banner_all_lines_same_width():
    cols = 80
    lines = render_banner("http://x", cols, False)
    # Unicode box chars are 1 display column each; line length == cols
    for line in lines:
        assert len(line) == cols, f"Expected width {cols}, got {len(line)}: {line!r}"

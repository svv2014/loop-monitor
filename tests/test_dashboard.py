from scripts.dashboard import (
    _since,
    _strip_ansi,
    _box_top,
    _box_bot,
    _box_sep,
    _box_row,
    _center_padded,
    render_banner,
    render_cards,
    render_feed,
    render_leaderboard,
    render_verdict,
    render_simple,
)


# ── _since (unchanged helper) ─────────────────────────────────────────────────

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


# ── _strip_ansi ───────────────────────────────────────────────────────────────

def test_strip_ansi_removes_codes():
    assert _strip_ansi("\x1b[32mgreen\x1b[0m") == "green"
    assert _strip_ansi("plain") == "plain"
    assert _strip_ansi("\x1b[1m\x1b[33mbold yellow\x1b[0m") == "bold yellow"


def test_strip_ansi_empty():
    assert _strip_ansi("") == ""


# ── Box drawing helpers ───────────────────────────────────────────────────────

def test_box_top_width():
    result = _box_top(10)
    assert result.startswith("┌")
    assert result.endswith("┐")
    assert len(result) == 10


def test_box_bot_width():
    result = _box_bot(10)
    assert result.startswith("└")
    assert result.endswith("┘")
    assert len(result) == 10


def test_box_sep_width():
    result = _box_sep(10)
    assert result.startswith("├")
    assert result.endswith("┤")
    assert len(result) == 10


def test_box_row_pads_content():
    result = _box_row("hi", 10)
    assert result.startswith("│")
    assert result.endswith("│")
    visible = _strip_ansi(result)
    assert len(visible) == 10


def test_center_padded_centers():
    result = _center_padded("HI", 10)
    assert "HI" in result
    assert len(result) == 10
    assert result.startswith("    ")  # 4 spaces of left padding for 2-char text in 10-wide


# ── render_banner ─────────────────────────────────────────────────────────────

def test_render_banner_contains_loop_monitor():
    lines = render_banner("http://localhost:18792", 80)
    combined = "\n".join(lines)
    assert "LOOP MONITOR" in _strip_ansi(combined)


def test_render_banner_contains_url():
    lines = render_banner("http://localhost:18792", 80)
    combined = "\n".join(lines)
    assert "http://localhost:18792" in combined


def test_render_banner_contains_utc():
    lines = render_banner("http://localhost:18792", 80)
    combined = "\n".join(lines)
    assert "UTC" in combined


def test_render_banner_uses_box_chars():
    lines = render_banner("http://localhost:18792", 80)
    combined = "\n".join(lines)
    assert "┌" in combined
    assert "┘" in combined or "┤" in combined


def test_render_banner_width():
    width = 80
    lines = render_banner("http://localhost:18792", width)
    for line in lines:
        visible = _strip_ansi(line)
        assert len(visible) == width, f"Expected width {width}, got {len(visible)}: {visible!r}"


# ── render_cards ──────────────────────────────────────────────────────────────

def test_render_cards_empty():
    lines = render_cards([], 80)
    combined = "\n".join(lines)
    assert "No projects." in combined


def test_render_cards_shows_project_name():
    projects = [{"project": "Lint", "total_points": 52, "status": "idle",
                 "age_seconds": 300}]
    lines = render_cards(projects, 80)
    combined = _strip_ansi("\n".join(lines))
    assert "Lint" in combined


def test_render_cards_shows_points():
    projects = [{"project": "Build", "total_points": 185, "status": "busy",
                 "age_seconds": 60}]
    lines = render_cards(projects, 80)
    combined = _strip_ansi("\n".join(lines))
    assert "185" in combined


def test_render_cards_shows_status_glyph():
    projects = [{"project": "Test", "total_points": 0, "status": "wait",
                 "age_seconds": 10}]
    lines = render_cards(projects, 80)
    combined = "\n".join(lines)
    assert "◉" in combined


# ── render_feed ───────────────────────────────────────────────────────────────

def test_render_feed_empty():
    lines = render_feed([], col_width=40)
    combined = "\n".join(lines)
    assert "LIVE FEED" in _strip_ansi(combined)


def test_render_feed_shows_events():
    events = [
        {"role": "builder", "event_type": "dev_start", "issue_number": 42, "age_seconds": 30},
    ]
    lines = render_feed(events, col_width=40)
    combined = _strip_ansi("\n".join(lines))
    assert "builder" in combined
    assert "#42" in combined


def test_render_feed_role_glyph_builder():
    events = [{"role": "builder", "event_type": "dev_done", "age_seconds": 10}]
    lines = render_feed(events, col_width=40)
    combined = "\n".join(lines)
    assert "⚙" in combined


def test_render_feed_role_glyph_judge():
    events = [{"role": "judge", "event_type": "verdict", "age_seconds": 10}]
    lines = render_feed(events, col_width=40)
    combined = "\n".join(lines)
    assert "★" in combined


def test_render_feed_respects_limit():
    events = [{"role": "tester", "event_type": "test_done", "age_seconds": i}
              for i in range(10)]
    lines = render_feed(events, col_width=60, limit=3)
    event_lines = [l for l in lines if "•" in l]
    assert len(event_lines) == 3


# ── render_leaderboard ────────────────────────────────────────────────────────

def test_render_leaderboard_empty():
    lines = render_leaderboard([], col_width=30)
    combined = "\n".join(lines)
    assert "LEADERBOARD" in _strip_ansi(combined)


def test_render_leaderboard_shows_ranks():
    board = [
        {"role": "sonnet", "total_points": 185},
        {"role": "opus", "total_points": 120},
    ]
    lines = render_leaderboard(board, col_width=30)
    combined = _strip_ansi("\n".join(lines))
    assert "1." in combined
    assert "2." in combined
    assert "185" in combined
    assert "120" in combined


def test_render_leaderboard_limit():
    board = [{"role": f"r{i}", "total_points": i} for i in range(10)]
    lines = render_leaderboard(board, col_width=30, limit=5)
    rank_lines = [l for l in lines if l.strip().startswith(tuple("123456789"))]
    assert len(rank_lines) == 5


# ── render_verdict ────────────────────────────────────────────────────────────

def test_render_verdict_no_judge_events():
    feed = [{"role": "builder", "event_type": "dev_done", "age_seconds": 10}]
    result = render_verdict(feed, 80)
    assert result == []


def test_render_verdict_extracts_judge():
    feed = [{"role": "judge", "detail": "Clean merge. Full score.", "age_seconds": 5}]
    result = render_verdict(feed, 80)
    assert len(result) > 0
    combined = _strip_ansi("\n".join(result))
    assert "Clean merge" in combined


def test_render_verdict_truncates_to_width():
    long_detail = "A" * 500
    feed = [{"role": "judge", "detail": long_detail, "age_seconds": 1}]
    result = render_verdict(feed, 80)
    for line in result:
        assert len(_strip_ansi(line)) <= 80


# ── render_simple ─────────────────────────────────────────────────────────────

def test_render_simple_contains_loop_monitor():
    out = render_simple("http://localhost:18792", [], [], [])
    assert "LOOP MONITOR" in out


def test_render_simple_no_projects():
    out = render_simple("http://localhost:18792", [], [], [])
    assert "No projects." in out


def test_render_simple_no_feed():
    out = render_simple("http://localhost:18792", [], [], [])
    assert "No recent events." in out


def test_render_simple_shows_projects():
    board = [{"project": "Lint", "total_points": 52, "role": "builder"}]
    out = render_simple("http://localhost:18792", [], board, [])
    assert "Lint" in out
    assert "52" in out


def test_render_simple_shows_feed():
    feed = [{"role": "tester", "event_type": "test_pass", "age_seconds": 60}]
    out = render_simple("http://localhost:18792", [], [], feed)
    assert "tester" in out
    assert "test_pass" in out


def test_render_simple_no_box_chars():
    board = [{"project": "X", "total_points": 1, "role": "dev"}]
    feed = [{"role": "dev", "event_type": "dev_done", "age_seconds": 10}]
    out = render_simple("http://localhost:18792", [], board, feed)
    assert "┌" not in out
    assert "┐" not in out

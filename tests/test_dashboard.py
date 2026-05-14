from scripts.dashboard import (
    _project_points,
    _project_state,
    _role_glyph,
    _since,
    colorize,
    render_banner,
    render_cards,
    render_feed,
    render_leaderboard,
    render_narrow,
    render_verdict,
    render_wide,
)


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


def test_role_glyph_known():
    assert _role_glyph("builder") == "◉"
    assert _role_glyph("tester") == "✓"
    assert _role_glyph("judge") == "⚖"


def test_role_glyph_unknown():
    assert _role_glyph("unknown_role") == "•"


def test_colorize_no_color():
    assert colorize("builder", "hello", use_color=False) == "hello"


def test_colorize_with_color():
    result = colorize("builder", "hello", use_color=True)
    assert "hello" in result
    assert "\x1b[" in result


def test_render_banner_structure():
    lines = render_banner("http://localhost:18792", 80, use_color=False)
    assert lines[0].startswith("┌")
    assert lines[0].endswith("┐")
    assert "LOOP MONITOR" in lines[1]
    assert "localhost:18792" in lines[2]
    assert lines[3].startswith("├")


def test_render_banner_width():
    cols = 80
    lines = render_banner("http://localhost:18792", cols, use_color=False)
    for line in lines:
        assert len(line) == cols, f"expected {cols}, got {len(line)}: {line!r}"


def test_project_state_idle():
    assert _project_state("foo", []) == "idle"


def test_project_state_busy():
    active = [{"project": "foo", "event_type": "dev_start"}]
    assert _project_state("foo", active) == "busy"


def test_project_state_wait():
    active = [{"project": "foo", "event_type": "dev_wait"}]
    assert _project_state("foo", active) == "wait"


def test_project_points_aggregates_roles():
    board = [
        {"project": "foo", "role": "builder", "total_points": 100},
        {"project": "foo", "role": "tester", "total_points": 50},
        {"project": "bar", "role": "builder", "total_points": 200},
    ]
    assert _project_points("foo", board) == 150
    assert _project_points("bar", board) == 200
    assert _project_points("baz", board) == 0


def test_project_points_handles_none():
    board = [{"project": "foo", "role": "builder", "total_points": None}]
    assert _project_points("foo", board) == 0


def test_render_cards_empty():
    assert render_cards([], [], [], [], 80, use_color=False) == []


def test_render_cards_single_project_shows_name_and_pts():
    board = [{"project": "loop", "role": "builder", "total_points": 42}]
    lines = render_cards(["loop"], [], board, [], 80, use_color=False)
    content = "\n".join(lines)
    assert "loop" in content
    assert "42 pts" in content
    assert "idle" in content


def test_render_cards_busy_state():
    active = [{"project": "loop", "event_type": "dev_start"}]
    lines = render_cards(["loop"], active, [], [], 80, use_color=False)
    assert any("busy" in line for line in lines)


def test_render_cards_line_width():
    board = [{"project": "p", "role": "r", "total_points": 10}]
    lines = render_cards(["p"], [], board, [], 80, use_color=False)
    for line in lines:
        assert len(line) == 80, f"expected 80, got {len(line)}: {line!r}"


def test_render_feed_empty():
    lines = render_feed([], 40, use_color=False)
    assert any("LIVE FEED" in line for line in lines)
    assert any("No recent events" in line for line in lines)


def test_render_feed_shows_event():
    events = [
        {"project": "loop", "role": "builder", "event_type": "dev_start",
         "issue_number": 42, "pr_number": None, "age_seconds": 10},
    ]
    lines = render_feed(events, 40, use_color=False)
    content = "\n".join(lines)
    assert "dev_start" in content
    assert "#42" in content


def test_render_feed_respects_limit():
    events = [
        {"project": f"p{i}", "role": "builder", "event_type": "dev_done",
         "issue_number": i, "pr_number": None, "age_seconds": i}
        for i in range(10)
    ]
    lines = render_feed(events, 40, use_color=False, limit=3)
    assert len(lines) == 4  # header + 3 events


def test_render_feed_header_padded_to_col_w():
    col_w = 40
    lines = render_feed([], col_w, use_color=False)
    assert len(lines[0]) == col_w


def test_render_feed_empty_line_padded_to_col_w():
    col_w = 40
    lines = render_feed([], col_w, use_color=False)
    for line in lines:
        assert len(line) == col_w


def test_render_leaderboard_empty():
    lines = render_leaderboard([], 40, use_color=False)
    assert any("LEADERBOARD" in line for line in lines)
    assert any("No scores yet" in line for line in lines)


def test_render_leaderboard_sorted_by_points():
    board = [
        {"role": "tester", "project": "p", "total_points": 50},
        {"role": "builder", "project": "p", "total_points": 185},
        {"role": "reviewer", "project": "p", "total_points": 120},
    ]
    lines = render_leaderboard(board, 40, use_color=False)
    content = "\n".join(lines)
    assert content.index("185") < content.index("120") < content.index("50")


def test_render_leaderboard_respects_limit():
    board = [{"role": f"r{i}", "project": "p", "total_points": i * 10} for i in range(10)]
    lines = render_leaderboard(board, 40, use_color=False, limit=3)
    assert len(lines) == 4  # header + 3 entries


def test_render_leaderboard_padded_to_col_w():
    board = [{"role": "builder", "project": "p", "total_points": 100}]
    col_w = 40
    lines = render_leaderboard(board, col_w, use_color=False)
    for line in lines:
        assert len(line) == col_w


def test_render_verdict_none_when_no_judge():
    events = [{"role": "builder", "event_type": "dev_done", "detail": "done",
               "pr_number": None, "issue_number": None}]
    assert render_verdict(events, 80) is None


def test_render_verdict_found_with_pr():
    events = [{"role": "judge", "event_type": "judge_done",
               "detail": "Clean merge, full score",
               "pr_number": 42, "issue_number": None}]
    verdict = render_verdict(events, 80)
    assert verdict is not None
    assert "PR #42" in verdict
    assert "Clean merge" in verdict
    assert verdict.startswith("│")
    assert verdict.endswith("│")


def test_render_verdict_width():
    events = [{"role": "judge", "event_type": "judge",
               "detail": "All good", "pr_number": 1, "issue_number": None}]
    cols = 80
    verdict = render_verdict(events, cols)
    assert verdict is not None
    assert len(verdict) == cols


def test_render_verdict_skips_empty_detail():
    events = [
        {"role": "judge", "event_type": "judge", "detail": "", "pr_number": 1, "issue_number": None},
        {"role": "judge", "event_type": "judge", "detail": "real verdict", "pr_number": 2, "issue_number": None},
    ]
    verdict = render_verdict(events, 80)
    assert verdict is not None
    assert "real verdict" in verdict


def test_render_wide_structure():
    board = [{"project": "loop", "role": "builder", "total_points": 100, "verdict_count": 3}]
    feed = [{"project": "loop", "role": "builder", "event_type": "dev_done",
             "age_seconds": 60, "issue_number": 1, "pr_number": None, "detail": "done", "status": "done"}]
    result = render_wide([], board, feed, "http://localhost:18792", 80, use_color=False)
    assert "LOOP MONITOR" in result
    assert "LIVE FEED" in result
    assert "LEADERBOARD" in result
    assert result.endswith("┘")


def test_render_wide_line_widths():
    board = [{"project": "loop", "role": "builder", "total_points": 50}]
    cols = 80
    result = render_wide([], board, [], "http://localhost", cols, use_color=False)
    for line in result.splitlines():
        assert len(line) == cols, f"expected {cols}, got {len(line)}: {line!r}"


def test_render_narrow_structure():
    board = [{"project": "loop", "role": "builder", "total_points": 100, "verdict_count": 3}]
    feed = [{"project": "loop", "role": "builder", "event_type": "dev_done",
             "age_seconds": 60, "issue_number": 1, "pr_number": None, "detail": "done", "status": "done"}]
    result = render_narrow([], board, feed, "http://localhost:18792", use_color=False)
    assert "LOOP MONITOR" in result
    assert "LIVE FEED" in result
    assert "LEADERBOARD" in result


def test_render_narrow_no_color():
    result = render_narrow([], [], [], "http://localhost", use_color=False)
    assert "\x1b[" not in result


def test_render_wide_with_judge_verdict():
    feed = [
        {"project": "loop", "role": "judge", "event_type": "judge",
         "age_seconds": 5, "issue_number": None, "pr_number": 7,
         "detail": "Solid spec, clean merge.", "status": "done"},
    ]
    result = render_wide([], [], feed, "http://localhost", 80, use_color=False)
    assert "JUDGE VERDICT" in result
    assert "PR #7" in result

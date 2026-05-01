import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.dashboard import format_active, format_board, format_feed, _since


def test_format_active_empty():
    out = format_active([])
    assert "ACTIVE WORKERS" in out
    assert "No active workers." in out


def test_format_active_rows():
    rows = [
        {"project": "loop-monitor", "role": "builder", "model": "sonnet",
         "event_type": "dev_start", "issue_number": 42, "pr_number": None,
         "detail": "working", "created_at": "2026-04-30T12:00:00+00:00"},
    ]
    out = format_active(rows)
    assert "loop-monitor" in out
    assert "builder" in out
    assert "dev_start" in out
    assert "#42" in out


def test_format_active_handles_missing_fields():
    rows = [{"project": "p", "role": "r"}]  # no event_type, model, ids, etc.
    out = format_active(rows)
    assert "p" in out
    assert "r" in out


def test_format_board_empty():
    out = format_board([])
    assert "PROJECT STATUS" in out
    assert "No project scores yet." in out


def test_format_board_rows():
    rows = [
        {"project": "loop-monitor", "role": "builder", "model": "sonnet",
         "total_points": 185, "verdict_count": 7},
    ]
    out = format_board(rows)
    assert "185" in out
    assert "7" in out


def test_format_board_handles_none_points():
    rows = [{"project": "p", "role": "r", "model": None,
             "total_points": None, "verdict_count": None}]
    out = format_board(rows)
    assert "p" in out
    assert "0" in out


def test_format_feed_empty():
    out = format_feed([])
    assert "RECENT FEED" in out
    assert "No recent events." in out


def test_format_feed_rows_truncates_to_limit():
    rows = [
        {"project": f"p{i}", "role": "builder", "event_type": "dev_done",
         "issue_number": i, "detail": "ok", "age_seconds": i, "status": "done"}
        for i in range(10)
    ]
    out = format_feed(rows, limit=5)
    # 1 header + 5 rows
    assert len(out.splitlines()) == 6
    assert "p0" in out
    assert "p4" in out
    assert "p5" not in out


def test_format_feed_uses_age_seconds():
    rows = [{"project": "p", "role": "r", "event_type": "x_done",
             "age_seconds": 90, "status": "done"}]
    out = format_feed(rows)
    assert "1m" in out


def test_since_seconds_minutes_hours_days():
    assert _since({"age_seconds": 5}) == "5s"
    assert _since({"age_seconds": 120}) == "2m"
    assert _since({"age_seconds": 3700}) == "1h"
    assert _since({"age_seconds": 90000}) == "1d"


def test_since_unknown():
    assert _since({}) == "?"


def test_since_falls_back_to_created_at():
    # any valid ISO timestamp parses without crashing
    out = _since({"created_at": "2026-04-30T12:00:00+00:00"})
    assert out and out != "?"

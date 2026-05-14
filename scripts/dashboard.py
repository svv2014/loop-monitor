#!/usr/bin/env python3
"""Terminal dashboard for Loop Monitor — stdlib-only TUI over the local REST API."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

DEFAULT_URL = "http://127.0.0.1:18792"
DEFAULT_INTERVAL = 10
HTTP_TIMEOUT = 5
CLEAR = "\x1b[2J\x1b[H"

# ANSI colors (basic 8 + bold, TTY-only)
ANSI_RESET = "\x1b[0m"
ANSI_BOLD = "\x1b[1m"
ANSI_GREEN = "\x1b[32m"
ANSI_YELLOW = "\x1b[33m"
ANSI_BLUE = "\x1b[34m"
ANSI_CYAN = "\x1b[36m"
ANSI_RED = "\x1b[31m"
ANSI_MAGENTA = "\x1b[35m"

ROLE_COLORS: dict[str, str] = {
    "dev": ANSI_GREEN,
    "builder": ANSI_GREEN,
    "reviewer": ANSI_BLUE,
    "tester": ANSI_CYAN,
    "judge": ANSI_YELLOW,
    "po": ANSI_MAGENTA,
    "planner": ANSI_MAGENTA,
}

ROLE_GLYPHS: dict[str, str] = {
    "dev": "⚙",
    "builder": "⚙",
    "reviewer": "◎",
    "tester": "✓",
    "judge": "★",
    "po": "◆",
    "planner": "◆",
}

STATUS_GLYPHS: dict[str, str] = {
    "busy": "◉",
    "idle": "◉",
    "wait": "◉",
}

STATUS_COLORS: dict[str, str] = {
    "busy": ANSI_GREEN,
    "idle": ANSI_CYAN,
    "wait": ANSI_YELLOW,
}


def _use_color() -> bool:
    return sys.stdout.isatty()


def _term_cols() -> int:
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


def colorize(color: str, text: str) -> str:
    if not _use_color():
        return text
    return f"{color}{text}{ANSI_RESET}"


def bold(text: str) -> str:
    if not _use_color():
        return text
    return f"{ANSI_BOLD}{text}{ANSI_RESET}"


def fetch_json(base_url: str, path: str) -> Any:
    url = base_url.rstrip("/") + path
    with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT) as resp:
        if resp.status != 200:
            raise urllib.error.HTTPError(url, resp.status, "non-200", resp.headers, None)
        return json.loads(resp.read().decode("utf-8"))


def _truncate(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "…"


def _since(row: dict) -> str:
    age = row.get("age_seconds")
    if age is None:
        created = row.get("created_at")
        if not created:
            return "?"
        try:
            dt = datetime.fromisoformat(str(created).replace(" ", "T"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age = int((datetime.now(timezone.utc) - dt).total_seconds())
        except Exception:
            return "?"
    age = int(age)
    if age < 60:
        return f"{age}s"
    if age < 3600:
        return f"{age // 60}m"
    if age < 86400:
        return f"{age // 3600}h"
    return f"{age // 86400}d"


# ── Box-drawing helpers ───────────────────────────────────────────────────────

def _box_top(width: int) -> str:
    return "┌" + "─" * (width - 2) + "┐"


def _box_bot(width: int) -> str:
    return "└" + "─" * (width - 2) + "┘"


def _box_sep(width: int) -> str:
    return "├" + "─" * (width - 2) + "┤"


def _box_row(content: str, width: int) -> str:
    """Pad content to fit inside a box of given total width."""
    inner = width - 4  # two border chars + two spaces
    # strip ANSI for length calculation
    visible = _strip_ansi(content)
    pad = max(0, inner - len(visible))
    return "│ " + content + " " * pad + " │"


def _strip_ansi(s: str) -> str:
    """Remove ANSI escape codes for length calculations."""
    import re
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


# ── Section renderers ─────────────────────────────────────────────────────────

def render_banner(base_url: str, width: int) -> list[str]:
    now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")
    now_local = datetime.now().strftime("%H:%M local")
    time_str = f"{now_utc}  {now_local}"

    title = bold("LOOP MONITOR")
    url_line = base_url
    lines = [
        _box_top(width),
        _box_row(_center_padded(title, width - 4), width),
        _box_row(_center_padded(url_line, width - 4), width),
        _box_row(_center_padded(time_str, width - 4), width),
        _box_sep(width),
    ]
    return lines


def _center_padded(text: str, width: int) -> str:
    visible_len = len(_strip_ansi(text))
    total_pad = max(0, width - visible_len)
    left_pad = total_pad // 2
    right_pad = total_pad - left_pad
    return " " * left_pad + text + " " * right_pad


def render_cards(projects: list[dict], width: int) -> list[str]:
    """One box per project; wrap to next row when line would exceed width."""
    if not projects:
        return [_box_row("  No projects.", width), _box_row("", width)]

    CARD_W = 14  # inner width of each card box (total card = CARD_W + 2 borders)
    CARD_TOTAL = CARD_W + 2
    GAP = 2
    cards_per_row = max(1, (width - 2) // (CARD_TOTAL + GAP))

    def make_card(p: dict) -> list[str]:
        name = _truncate(p.get("project") or p.get("name") or "?", CARD_W)
        pts = int(p.get("total_points") or p.get("score") or 0)
        status = (p.get("status") or "idle").lower()
        glyph = STATUS_GLYPHS.get(status, "◉")
        sc = STATUS_COLORS.get(status, "")
        age = _since(p)
        status_line = colorize(sc, f"{glyph} {status:<4}")
        pts_line = f"{pts} pts"
        age_line = age

        rows = [
            "┌" + "─" * CARD_W + "┐",
            "│" + _pad_inner(bold(name), CARD_W) + "│",
            "│" + _pad_inner(status_line, CARD_W) + "│",
            "│" + _pad_inner(pts_line, CARD_W) + "│",
            "│" + _pad_inner(age_line, CARD_W) + "│",
            "└" + "─" * CARD_W + "┘",
        ]
        return rows

    def _pad_inner(text: str, w: int) -> str:
        visible = len(_strip_ansi(text))
        pad = max(0, w - visible)
        return " " + text + " " * (pad - 1 if pad > 0 else 0)

    lines: list[str] = []
    for chunk_start in range(0, len(projects), cards_per_row):
        chunk = projects[chunk_start : chunk_start + cards_per_row]
        cards = [make_card(p) for p in chunk]
        card_height = len(cards[0])
        for row_i in range(card_height):
            row_parts = [c[row_i] for c in cards]
            combined = ("  " + "  ".join(row_parts))
            # Pad the whole thing to fit box interior
            inner_w = width - 4
            vis = len(_strip_ansi(combined))
            padded = combined + " " * max(0, inner_w - vis)
            lines.append("│ " + padded + " │")
        lines.append(_box_row("", width))

    return lines


def render_feed(events: list[dict], col_width: int, limit: int = 7) -> list[str]:
    """Left column: LIVE FEED."""
    header = bold("LIVE FEED")
    lines = [header, ""]
    for ev in events[:limit]:
        role = (ev.get("role") or "").lower()
        glyph = ROLE_GLYPHS.get(role, "•")
        color = ROLE_COLORS.get(role, "")
        target = ""
        if ev.get("issue_number"):
            target = f" #{ev['issue_number']}"
        elif ev.get("pr_number"):
            target = f" PR{ev['pr_number']}"
        etype = _truncate(ev.get("event_type") or "", 14)
        ago = _since(ev)
        role_str = colorize(color, f"{glyph} {_truncate(role, 8):<8}")
        text = f"{role_str} {_truncate(etype, 14)}{target} {ago}"
        lines.append("• " + _truncate(_strip_ansi(text), col_width - 2) if not _use_color()
                     else "• " + text)
    return lines


def render_leaderboard(board: list[dict], col_width: int, limit: int = 5) -> list[str]:
    """Right column: LEADERBOARD."""
    header = bold("LEADERBOARD")
    lines = [header, ""]
    for i, row in enumerate(board[:limit], start=1):
        role = _truncate(row.get("role") or row.get("project") or "?", 12)
        pts = int(row.get("total_points") or row.get("score") or 0)
        color = ROLE_COLORS.get(role.lower(), "")
        role_colored = colorize(color, role)
        lines.append(f"{i}. {role_colored:<12} {pts} pts")
    return lines


def render_verdict(feed: list[dict], width: int) -> list[str]:
    """Optional bottom callout for latest judge verdict."""
    for ev in feed:
        role = (ev.get("role") or "").lower()
        if role == "judge":
            detail = ev.get("detail") or ev.get("message") or ""
            if detail:
                tag = bold("JUDGE VERDICT:")
                inner = width - 4
                tag_vis = len(_strip_ansi(tag))
                avail = inner - tag_vis - 1
                snippet = _truncate(detail, avail)
                line = f"{tag} {snippet}"
                return [_box_sep(width), _box_row(line, width)]
    return []


def render_two_column(feed: list[dict], board: list[dict], width: int) -> list[str]:
    """Render LIVE FEED | LEADERBOARD side-by-side inside the outer box."""
    inner = width - 4  # content width between │  and  │
    left_w = inner * 2 // 3
    right_w = inner - left_w - 3  # 3 chars for " │ " divider

    feed_lines = render_feed(feed, left_w)
    board_lines = render_leaderboard(board, right_w)

    # Pad both columns to same height
    height = max(len(feed_lines), len(board_lines))
    feed_lines += [""] * (height - len(feed_lines))
    board_lines += [""] * (height - len(board_lines))

    result: list[str] = []
    for fl, bl in zip(feed_lines, board_lines):
        fl_vis = len(_strip_ansi(fl))
        bl_vis = len(_strip_ansi(bl))
        fl_padded = fl + " " * max(0, left_w - fl_vis)
        bl_padded = bl + " " * max(0, right_w - bl_vis)
        row = fl_padded + " │ " + bl_padded
        result.append("│ " + row + " │")

    return result


def render_simple(base_url: str, active: list[dict], board: list[dict],
                  feed: list[dict]) -> str:
    """Narrow-terminal fallback (< 80 cols): plain stacked sections, no boxes."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts = [f"LOOP MONITOR — {base_url}   {now}", ""]

    parts.append("PROJECTS")
    if board:
        for r in board[:5]:
            name = _truncate(r.get("project") or r.get("role") or "?", 18)
            pts = int(r.get("total_points") or 0)
            parts.append(f"  {name:<18} {pts} pts")
    else:
        parts.append("  No projects.")
    parts.append("")

    parts.append("LIVE FEED")
    if feed:
        for ev in feed[:6]:
            role = _truncate(ev.get("role") or "", 8)
            etype = _truncate(ev.get("event_type") or "", 16)
            parts.append(f"  [{_since(ev):>4}] {role:<8} {etype}")
    else:
        parts.append("  No recent events.")

    return "\n".join(parts)


def render_snapshot(base_url: str) -> str:
    active = fetch_json(base_url, "/api/active") or []
    board = fetch_json(base_url, "/api/board") or []
    feed = fetch_json(base_url, "/api/feed") or []

    term_cols = _term_cols()

    if term_cols < 80:
        return render_simple(base_url, active, board, feed)

    width = min(term_cols, 100)

    lines: list[str] = []
    lines += render_banner(base_url, width)

    # Project cards (use board rows as proxy for project status)
    projects = board if board else []
    if active:
        # Merge active status into project list
        active_map = {a.get("project", ""): a for a in active}
        for p in projects:
            name = p.get("project") or p.get("name") or ""
            if name in active_map:
                p["status"] = "busy"
    lines += render_cards(projects, width)

    # Two-column: feed + leaderboard
    lines += render_two_column(feed, board, width)

    # Optional judge verdict
    lines += render_verdict(feed, width)

    lines.append(_box_bot(width))

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Terminal dashboard for Loop Monitor.")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"API base URL (default: {DEFAULT_URL})")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL,
                        help=f"refresh interval in seconds (default: {DEFAULT_INTERVAL})")
    parser.add_argument("--once", action="store_true",
                        help="print one snapshot and exit")
    args = parser.parse_args(argv)

    if args.once:
        try:
            print(render_snapshot(args.url))
            return 0
        except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, OSError) as e:
            print(f"loop-monitor unreachable at {args.url}: {e}", file=sys.stderr)
            return 1

    try:
        while True:
            try:
                snapshot = render_snapshot(args.url)
                if sys.stdout.isatty():
                    sys.stdout.write(CLEAR + snapshot + "\n")
                else:
                    sys.stdout.write(snapshot + "\n")
                sys.stdout.flush()
            except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, OSError) as e:
                print(f"loop-monitor unreachable at {args.url}: {e}", file=sys.stderr)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("dashboard exited.", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())

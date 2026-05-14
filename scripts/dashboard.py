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
MIN_WIDE = 80  # below this width → narrow stacked layout

# ANSI basic 8 colors + bold — no 256/truecolor for portability
_A: dict[str, str] = {
    "R": "\x1b[0m", "B": "\x1b[1m",
    "red": "\x1b[31m", "green": "\x1b[32m", "yellow": "\x1b[33m",
    "blue": "\x1b[34m", "magenta": "\x1b[35m", "cyan": "\x1b[36m",
    "white": "\x1b[37m",
}

_ROLE_COLOR: dict[str, str] = {
    "builder": "cyan", "dev": "cyan",
    "tester": "green",
    "reviewer": "yellow",
    "judge": "magenta",
    "planner": "blue",
}

_ROLE_GLYPH: dict[str, str] = {
    "builder": "◉", "dev": "◉",
    "tester": "✓",
    "reviewer": "★",
    "judge": "⚖",
    "planner": "◈",
}

CARD_INNER = 12  # inner content width of each project card box


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


def _role_glyph(role: str) -> str:
    return _ROLE_GLYPH.get(role.lower(), "•")


def colorize(role: str, text: str, use_color: bool = True) -> str:
    """Wrap pre-padded plain text in ANSI color for the given role.

    Caller must measure/pad text BEFORE calling — ANSI codes are invisible to
    the terminal but inflate Python's len(), so all width math must use the
    plain string.
    """
    if not use_color:
        return text
    color = _ROLE_COLOR.get(role.lower(), "white")
    return _A.get(color, "") + text + _A["R"]


def _bold(text: str, use_color: bool) -> str:
    """Wrap pre-padded plain text in bold. Same caveat as colorize."""
    if not use_color:
        return text
    return _A["B"] + text + _A["R"]


def render_banner(base_url: str, term_cols: int, use_color: bool) -> list[str]:
    """Bordered header: LOOP MONITOR title, base URL, UTC + local time."""
    inner = term_cols - 2
    now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")
    now_local = datetime.now().strftime("%H:%M local")
    time_str = f"{now_utc} · {now_local}"
    title_padded = "LOOP MONITOR".center(inner)
    return [
        "┌" + "─" * inner + "┐",
        "│" + _bold(title_padded, use_color) + "│",
        "│" + _truncate(base_url, inner).center(inner) + "│",
        "├" + "─" * inner + "┤",
        "│" + time_str.center(inner) + "│",
    ]


def _project_state(project: str, active: list[dict]) -> str:
    for w in active:
        if w.get("project") == project:
            event_type = w.get("event_type", "")
            return "wait" if "wait" in event_type else "busy"
    return "idle"


def _project_points(project: str, board: list[dict]) -> int:
    return sum(int(r.get("total_points") or 0) for r in board if r.get("project") == project)


def _project_last_event(project: str, feed: list[dict]) -> str:
    for ev in feed:
        if ev.get("project") == project:
            return _since(ev)
    return "?"


def render_cards(
    projects: list[str],
    active: list[dict],
    board: list[dict],
    feed: list[dict],
    term_cols: int,
    use_color: bool,
) -> list[str]:
    """One box per project, wrapping to the next row when they exceed terminal width."""
    inner = term_cols - 2
    box_w = CARD_INNER + 2  # │content│
    gap = 2
    cards_per_row = max(1, (inner - 2) // (box_w + gap))

    def make_card(proj: str) -> list[str]:
        state = _project_state(proj, active)
        pts = _project_points(proj, board)
        age = _project_last_event(proj, feed)
        return [
            "┌" + "─" * CARD_INNER + "┐",
            "│" + _truncate(proj, CARD_INNER).center(CARD_INNER) + "│",
            "│" + f"◉  {state}".center(CARD_INNER) + "│",
            "│" + f"{pts} pts".center(CARD_INNER) + "│",
            "│" + age.center(CARD_INNER) + "│",
            "└" + "─" * CARD_INNER + "┘",
        ]

    all_lines: list[str] = []
    for chunk_start in range(0, len(projects), cards_per_row):
        chunk = projects[chunk_start: chunk_start + cards_per_row]
        cards = [make_card(p) for p in chunk]
        for row_idx in range(len(cards[0])):
            row_content = "  ".join(c[row_idx] for c in cards)
            padded = (" " + row_content).ljust(inner)
            all_lines.append("│" + padded + "│")
    return all_lines


def render_feed(events: list[dict], col_w: int, use_color: bool, limit: int = 8) -> list[str]:
    """LIVE FEED column — each line padded to exactly col_w plain chars, then colorized."""
    header = "LIVE FEED".ljust(col_w)
    lines = [_bold(header, use_color)]
    if not events:
        lines.append("  No recent events.".ljust(col_w))
        return lines
    for ev in events[:limit]:
        role = ev.get("role") or ""
        glyph = _role_glyph(role)
        project = _truncate(ev.get("project") or "", 10)
        event_type = _truncate(ev.get("event_type") or "", 14)
        target = ""
        if ev.get("issue_number"):
            target = f" #{ev['issue_number']}"
        elif ev.get("pr_number"):
            target = f" PR{ev['pr_number']}"
        age = _since(ev)
        plain = f"  {glyph} {project} {event_type}{target} [{age}]"
        padded = _truncate(plain, col_w).ljust(col_w)
        lines.append(colorize(role, padded, use_color))
    return lines


def render_leaderboard(board: list[dict], col_w: int, use_color: bool, limit: int = 5) -> list[str]:
    """LEADERBOARD column — each line padded to exactly col_w plain chars."""
    header = "LEADERBOARD".ljust(col_w)
    lines = [_bold(header, use_color)]
    if not board:
        lines.append("  No scores yet.".ljust(col_w))
        return lines
    sorted_board = sorted(board, key=lambda r: int(r.get("total_points") or 0), reverse=True)
    for i, r in enumerate(sorted_board[:limit], 1):
        role = _truncate(r.get("role") or r.get("project") or "", 10)
        pts = int(r.get("total_points") or 0)
        plain = f"  {i}. {role:<10} {pts:>5} pts"
        lines.append(_truncate(plain, col_w).ljust(col_w))
    return lines


def render_verdict(events: list[dict], term_cols: int) -> str | None:
    """Latest judge verdict as a single bordered line, or None if not found."""
    inner = term_cols - 2
    for ev in events:
        role = (ev.get("role") or "").lower()
        if role != "judge" and ev.get("event_type") != "judge":
            continue
        detail = ev.get("detail") or ""
        if not detail:
            continue
        if ev.get("pr_number"):
            prefix = f"JUDGE VERDICT (PR #{ev['pr_number']}): "
        elif ev.get("issue_number"):
            prefix = f"JUDGE VERDICT (#{ev['issue_number']}): "
        else:
            prefix = "JUDGE VERDICT: "
        max_detail = inner - len(prefix) - 2
        content = f" {prefix}{_truncate(detail, max_detail)} "
        return "│" + content.ljust(inner) + "│"
    return None


def render_wide(
    active: list[dict],
    board: list[dict],
    feed: list[dict],
    base_url: str,
    term_cols: int,
    use_color: bool,
) -> str:
    """Full box-drawn layout for wide terminals (>= MIN_WIDE cols)."""
    inner = term_cols - 2
    blank = "│" + " " * inner + "│"
    lines: list[str] = []

    lines.extend(render_banner(base_url, term_cols, use_color))
    lines.append(blank)

    projects = sorted({r.get("project") for r in board if r.get("project")})
    for w in active:
        p = w.get("project")
        if p and p not in projects:
            projects.append(p)

    if projects:
        lines.extend(render_cards(projects, active, board, feed, term_cols, use_color))
        lines.append(blank)

    col_w = inner // 2
    right_w = inner - col_w
    feed_lines = render_feed(feed, col_w, use_color)
    lb_lines = render_leaderboard(board, right_w, use_color)
    height = max(len(feed_lines), len(lb_lines))
    for i in range(height):
        fl = feed_lines[i] if i < len(feed_lines) else " " * col_w
        ll = lb_lines[i] if i < len(lb_lines) else " " * right_w
        lines.append("│" + fl + ll + "│")

    lines.append(blank)

    verdict = render_verdict(feed, term_cols)
    if verdict:
        lines.append(verdict)
        lines.append(blank)

    lines.append("└" + "─" * inner + "┘")
    return "\n".join(lines)


def render_narrow(
    active: list[dict],
    board: list[dict],
    feed: list[dict],
    base_url: str,
    use_color: bool,
) -> str:
    """Simple stacked layout for narrow terminals (< MIN_WIDE cols)."""
    now_utc = datetime.now(timezone.utc).strftime("%H:%M UTC")
    parts: list[str] = [
        _bold(f"LOOP MONITOR — {base_url}", use_color),
        f"  {now_utc}",
        "",
    ]

    projects = sorted({r.get("project") for r in board if r.get("project")})
    for w in active:
        p = w.get("project")
        if p and p not in projects:
            projects.append(p)

    if projects:
        parts.append(_bold("PROJECTS", use_color))
        for p in projects:
            state = _project_state(p, active)
            pts = _project_points(p, board)
            parts.append(f"  {p}  ◉ {state}  {pts} pts")
        parts.append("")

    parts.append(_bold("LIVE FEED", use_color))
    if feed:
        for ev in feed[:6]:
            role = ev.get("role") or ""
            glyph = _role_glyph(role)
            event_type = _truncate(ev.get("event_type") or "", 18)
            target = ""
            if ev.get("issue_number"):
                target = f" #{ev['issue_number']}"
            elif ev.get("pr_number"):
                target = f" PR{ev['pr_number']}"
            age = _since(ev)
            plain = f"  {glyph} {event_type}{target} [{age}]"
            parts.append(colorize(role, plain, use_color))
    else:
        parts.append("  No recent events.")
    parts.append("")

    parts.append(_bold("LEADERBOARD", use_color))
    sorted_board = sorted(board, key=lambda r: int(r.get("total_points") or 0), reverse=True)
    for i, r in enumerate(sorted_board[:5], 1):
        role = _truncate(r.get("role") or r.get("project") or "", 10)
        pts = int(r.get("total_points") or 0)
        parts.append(f"  {i}. {role:<10} {pts} pts")

    return "\n".join(parts)


def render_snapshot(base_url: str, use_color: bool | None = None) -> str:
    active = fetch_json(base_url, "/api/active")
    board = fetch_json(base_url, "/api/board")
    feed = fetch_json(base_url, "/api/feed")

    if use_color is None:
        use_color = sys.stdout.isatty()

    try:
        term_cols = os.get_terminal_size().columns
    except OSError:
        term_cols = 80

    if term_cols < MIN_WIDE:
        return render_narrow(active or [], board or [], feed or [], base_url, use_color)
    return render_wide(active or [], board or [], feed or [], base_url, term_cols, use_color)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Terminal dashboard for Loop Monitor.")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"API base URL (default: {DEFAULT_URL})")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL,
                        help=f"refresh interval in seconds (default: {DEFAULT_INTERVAL})")
    parser.add_argument("--once", action="store_true", help="print one snapshot and exit")
    args = parser.parse_args(argv)

    use_color = sys.stdout.isatty()

    if args.once:
        try:
            print(render_snapshot(args.url, use_color=use_color))
            return 0
        except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, OSError) as e:
            print(f"loop-monitor unreachable at {args.url}: {e}", file=sys.stderr)
            return 1

    try:
        while True:
            try:
                snapshot = render_snapshot(args.url, use_color=use_color)
                if use_color:
                    sys.stdout.write(CLEAR + snapshot + "\n")
                else:
                    print(snapshot)
                sys.stdout.flush()
            except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, OSError) as e:
                print(f"loop-monitor unreachable at {args.url}: {e}", file=sys.stderr)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("dashboard exited.", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())

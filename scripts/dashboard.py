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

# Box-drawing
_H = "─"
_V = "│"
_TL = "┌"
_TR = "┐"
_BL = "└"
_BR = "┘"
_LT = "├"
_RT = "┤"

# ANSI
_RST = "\x1b[0m"
_BOLD = "\x1b[1m"
_ROLE_COLORS: dict[str, str] = {
    "dev": "\x1b[34m",
    "po": "\x1b[33m",
    "judge": "\x1b[35m",
    "qa": "\x1b[36m",
    "builder": "\x1b[32m",
    "reviewer": "\x1b[34m",
    "admin": "\x1b[31m",
}
_STATUS_COLORS: dict[str, str] = {
    "busy": "\x1b[32m",
    "idle": "\x1b[37m",
    "wait": "\x1b[33m",
}
_EVENT_GLYPHS: dict[str, str] = {
    "start": "◉",
    "done": "✓",
    "fail": "✗",
    "pass": "✓",
    "skip": "→",
    "judge": "★",
}

CARD_INNER = 12
CARD_TOTAL = CARD_INNER + 2
CARD_GAP = 2
NARROW_COLS = 80


# ── helpers ──────────────────────────────────────────────────────────────────


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


def _get_term_cols() -> int:
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


def _colorize(code: str, text: str, use_color: bool) -> str:
    if not use_color:
        return text
    return f"{code}{text}{_RST}"


def _role_color(role: str) -> str:
    return _ROLE_COLORS.get((role or "").lower(), "\x1b[37m")


def _event_glyph(event_type: str) -> str:
    if not event_type:
        return "•"
    if event_type == "judge":
        return _EVENT_GLYPHS["judge"]
    suffix = event_type.rsplit("_", 1)[-1].lower()
    return _EVENT_GLYPHS.get(suffix, "•")


def _hbar(width: int, left: str = _TL, right: str = _TR) -> str:
    return left + _H * (width - 2) + right


def _box_row(text: str, total_w: int) -> str:
    """One │-bordered row: pad text to fill total_w (includes borders)."""
    inner_w = total_w - 2
    # text may contain ANSI codes; truncate on display length only for plain text
    padded = text[:inner_w].ljust(inner_w)
    return f"{_V}{padded}{_V}"


# ── renderers ────────────────────────────────────────────────────────────────


def render_banner(base_url: str, cols: int, use_color: bool) -> list[str]:
    now_utc = datetime.now(timezone.utc)
    now_local = datetime.now()
    utc_str = now_utc.strftime("UTC %H:%M:%S")
    local_str = now_local.strftime("Local %H:%M:%S")
    time_str = f"{utc_str}   {local_str}"

    inner_w = cols - 2
    title = "LOOP MONITOR"
    title_plain = title.center(inner_w)
    url_plain = _truncate(base_url, inner_w).center(inner_w)
    time_plain = time_str.center(inner_w)

    if use_color:
        title_line = f"{_V}{_BOLD}{title_plain}{_RST}{_V}"
    else:
        title_line = f"{_V}{title_plain}{_V}"

    return [
        _hbar(cols),
        title_line,
        f"{_V}{url_plain}{_V}",
        f"{_V}{time_plain}{_V}",
        _hbar(cols, _LT, _RT),
    ]


def _render_single_card(
    name: str, status: str, pts: int, age: str, use_color: bool
) -> list[str]:
    """Six-line card box (CARD_TOTAL wide)."""
    name_s = _truncate(name, CARD_INNER).center(CARD_INNER)
    status_content = f"◉ {status}".center(CARD_INNER)
    pts_s = f"{pts} pts".center(CARD_INNER)
    age_s = (f"{age} ago" if age != "?" else "?").center(CARD_INNER)

    if use_color:
        sc = _STATUS_COLORS.get(status, "")
        status_line = f"{_V}{_colorize(sc, status_content, True)}{_V}"
    else:
        status_line = f"{_V}{status_content}{_V}"

    return [
        _TL + _H * CARD_INNER + _TR,
        f"{_V}{name_s}{_V}",
        status_line,
        f"{_V}{pts_s}{_V}",
        f"{_V}{age_s}{_V}",
        _BL + _H * CARD_INNER + _BR,
    ]


def render_cards(
    board: list[dict],
    active_projects: set[str],
    last_age: dict[str, str],
    queue_projects: set[str],
    cols: int,
    use_color: bool,
) -> list[str]:
    # Aggregate pts by project
    project_pts: dict[str, int] = {}
    for row in board:
        proj = row.get("project") or "?"
        project_pts[proj] = project_pts.get(proj, 0) + int(row.get("total_points") or 0)

    inner_w = cols - 2
    if not project_pts:
        return [_box_row("  No project data.", cols)]

    avail = inner_w - 2  # 1-space margin on each side
    card_slot = CARD_TOTAL + CARD_GAP
    per_row = max(1, avail // card_slot)

    projects = sorted(project_pts.keys())
    card_h = 6
    output: list[str] = []

    for chunk_start in range(0, len(projects), per_row):
        chunk = projects[chunk_start : chunk_start + per_row]
        rendered_cards = [
            _render_single_card(
                p,
                "wait" if p in queue_projects else "busy" if p in active_projects else "idle",
                project_pts[p],
                last_age.get(p, "?"),
                use_color,
            )
            for p in chunk
        ]

        for line_idx in range(card_h):
            gap = " " * CARD_GAP
            row_content = " " + gap.join(c[line_idx] for c in rendered_cards)
            # Pad to inner_w
            # ANSI codes in status line (line_idx==2) inflate len(); use plain width estimate
            plain_len = 1 + (CARD_TOTAL + CARD_GAP) * len(chunk) - CARD_GAP
            padding = " " * max(0, inner_w - plain_len)
            output.append(f"{_V}{row_content}{padding}{_V}")

        output.append(_box_row("", cols))  # blank spacer between card rows

    return output


def render_feed_items(feed: list[dict]) -> list[tuple[str, str]]:
    """Return (plain_line, role) for up to 8 feed entries."""
    items: list[tuple[str, str]] = []
    for row in feed[:8]:
        role = (row.get("role") or "").lower()
        glyph = _event_glyph(row.get("event_type") or "")
        target = ""
        if row.get("issue_number"):
            target = f" #{row['issue_number']}"
        elif row.get("pr_number"):
            target = f" PR{row['pr_number']}"
        evtype = _truncate(row.get("event_type") or "", 16)
        role_s = _truncate(role, 8)
        line = f"  {glyph} {role_s:<8} {evtype}{target}"
        items.append((line, role))
    return items


def render_leaderboard_items(board: list[dict]) -> list[str]:
    """Return plain lines for top-5 leaderboard."""
    lines: list[str] = []
    for i, row in enumerate(board[:5], 1):
        role = _truncate(row.get("role") or "?", 10)
        pts = int(row.get("total_points") or 0)
        lines.append(f"  {i}. {role:<10} {pts:>5} pts")
    return lines or ["  No scores yet."]


def render_two_columns(
    feed: list[dict], board: list[dict], cols: int, use_color: bool
) -> list[str]:
    inner_w = cols - 2
    left_w = inner_w * 3 // 5
    right_w = inner_w - left_w

    hdr_left = "  LIVE FEED"
    hdr_right = "  LEADERBOARD"

    feed_items = render_feed_items(feed)
    board_lines = render_leaderboard_items(board)

    # Pad to equal height
    max_h = max(len(feed_items), len(board_lines), 1)
    feed_items += [("", "")] * (max_h - len(feed_items))
    board_lines += [""] * (max_h - len(board_lines))

    output: list[str] = []

    # Header
    hdr_l_plain = hdr_left[:left_w].ljust(left_w)
    hdr_r_plain = hdr_right[:right_w].ljust(right_w)
    if use_color:
        hdr_l = _colorize(_BOLD, hdr_l_plain, True)
        hdr_r = _colorize(_BOLD, hdr_r_plain, True)
    else:
        hdr_l, hdr_r = hdr_l_plain, hdr_r_plain
    output.append(f"{_V}{hdr_l}{hdr_r}{_V}")

    for (plain_l, role), plain_r in zip(feed_items, board_lines):
        left_plain = plain_l[:left_w].ljust(left_w)
        right_plain = plain_r[:right_w].ljust(right_w)
        if use_color and plain_l:
            left_cell = _colorize(_role_color(role), left_plain, True)
        else:
            left_cell = left_plain
        output.append(f"{_V}{left_cell}{right_plain}{_V}")

    return output


def render_verdict(verdict: dict | None, cols: int, use_color: bool) -> list[str]:
    if not verdict:
        return []
    project = verdict.get("project") or ""
    reason = verdict.get("reason") or ""
    inner_w = cols - 2
    label = f"  JUDGE VERDICT ({project}):"
    reason_line = f'  "{_truncate(reason, inner_w - 3)}"'
    output = [
        _hbar(cols, _LT, _RT),
        _box_row(label, cols),
        _box_row(reason_line, cols),
    ]
    return output


# ── narrow (< 80 col) fallback ───────────────────────────────────────────────


def render_narrow(
    base_url: str,
    feed: list[dict],
    board: list[dict],
    active_projects: set[str],
    queue_projects: set[str],
    verdict: dict | None,
    cols: int,
    use_color: bool,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts: list[str] = [
        f"LOOP MONITOR — {base_url}   {now}",
        "",
        "PROJECT STATUS",
    ]
    # Aggregate pts by project
    project_pts: dict[str, int] = {}
    for row in board:
        proj = row.get("project") or "?"
        project_pts[proj] = project_pts.get(proj, 0) + int(row.get("total_points") or 0)
    if not project_pts:
        parts.append("  No project data.")
    else:
        for proj in sorted(project_pts):
            status = "wait" if proj in queue_projects else "busy" if proj in active_projects else "idle"
            parts.append(f"  {proj}: ◉ {status}  {project_pts[proj]} pts")

    parts += ["", "LIVE FEED"]
    if not feed:
        parts.append("  No recent events.")
    else:
        for row in feed[:8]:
            role = (row.get("role") or "").lower()
            glyph = _event_glyph(row.get("event_type") or "")
            target = ""
            if row.get("issue_number"):
                target = f" #{row['issue_number']}"
            elif row.get("pr_number"):
                target = f" PR{row['pr_number']}"
            evtype = _truncate(row.get("event_type") or "", 16)
            line = f"  {glyph} {role:<8} {evtype}{target}"
            if use_color:
                line = _colorize(_role_color(role), line, True)
            parts.append(line)

    parts += ["", "LEADERBOARD"]
    for i, row in enumerate(board[:5], 1):
        role = _truncate(row.get("role") or "?", 10)
        pts = int(row.get("total_points") or 0)
        parts.append(f"  {i}. {role:<10} {pts:>5} pts")

    if verdict:
        parts += [
            "",
            f"JUDGE VERDICT ({verdict.get('project','')}):",
            f"  \"{_truncate(verdict.get('reason',''), cols - 5)}\"",
        ]

    return "\n".join(parts)


# ── snapshot ─────────────────────────────────────────────────────────────────


def render_snapshot(base_url: str, use_color: bool) -> str:
    active_data: list[dict] = fetch_json(base_url, "/api/active") or []
    board_data: list[dict] = fetch_json(base_url, "/api/board") or []
    feed_data: list[dict] = fetch_json(base_url, "/api/feed") or []

    queue_projects: set[str] = set()
    try:
        queue_data: list[dict] = fetch_json(base_url, "/api/action_queue") or []
        queue_projects = {r.get("project", "") for r in queue_data if r.get("project")}
    except Exception:
        pass

    latest_verdict: dict | None = None
    try:
        verdicts: list[dict] = fetch_json(base_url, "/api/verdicts") or []
        latest_verdict = verdicts[0] if verdicts else None
    except Exception:
        pass

    cols = _get_term_cols()
    active_projects = {r.get("project", "") for r in active_data}

    # Last event age per project from feed (feed is DESC by id)
    last_age: dict[str, str] = {}
    for row in feed_data:
        proj = row.get("project") or ""
        if proj and proj not in last_age:
            last_age[proj] = _since(row)

    if cols < NARROW_COLS:
        return render_narrow(
            base_url, feed_data, board_data, active_projects, queue_projects, latest_verdict, cols, use_color
        )

    lines: list[str] = []
    lines += render_banner(base_url, cols, use_color)
    lines += render_cards(board_data, active_projects, last_age, queue_projects, cols, use_color)
    lines += render_two_columns(feed_data, board_data, cols, use_color)
    lines += render_verdict(latest_verdict, cols, use_color)
    lines.append(_hbar(cols, _BL, _BR))

    return "\n".join(lines)


# ── main ─────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Terminal dashboard for Loop Monitor.")
    parser.add_argument(
        "--url", default=DEFAULT_URL, help=f"API base URL (default: {DEFAULT_URL})"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help=f"refresh interval in seconds (default: {DEFAULT_INTERVAL})",
    )
    parser.add_argument("--once", action="store_true", help="print one snapshot and exit")
    args = parser.parse_args(argv)

    use_color = sys.stdout.isatty()

    if args.once:
        try:
            print(render_snapshot(args.url, use_color))
            return 0
        except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, OSError) as e:
            print(f"loop-monitor unreachable at {args.url}: {e}", file=sys.stderr)
            return 1

    try:
        while True:
            try:
                snapshot = render_snapshot(args.url, use_color)
                prefix = CLEAR if use_color else ""
                sys.stdout.write(prefix + snapshot + "\n")
                sys.stdout.flush()
            except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, OSError) as e:
                print(f"loop-monitor unreachable at {args.url}: {e}", file=sys.stderr)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("dashboard exited.", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())

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


def _dedupe_projects(rows: list[dict]) -> list[dict]:
    """Collapse board rows (one per project×role×model) into one entry per project."""
    agg: dict[str, dict] = {}
    for r in rows:
        name = r.get("project") or r.get("name") or "?"
        if name not in agg:
            agg[name] = {"project": name, "total_points": 0, "status": r.get("status") or "idle"}
        agg[name]["total_points"] += int(r.get("total_points") or r.get("score") or 0)
    return sorted(agg.values(), key=lambda p: p["total_points"], reverse=True)


def render_cards(projects: list[dict], width: int, max_rows: int = 2) -> list[str]:
    """One box per project; wrap to next row when line would exceed width."""
    if not projects:
        return [_box_row("  No projects.", width), _box_row("", width)]

    CARD_W = 14  # inner width of each card box (total card = CARD_W + 2 borders)
    CARD_TOTAL = CARD_W + 2
    GAP = 2
    cards_per_row = max(1, (width - 2) // (CARD_TOTAL + GAP))
    projects = projects[: cards_per_row * max_rows]

    def make_card(p: dict) -> list[str]:
        name = _truncate(p.get("project") or p.get("name") or "?", CARD_W)
        pts = int(p.get("total_points") or p.get("score") or 0)
        status = (p.get("status") or "idle").lower()
        glyph = STATUS_GLYPHS.get(status, "◉")
        sc = STATUS_COLORS.get(status, "")
        status_line = colorize(sc, f"{glyph} {status:<4}")
        pts_line = f"{pts} pts"

        rows = [
            "┌" + "─" * CARD_W + "┐",
            "│" + _pad_inner(bold(name), CARD_W) + "│",
            "│" + _pad_inner(status_line, CARD_W) + "│",
            "│" + _pad_inner(pts_line, CARD_W) + "│",
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
        project = row.get("project") or "?"
        role = row.get("role") or ""
        pts = int(row.get("total_points") or row.get("score") or 0)
        color = ROLE_COLORS.get(role.lower(), "")
        label = _truncate(f"{project}·{role}" if role else project, col_width - 9)
        label_colored = colorize(color, label)
        pad = max(0, (col_width - 9) - len(_strip_ansi(label)))
        lines.append(f"{i}. {label_colored}{' ' * pad} {pts} pts")
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


def _safe_fetch(base_url: str, path: str, default):
    try:
        return fetch_json(base_url, path) or default
    except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, OSError):
        return default


SPARK_CHARS = " ▁▂▃▄▅▆▇█"


def _sparkline(counts: list[int]) -> str:
    if not counts:
        return ""
    peak = max(counts)
    if peak == 0:
        return SPARK_CHARS[0] * len(counts)
    out = []
    for c in counts:
        # 1..8 levels; 0 stays blank
        idx = 0 if c == 0 else 1 + int((c / peak) * (len(SPARK_CHARS) - 2))
        idx = min(idx, len(SPARK_CHARS) - 1)
        out.append(SPARK_CHARS[idx])
    return "".join(out)


def _events_24h_hourly(events_graph: dict) -> tuple[list[int], int]:
    """Returns (24-element hourly counts list, total)."""
    buckets = (events_graph or {}).get("buckets") or []
    by_hour: dict[str, int] = {}
    for b in buckets:
        hr = b.get("hour", "")
        by_hour[hr] = by_hour.get(hr, 0) + int(b.get("count") or 0)
    hours_sorted = sorted(by_hour.keys())[-24:]
    counts = [by_hour[h] for h in hours_sorted]
    # Pad to 24
    counts = [0] * (24 - len(counts)) + counts
    return counts, sum(counts)


def render_summary(active: list[dict], board: list[dict], queue: list[dict],
                   quality: dict, scanner: dict, events_graph: dict,
                   width: int) -> list[str]:
    projects = _dedupe_projects(board) if board else []
    busy_names = {a.get("project", "") for a in active}
    busy = sum(1 for p in projects if p["project"] in busy_names)
    total_proj = len(projects)
    total_pts = sum(p["total_points"] for p in projects)

    queue_total = len(queue)
    queue_late = sum(1 for q in queue if q.get("threshold_seconds")
                     and q.get("age_seconds", 0) > q["threshold_seconds"])

    v = (quality or {}).get("verdicts") or {}
    clean = v.get("clean", 0)
    light = v.get("light_rework", 0)
    heavy = v.get("heavy_rework", 0)
    blocked = v.get("blocked", 0)

    counts_24h, total_24h = _events_24h_hourly(events_graph or {})
    spark = _sparkline(counts_24h)

    late_str = colorize(ANSI_RED, f"⚠ {queue_late} late") if queue_late else "0 late"
    busy_str = colorize(ANSI_GREEN, f"{busy} busy") if busy else "0 busy"

    # Active workers inline: role@project·target
    def _worker_label(w: dict) -> str:
        role = (w.get("role") or "?").lower()
        proj = w.get("project") or "?"
        if w.get("issue_number"):
            tgt = f"#{w['issue_number']}"
        elif w.get("pr_number"):
            tgt = f"PR{w['pr_number']}"
        else:
            tgt = ""
        color = ROLE_COLORS.get(role, "")
        label = f"{role}@{proj}" + (f"·{tgt}" if tgt else "")
        return colorize(color, label)

    active_workers = active[:4]
    if active_workers:
        active_line = " · ".join(_worker_label(w) for w in active_workers)
        if len(active) > 4:
            active_line += f"  +{len(active) - 4} more"
    else:
        active_line = colorize(ANSI_YELLOW, "(none)")

    # Stages line from scanner_state
    stages = (scanner or {}).get("stages") or {}
    stage_order = ["po", "dev", "qa", "review", "merge"]
    stage_bits = []
    for s in stage_order:
        n = (stages.get(s) or {}).get("in_flight", 0)
        bit = f"{s}:{n}"
        if n > 0:
            bit = colorize(ANSI_GREEN, bit)
        stage_bits.append(bit)
    stages_line = " ".join(stage_bits)

    # Retries (escalation candidates from scanner_state)
    retries = (scanner or {}).get("retries") or []
    over = [r for r in retries if (r.get("count") or 0) > (r.get("max") or 0)]
    retries_line = ""
    if over:
        retries_line = colorize(ANSI_RED, f"  retries  ⚠ {len(over)} over-max")

    lines = [_box_row(bold("SUMMARY"), width), _box_row("", width)]
    lines.append(_box_row(
        f"  projects {total_proj:>3}  ({busy_str}, {total_proj - busy} idle)"
        f"   queue {queue_total:>4}  {late_str}   pts {total_pts:>5,}", width))
    lines.append(_box_row(f"  active   {active_line}", width))
    lines.append(_box_row(f"  stages   {stages_line}", width))
    lines.append(_box_row(f"  events 24h  {spark}  ({total_24h})", width))
    lines.append(_box_row(
        f"  verdicts  clean {clean} · light {light} · heavy {heavy} · blocked {blocked}",
        width))
    if retries_line:
        lines.append(_box_row(retries_line, width))
    return lines


def render_stuck(queue: list[dict], width: int, limit: int = 3) -> list[str]:
    """Top N oldest items from action queue."""
    if not queue:
        return []
    items = sorted(queue, key=lambda q: q.get("age_seconds", 0), reverse=True)[:limit]
    lines = [_box_sep(width), _box_row(bold(f"STUCK (oldest {limit})"), width)]
    for it in items:
        age = _since(it)
        proj = it.get("project") or "?"
        kind = it.get("kind") or "?"
        num = it.get("number") or "?"
        stage = it.get("stage") or "?"
        reason = it.get("reason") or ""
        target = f"{proj}·{kind}#{num}"
        line = f"  {age:>5}  {_truncate(target, 28):<28} {_truncate(stage, 14):<14} {reason}"
        lines.append(_box_row(line, width))
    return lines


def render_activity(feed: list[dict], width: int, limit: int = 10) -> list[str]:
    lines = [_box_sep(width), _box_row(bold(f"ACTIVITY (last {limit})"), width), _box_row("", width)]
    inner = width - 4
    if not feed:
        lines.append(_box_row("  no recent events.", width))
        return lines
    for ev in feed[:limit]:
        role = (ev.get("role") or "").lower()
        glyph = ROLE_GLYPHS.get(role, "•")
        color = ROLE_COLORS.get(role, "")
        etype = ev.get("event_type") or ""
        project = ev.get("project") or ""
        target = ""
        if ev.get("issue_number"):
            target = f"#{ev['issue_number']}"
        elif ev.get("pr_number"):
            target = f"PR{ev['pr_number']}"
        ago = _since(ev)
        role_disp = colorize(color, f"{glyph} {_truncate(role, 8):<8}")
        proj_t = _truncate(project, 14)
        etype_t = _truncate(etype, 18)
        content = f"  {ago:>4}  {role_disp}  {proj_t:<14} {etype_t:<18} {target}"
        # Truncate to fit
        if len(_strip_ansi(content)) > inner:
            content = content[: inner + (len(content) - len(_strip_ansi(content)))]
        lines.append(_box_row(content, width))
    return lines


def render_snapshot(base_url: str) -> str:
    active = _safe_fetch(base_url, "/api/active", [])
    board = _safe_fetch(base_url, "/api/board", [])
    feed = _safe_fetch(base_url, "/api/feed", [])
    queue = _safe_fetch(base_url, "/api/action_queue", [])
    quality = _safe_fetch(base_url, "/api/analytics/quality", {})
    scanner = _safe_fetch(base_url, "/api/scanner_state", {})
    events_graph = _safe_fetch(base_url, "/api/events_graph?window_hours=24", {})

    term_cols = _term_cols()

    if term_cols < 80:
        return render_simple(base_url, active, board, feed)

    width = min(term_cols, 100)

    term_rows = 24
    try:
        term_rows = os.get_terminal_size().lines
    except OSError:
        pass

    summary_lines = render_summary(active, board, queue, quality, scanner, events_graph, width)
    stuck_lines = render_stuck(queue, width, limit=3)
    # banner(5) + summary(~7-8) + stuck(~5) + activity header(2) + bottom(1)
    reserved = 5 + len(summary_lines) + len(stuck_lines) + 2 + 1
    activity_limit = max(3, term_rows - reserved)

    lines: list[str] = []
    lines += render_banner(base_url, width)
    lines += summary_lines
    lines += stuck_lines
    lines += render_activity(feed, width, limit=activity_limit)
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

#!/usr/bin/env python3
"""Terminal dashboard for Loop Monitor — stdlib-only TUI over the local REST API."""
from __future__ import annotations

import argparse
import json
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


def format_active(rows: list[dict]) -> str:
    header = "ACTIVE WORKERS"
    if not rows:
        return f"{header}\n  No active workers."
    lines = [header]
    lines.append(f"  {'PROJECT':<18} {'ROLE':<10} {'MODEL':<14} {'EVENT':<18} {'TASK':<10} SINCE")
    for r in rows:
        task = ""
        if r.get("issue_number"):
            task = f"#{r['issue_number']}"
        elif r.get("pr_number"):
            task = f"PR{r['pr_number']}"
        lines.append(
            f"  {_truncate(r.get('project',''), 18):<18} "
            f"{_truncate(r.get('role',''), 10):<10} "
            f"{_truncate(r.get('model','') or '', 14):<14} "
            f"{_truncate(r.get('event_type',''), 18):<18} "
            f"{_truncate(task, 10):<10} "
            f"{_since(r)}"
        )
    return "\n".join(lines)


def format_board(rows: list[dict]) -> str:
    header = "PROJECT STATUS"
    if not rows:
        return f"{header}\n  No project scores yet."
    lines = [header]
    lines.append(f"  {'PROJECT':<18} {'ROLE':<10} {'MODEL':<14} {'PTS':>6} {'VERDICTS':>9}")
    for r in rows:
        lines.append(
            f"  {_truncate(r.get('project',''), 18):<18} "
            f"{_truncate(r.get('role',''), 10):<10} "
            f"{_truncate(r.get('model','') or '', 14):<14} "
            f"{int(r.get('total_points') or 0):>6} "
            f"{int(r.get('verdict_count') or 0):>9}"
        )
    return "\n".join(lines)


def format_feed(rows: list[dict], limit: int = 5) -> str:
    header = "RECENT FEED"
    if not rows:
        return f"{header}\n  No recent events."
    lines = [header]
    for r in rows[:limit]:
        target = ""
        if r.get("issue_number"):
            target = f" #{r['issue_number']}"
        elif r.get("pr_number"):
            target = f" PR{r['pr_number']}"
        detail = r.get("detail") or ""
        status = r.get("status") or ""
        lines.append(
            f"  [{_since(r):>4}] "
            f"{_truncate(r.get('project',''), 14):<14} "
            f"{_truncate(r.get('role',''), 8):<8} "
            f"{_truncate(r.get('event_type',''), 18):<18}"
            f"{target}"
            f"{(' — ' + _truncate(detail, 50)) if detail else ''}"
            f"{(' [' + status + ']') if status else ''}"
        )
    return "\n".join(lines)


def render_snapshot(base_url: str) -> str:
    active = fetch_json(base_url, "/api/active")
    board = fetch_json(base_url, "/api/board")
    feed = fetch_json(base_url, "/api/feed")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts = [
        f"LOOP MONITOR — {base_url}   {now}",
        "",
        format_active(active or []),
        "",
        format_board(board or []),
        "",
        format_feed(feed or [], limit=5),
    ]
    return "\n".join(parts)


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
                sys.stdout.write(CLEAR + snapshot + "\n")
                sys.stdout.flush()
            except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, OSError) as e:
                print(f"loop-monitor unreachable at {args.url}: {e}", file=sys.stderr)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("dashboard exited.", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())

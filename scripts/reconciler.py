#!/usr/bin/env python3
"""Reconciler tick — checks SLO breaches, emits alerts, and syncs closed-issue state.

Intended to be invoked on a schedule (e.g. every 15 min by cron or the
loop orchestrator).  Reads from bounty.db, checks each project with a
configured SLO, and sends a Signal alert when a sustained breach is detected.
Also emits `issue_closed` events for issues that GitHub reports as CLOSED but
have no terminal event in the DB yet (eliminating per-request gh calls from
the action_queue endpoint).

Environment variables:
    DB_PATH            path to bounty.db (default: bounty.db)
    SIGNAL_NOTIFY_CMD  path to the notification command; receives the alert
                       message as a single argument. When absent, the alert
                       is written to stdout instead.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone

_TS_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
)


def _parse_unix(ts_str: str | None) -> int | None:
    if not ts_str:
        return None
    normalized = str(ts_str).replace("+0000", "+00:00").replace(" ", "T")
    for fmt in _TS_FORMATS:
        try:
            dt = datetime.strptime(normalized, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except ValueError:
            continue
    return None


def send_signal_alert(message: str) -> None:
    """Emit an alert via SIGNAL_NOTIFY_CMD or stdout fallback."""
    cmd = os.environ.get("SIGNAL_NOTIFY_CMD")
    if not cmd:
        print(f"[SLO-ALERT] {message}", flush=True)
        return
    try:
        subprocess.run([cmd, message], check=True, timeout=10)
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"[SLO-ALERT send-failed: {exc}] {message}", flush=True)


def _find_breach_streak_start(conn: sqlite3.Connection, slug: str, total_seconds: int) -> int | None:
    """Return Unix timestamp of the first run in the current unbroken breach streak, or None."""
    runs = conn.execute(
        """SELECT total_duration_seconds, started_at
           FROM pipeline_runs
           WHERE project = ? AND total_duration_seconds IS NOT NULL
           ORDER BY id DESC LIMIT 50""",
        (slug,),
    ).fetchall()

    streak_start: int | None = None
    for run in runs:
        if run["total_duration_seconds"] > total_seconds:
            ts = _parse_unix(run["started_at"])
            if ts is not None:
                streak_start = ts
        else:
            break
    return streak_start


def check_slo_breaches(conn: sqlite3.Connection) -> None:
    """Check all configured project SLOs and alert on sustained breaches."""
    slos = conn.execute(
        "SELECT slug, total_seconds, breach_grace_seconds, last_alerted_at"
        " FROM project_slos WHERE total_seconds IS NOT NULL"
    ).fetchall()

    now = int(time.time())

    for slo in slos:
        slug = slo["slug"]
        total_seconds = slo["total_seconds"]
        grace = slo["breach_grace_seconds"]
        last_alerted_at = slo["last_alerted_at"]

        streak_start = _find_breach_streak_start(conn, slug, total_seconds)
        if streak_start is None:
            continue

        breach_duration = now - streak_start
        if breach_duration < grace:
            continue

        # Dedupe: skip if already alerted for this breach episode
        if last_alerted_at is not None and last_alerted_at >= streak_start:
            continue

        msg = (
            f"SLO breach: project '{slug}' has exceeded {total_seconds}s "
            f"for {breach_duration}s (grace threshold: {grace}s)"
        )
        send_signal_alert(msg)

        conn.execute(
            "UPDATE project_slos SET last_alerted_at = ? WHERE slug = ?",
            (now, slug),
        )
        conn.commit()


_TERMINAL_EVENTS = ("merge_done", "done", "issue_closed")


def _fetch_closed_issue_numbers(repo: str) -> set[int] | None:
    """Return the set of closed issue numbers for a repo via gh, or None on failure."""
    try:
        result = subprocess.run(
            [
                "gh", "issue", "list",
                "--repo", repo,
                "--state", "closed",
                "--limit", "1000",
                "--json", "number",
                "--jq", "[.[].number]",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    try:
        return set(json.loads(result.stdout))
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def emit_issue_closed_events(conn: sqlite3.Connection, projects: dict[str, str]) -> None:
    """For each project, detect issues closed on GitHub with no terminal DB event.

    Queries the DB for issue_numbers that have prior events but no terminal event,
    then calls gh once per project to find which are CLOSED, and inserts
    `issue_closed` events for them so the action_queue endpoint needs zero gh calls.
    """
    placeholders = ",".join("?" * len(_TERMINAL_EVENTS))
    for slug, repo in projects.items():
        candidates_rows = conn.execute(
            f"""
            SELECT DISTINCT issue_number
            FROM events
            WHERE project = ? AND issue_number IS NOT NULL
              AND issue_number NOT IN (
                SELECT DISTINCT issue_number
                FROM events
                WHERE project = ? AND issue_number IS NOT NULL
                  AND event_type IN ({placeholders})
              )
            """,
            (slug, slug, *_TERMINAL_EVENTS),
        ).fetchall()

        if not candidates_rows:
            continue

        candidate_numbers = {row[0] for row in candidates_rows}
        closed_numbers = _fetch_closed_issue_numbers(repo)
        if closed_numbers is None:
            print(f"[reconciler] gh call failed for {repo}, skipping issue_closed sync", flush=True)
            continue

        to_close = candidate_numbers & closed_numbers
        if not to_close:
            continue

        now = datetime.now(timezone.utc).isoformat()
        for number in to_close:
            conn.execute(
                "INSERT INTO events (project, role, event_type, issue_number, created_at)"
                " VALUES (?, 'reconciler', 'issue_closed', ?, ?)",
                (slug, number, now),
            )
        conn.commit()
        print(f"[reconciler] emitted issue_closed for {slug}: {sorted(to_close)}", flush=True)


def main() -> int:
    db_path = os.environ.get("DB_PATH", "bounty.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    try:
        check_slo_breaches(conn)
        try:
            from server.constants import PROJECTS
        except ImportError:
            PROJECTS = {}
        if PROJECTS:
            emit_issue_closed_events(conn, PROJECTS)
        return 0
    except Exception as exc:
        print(f"reconciler error: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())

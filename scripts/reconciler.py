#!/usr/bin/env python3
"""Reconciler tick — checks SLO breaches and emits alerts.

Intended to be invoked on a schedule (e.g. every 15 min by cron or the
loop orchestrator).  Reads from bounty.db, checks each project with a
configured SLO, and sends a Signal alert when a sustained breach is detected.

Environment variables:
    DB_PATH            path to bounty.db (default: bounty.db)
    SIGNAL_NOTIFY_CMD  path to the notification command; receives the alert
                       message as a single argument. When absent, the alert
                       is written to stdout instead.
"""
from __future__ import annotations

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


def main() -> int:
    db_path = os.environ.get("DB_PATH", "bounty.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    try:
        check_slo_breaches(conn)
        return 0
    except Exception as exc:
        print(f"reconciler error: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Nightly retention script: prune old rows from bounty.db.

Usage:
    python scripts/prune.py --db bounty.db
    python scripts/prune.py --db bounty.db --dry-run

Retention horizons (days) are read from env vars with these defaults:
    RETAIN_EVENTS_DAYS=90
    RETAIN_VERDICTS_DAYS=365
    RETAIN_SCORES_DAYS=365
    RETAIN_ISSUE_HISTORY_DAYS=90
    RETAIN_PIPELINE_RUNS_DAYS=365
"""

import argparse
import os
import sqlite3
from datetime import datetime, timedelta, timezone


def _days(env_var: str, default: int) -> int:
    return int(os.environ.get(env_var, default))


def _cutoff(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _count_events(conn: sqlite3.Connection, cutoff: str) -> int:
    """Count events older than cutoff that are safe to prune (not in-flight)."""
    return conn.execute(
        """
        SELECT COUNT(*) FROM events
        WHERE created_at < ?
          AND (
            issue_number IS NULL
            OR issue_number NOT IN (
              SELECT issue_number FROM pipeline_runs
              WHERE project = events.project
                AND completed_at IS NULL
            )
          )
        """,
        (cutoff,),
    ).fetchone()[0]


def _delete_events(conn: sqlite3.Connection, cutoff: str) -> int:
    cur = conn.execute(
        """
        DELETE FROM events
        WHERE created_at < ?
          AND (
            issue_number IS NULL
            OR issue_number NOT IN (
              SELECT issue_number FROM pipeline_runs
              WHERE project = events.project
                AND completed_at IS NULL
            )
          )
        """,
        (cutoff,),
    )
    return cur.rowcount


def _count_issue_history(conn: sqlite3.Connection, cutoff: str) -> int:
    return conn.execute(
        """
        SELECT COUNT(*) FROM issue_history
        WHERE created_at < ?
          AND (project, issue_number) NOT IN (
            SELECT project, issue_number FROM pipeline_runs
            WHERE completed_at IS NULL
          )
        """,
        (cutoff,),
    ).fetchone()[0]


def _delete_issue_history(conn: sqlite3.Connection, cutoff: str) -> int:
    cur = conn.execute(
        """
        DELETE FROM issue_history
        WHERE created_at < ?
          AND (project, issue_number) NOT IN (
            SELECT project, issue_number FROM pipeline_runs
            WHERE completed_at IS NULL
          )
        """,
        (cutoff,),
    )
    return cur.rowcount


def _count_pipeline_runs(conn: sqlite3.Connection, cutoff: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM pipeline_runs WHERE created_at < ? AND completed_at IS NOT NULL",
        (cutoff,),
    ).fetchone()[0]


def _delete_pipeline_runs(conn: sqlite3.Connection, cutoff: str) -> int:
    cur = conn.execute(
        "DELETE FROM pipeline_runs WHERE created_at < ? AND completed_at IS NOT NULL",
        (cutoff,),
    )
    return cur.rowcount


_TS_COLUMN = {
    "events": "created_at",
    "verdicts": "created_at",
    "scores": "updated_at",
    "issue_history": "created_at",
    "pipeline_runs": "created_at",
}


def _count_simple(conn: sqlite3.Connection, table: str, cutoff: str) -> int:
    col = _TS_COLUMN[table]
    return conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE {col} < ?",  # noqa: S608
        (cutoff,),
    ).fetchone()[0]


def _delete_simple(conn: sqlite3.Connection, table: str, cutoff: str) -> int:
    col = _TS_COLUMN[table]
    cur = conn.execute(
        f"DELETE FROM {table} WHERE {col} < ?",  # noqa: S608
        (cutoff,),
    )
    return cur.rowcount


def run(db_path: str, dry_run: bool = False) -> None:
    horizons = {
        "events": _days("RETAIN_EVENTS_DAYS", 90),
        "verdicts": _days("RETAIN_VERDICTS_DAYS", 365),
        "scores": _days("RETAIN_SCORES_DAYS", 365),
        "issue_history": _days("RETAIN_ISSUE_HISTORY_DAYS", 90),
        "pipeline_runs": _days("RETAIN_PIPELINE_RUNS_DAYS", 365),
    }

    size_before = os.path.getsize(db_path)
    conn = sqlite3.connect(db_path)

    try:
        if dry_run:
            counts = {}
            counts["events"] = _count_events(conn, _cutoff(horizons["events"]))
            counts["issue_history"] = _count_issue_history(conn, _cutoff(horizons["issue_history"]))
            counts["pipeline_runs"] = _count_pipeline_runs(conn, _cutoff(horizons["pipeline_runs"]))
            for table in ("verdicts", "scores"):
                counts[table] = _count_simple(conn, table, _cutoff(horizons[table]))
            conn.close()
            parts = " ".join(f"{t}={n}" for t, n in counts.items())
            print(f"dry-run {parts}; would free ~{_estimate_free(counts, size_before):.1f}MB")
        else:
            deleted = {}
            deleted["events"] = _delete_events(conn, _cutoff(horizons["events"]))
            deleted["issue_history"] = _delete_issue_history(conn, _cutoff(horizons["issue_history"]))
            deleted["pipeline_runs"] = _delete_pipeline_runs(conn, _cutoff(horizons["pipeline_runs"]))
            for table in ("verdicts", "scores"):
                deleted[table] = _delete_simple(conn, table, _cutoff(horizons[table]))
            conn.commit()
            conn.execute("VACUUM")
            conn.close()
            size_after = os.path.getsize(db_path)
            freed_mb = (size_before - size_after) / (1024 * 1024)
            parts = " ".join(f"{t}={n}" for t, n in deleted.items())
            print(f"pruned {parts}; freed {freed_mb:.1f}MB")
    except Exception:
        conn.close()
        raise


def _estimate_free(counts: dict, size_before: int) -> float:
    """Rough estimate: assume average row ~200 bytes."""
    total_rows = sum(counts.values())
    return (total_rows * 200) / (1024 * 1024)


def main() -> None:
    default_db = os.environ.get("DB_PATH", "bounty.db")
    parser = argparse.ArgumentParser(description="Prune old rows from bounty.db")
    parser.add_argument("--db", default=default_db, help="Path to bounty.db")
    parser.add_argument("--dry-run", action="store_true", help="Report counts without deleting")
    args = parser.parse_args()
    run(db_path=args.db, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

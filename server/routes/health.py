import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends

from server.constants import MONITOR_VERSION, SUPPORTED_API_MAJOR
from server.db import db_dep

router = APIRouter()

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REMOTE_URL = "https://github.com/svv2014/loop-monitor.git"
_LATEST_SHA_TTL = 60  # seconds

_latest_sha_cache: Optional[str] = None
_latest_sha_fetched_at: float = 0.0


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=_REPO_ROOT,
        )
    except Exception:
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    sha = result.stdout.strip()
    return sha or "unknown"


def _latest_main_sha() -> Optional[str]:
    global _latest_sha_cache, _latest_sha_fetched_at
    now = time.monotonic()
    if _latest_sha_cache is not None and now - _latest_sha_fetched_at < _LATEST_SHA_TTL:
        return _latest_sha_cache
    try:
        result = subprocess.run(
            ["git", "ls-remote", _REMOTE_URL, "refs/heads/main"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return _latest_sha_cache
    if result.returncode != 0 or not result.stdout.strip():
        return _latest_sha_cache
    full_sha = result.stdout.split()[0]
    short_sha = full_sha[:7]
    _latest_sha_cache = short_sha
    _latest_sha_fetched_at = now
    return short_sha


def _commit_delta(running: str, latest: str) -> Optional[int]:
    if running == "unknown" or latest is None:
        return None
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"{running}..{latest}"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=_REPO_ROOT,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


@router.get("/api/health")
def health(conn: sqlite3.Connection = Depends(db_dep)):
    rows = conn.execute(
        "SELECT core_version, COUNT(*) as cnt FROM events WHERE core_version IS NOT NULL GROUP BY core_version"
    ).fetchall()
    core_version_counts = {r["core_version"]: r["cnt"] for r in rows}
    loop_rows = conn.execute(
        "SELECT DISTINCT COALESCE(loop_id, '(unknown)') AS loop_id FROM events ORDER BY loop_id"
    ).fetchall()
    loop_ids = [r["loop_id"] for r in loop_rows]
    running_sha = _git_sha()
    latest_sha = _latest_main_sha()
    delta = _commit_delta(running_sha, latest_sha) if latest_sha and running_sha != latest_sha else None
    return {
        "status": "ok",
        "monitor_version": MONITOR_VERSION,
        "git_sha": running_sha,
        "latest_main_sha": latest_sha,
        "commit_delta": delta,
        "supported_bounty_api": f"{SUPPORTED_API_MAJOR}.x",
        "core_version_counts": core_version_counts,
        "loop_ids": loop_ids,
    }


@router.get("/api/loops")
def get_loops(conn: sqlite3.Connection = Depends(db_dep)):
    rows = conn.execute("""
        SELECT COALESCE(loop_id, '(unknown)') AS loop_id,
               MAX(created_at) AS last_seen,
               COUNT(*) AS event_count,
               GROUP_CONCAT(DISTINCT core_version) AS core_versions
        FROM events
        GROUP BY COALESCE(loop_id, '(unknown)')
        ORDER BY 1
    """).fetchall()
    result = []
    for r in rows:
        entry = dict(r)
        raw = entry.get("core_versions") or ""
        entry["core_versions"] = sorted(set(v for v in raw.split(",") if v)) if raw else []
        result.append(entry)
    return result

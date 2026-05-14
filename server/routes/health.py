import sqlite3
import subprocess
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Depends

from server.constants import MONITOR_VERSION, SUPPORTED_API_MAJOR
from server.db import db_dep

router = APIRouter()

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REMOTE_URL = "https://github.com/svv2014/loop-monitor.git"
_CACHE_TTL = 60.0

_cache_lock = threading.Lock()
_cache_sha: str | None = None
_cache_commits_behind: int | None = None
_cache_fetched_at: float = 0.0


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


def _refresh_latest_main() -> tuple[str, int | None]:
    try:
        ls = subprocess.run(
            ["git", "ls-remote", _REMOTE_URL, "refs/heads/main"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if ls.returncode != 0 or not ls.stdout.strip():
            return "unknown", None
        full_sha = ls.stdout.strip().split()[0]
        latest_sha = full_sha[:7]
    except Exception:
        return "unknown", None

    commits_behind: int | None = None
    try:
        running = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=_REPO_ROOT,
        )
        if running.returncode == 0:
            running_full = running.stdout.strip()
            if running_full != full_sha:
                # Fetch remote objects so rev-list can traverse them
                subprocess.run(
                    ["git", "fetch", "origin", "main", "--quiet"],
                    capture_output=True,
                    timeout=15,
                    cwd=_REPO_ROOT,
                )
                rev = subprocess.run(
                    ["git", "rev-list", f"{running_full}..origin/main", "--count"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    cwd=_REPO_ROOT,
                )
                if rev.returncode == 0:
                    commits_behind = int(rev.stdout.strip())
            else:
                commits_behind = 0
    except Exception:
        pass

    return latest_sha, commits_behind


def _get_latest_main() -> tuple[str, int | None]:
    global _cache_sha, _cache_commits_behind, _cache_fetched_at

    now = time.monotonic()
    with _cache_lock:
        if _cache_sha is not None and now - _cache_fetched_at < _CACHE_TTL:
            return _cache_sha, _cache_commits_behind

    sha, behind = _refresh_latest_main()

    with _cache_lock:
        _cache_sha = sha
        _cache_commits_behind = behind
        _cache_fetched_at = time.monotonic()

    return sha, behind


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
    latest_main_sha, commits_behind = _get_latest_main()
    return {
        "status": "ok",
        "monitor_version": MONITOR_VERSION,
        "git_sha": _git_sha(),
        "latest_main_sha": latest_main_sha,
        "commits_behind": commits_behind,
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

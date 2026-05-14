import sqlite3
import subprocess
import time
from pathlib import Path
from threading import Lock
from typing import Optional

from fastapi import APIRouter, Depends

from server.constants import MONITOR_VERSION, SUPPORTED_API_MAJOR
from server.db import db_dep

router = APIRouter()

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REMOTE_URL = "https://github.com/svv2014/loop-monitor.git"
_LATEST_SHA_CACHE: Optional[tuple] = None
_LATEST_SHA_TTL = 60.0
_LATEST_SHA_LOCK = Lock()


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


def _latest_main_sha() -> str:
    global _LATEST_SHA_CACHE
    with _LATEST_SHA_LOCK:
        now = time.monotonic()
        if _LATEST_SHA_CACHE is not None:
            sha, ts = _LATEST_SHA_CACHE
            if now - ts < _LATEST_SHA_TTL:
                return sha
        try:
            result = subprocess.run(
                ["git", "ls-remote", _REMOTE_URL, "refs/heads/main"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except Exception:
            return "unknown"
        if result.returncode != 0 or not result.stdout.strip():
            return "unknown"
        full_sha = result.stdout.split()[0]
        short_sha = full_sha[:7]
        _LATEST_SHA_CACHE = (short_sha, now)
        return short_sha


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
    return {
        "status": "ok",
        "monitor_version": MONITOR_VERSION,
        "git_sha": _git_sha(),
        "latest_main_sha": _latest_main_sha(),
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

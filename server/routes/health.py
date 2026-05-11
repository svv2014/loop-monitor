import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter

from server.constants import MONITOR_VERSION, SUPPORTED_API_MAJOR
from server.db import get_db

router = APIRouter()

_PIPELINE_CACHE: dict = {"ts": 0.0, "payload": None}
_PIPELINE_LOCK = threading.Lock()

_REPO_ROOT = Path(__file__).resolve().parents[2]


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


@router.get("/api/health")
def health():
    conn = get_db()
    rows = conn.execute(
        "SELECT core_version, COUNT(*) as cnt FROM events WHERE core_version IS NOT NULL GROUP BY core_version"
    ).fetchall()
    core_version_counts = {r["core_version"]: r["cnt"] for r in rows}
    loop_rows = conn.execute(
        "SELECT DISTINCT COALESCE(loop_id, '(unknown)') AS loop_id FROM events ORDER BY loop_id"
    ).fetchall()
    loop_ids = [r["loop_id"] for r in loop_rows]
    conn.close()
    return {
        "status": "ok",
        "monitor_version": MONITOR_VERSION,
        "git_sha": _git_sha(),
        "supported_bounty_api": f"{SUPPORTED_API_MAJOR}.x",
        "core_version_counts": core_version_counts,
        "loop_ids": loop_ids,
    }


@router.get("/api/loops")
def get_loops():
    conn = get_db()
    rows = conn.execute("""
        SELECT COALESCE(loop_id, '(unknown)') AS loop_id,
               MAX(created_at) AS last_seen,
               COUNT(*) AS event_count,
               GROUP_CONCAT(DISTINCT core_version) AS core_versions
        FROM events
        GROUP BY COALESCE(loop_id, '(unknown)')
        ORDER BY 1
    """).fetchall()
    conn.close()
    result = []
    for r in rows:
        entry = dict(r)
        raw = entry.get("core_versions") or ""
        entry["core_versions"] = sorted(set(v for v in raw.split(",") if v)) if raw else []
        result.append(entry)
    return result


def _compute_status(last_tick_iso, interval_seconds) -> str:
    if last_tick_iso is None or interval_seconds is None or interval_seconds <= 0:
        return "down"
    try:
        last_tick = datetime.fromisoformat(last_tick_iso.replace("Z", "+00:00"))
        age = time.time() - last_tick.timestamp()
    except (ValueError, AttributeError):
        return "down"
    if age > 4 * interval_seconds:
        return "down"
    if age > 2 * interval_seconds:
        return "stale"
    return "ok"


def _probe_loop_status() -> dict:
    result = {"scanner": None, "orchestrator": None}
    try:
        proc = subprocess.run(
            ["loop", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode != 0:
            err = (proc.stderr or "")[:200]
            down = {"status": "down", "last_tick_iso": None, "interval_seconds": None, "detail": err or "non-zero exit"}
            return {"scanner": down, "orchestrator": down}
        import json as _json
        data = _json.loads(proc.stdout)
        for key in ("scanner", "orchestrator"):
            sub = data.get(key, {})
            last_tick = sub.get("last_tick_iso")
            interval = sub.get("interval_seconds")
            status = _compute_status(last_tick, interval)
            result[key] = {
                "status": status,
                "last_tick_iso": last_tick,
                "interval_seconds": interval,
                "detail": sub.get("detail", ""),
            }
    except FileNotFoundError:
        down = {"status": "down", "last_tick_iso": None, "interval_seconds": None, "detail": "loop binary not found"}
        result["scanner"] = down
        result["orchestrator"] = down
    except subprocess.TimeoutExpired:
        down = {"status": "down", "last_tick_iso": None, "interval_seconds": None, "detail": "loop status timed out"}
        result["scanner"] = down
        result["orchestrator"] = down
    except Exception as exc:
        down = {"status": "down", "last_tick_iso": None, "interval_seconds": None, "detail": str(exc)[:200]}
        result["scanner"] = down
        result["orchestrator"] = down
    return result


def _probe_event_queue() -> dict:
    url = os.getenv("EVENT_QUEUE_URL", "http://localhost:8765") + "/health"
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            if resp.status != 200:
                return {"status": "down", "last_tick_iso": None, "interval_seconds": None,
                        "detail": f"HTTP {resp.status}"}
            import json as _json
            body = _json.loads(resp.read().decode())
            depth = body.get("queue_depth") or body.get("depth")
            detail = f"queue depth: {depth}" if depth is not None else "healthy"
            return {"status": "ok", "last_tick_iso": None, "interval_seconds": None, "detail": detail}
    except urllib.error.URLError as exc:
        return {"status": "down", "last_tick_iso": None, "interval_seconds": None, "detail": str(exc.reason)[:200]}
    except Exception as exc:
        return {"status": "down", "last_tick_iso": None, "interval_seconds": None, "detail": str(exc)[:200]}


def _build_pipeline_payload() -> dict:
    loop_data = _probe_loop_status()
    eq_data = _probe_event_queue()
    return {
        "scanner": loop_data["scanner"],
        "orchestrator": loop_data["orchestrator"],
        "event_queue": eq_data,
    }


@router.get("/api/health/pipeline")
def pipeline_health():
    with _PIPELINE_LOCK:
        now = time.monotonic()
        if _PIPELINE_CACHE["payload"] is not None and (now - _PIPELINE_CACHE["ts"]) < 30:
            return _PIPELINE_CACHE["payload"]
        payload = _build_pipeline_payload()
        _PIPELINE_CACHE["ts"] = now
        _PIPELINE_CACHE["payload"] = payload
        return payload

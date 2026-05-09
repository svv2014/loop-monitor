import json
import subprocess
import time
from typing import Any, Optional

_OPEN = "<!-- failure-context -->"
_CLOSE = "<!-- /failure-context -->"
_CACHE_TTL = 60.0

_cache: dict[tuple[str, str, int], tuple[float, dict[str, Any]]] = {}


def _run_gh(*args: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _fetch_comments(repo: str, number: int) -> list[dict[str, Any]]:
    raw = _run_gh("api", f"repos/{repo}/issues/{number}/comments", "--paginate")
    if raw is None:
        return []
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return []


def _parse_block(body: str) -> Optional[dict[str, Any]]:
    """Extract failure context from the <!-- failure-context --> block.

    Returns None if the marker is absent or the block is malformed.
    Uses literal-substring extraction; no regex on user content.
    """
    open_idx = body.find(_OPEN)
    if open_idx == -1:
        return None
    start = open_idx + len(_OPEN)
    close_idx = body.find(_CLOSE, start)
    if close_idx == -1:
        return None
    block = body[start:close_idx]

    result: dict[str, Any] = {
        "excerpt": None,
        "model": None,
        "run_id": None,
        "retry_count": 0,
        "log_path": None,
    }

    excerpt_parts: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("model:"):
            val = stripped[len("model:"):].strip()
            result["model"] = val or None
        elif stripped.startswith("run_id:"):
            val = stripped[len("run_id:"):].strip()
            result["run_id"] = val or None
        elif stripped.startswith("retry_count:"):
            val = stripped[len("retry_count:"):].strip()
            try:
                result["retry_count"] = int(val)
            except ValueError:
                result["retry_count"] = 0
        elif stripped.startswith("log_path:"):
            val = stripped[len("log_path:"):].strip()
            result["log_path"] = val or None
        else:
            excerpt_parts.append(line)

    excerpt = "\n".join(excerpt_parts).strip()
    result["excerpt"] = excerpt or None
    return result


def fetch_failure_context(
    repo: str, kind: str, number: int
) -> dict[str, Any]:
    """Return parsed failure context for the given issue/PR.

    Searches the most recent comment that contains the failure-context marker.
    Returns an empty payload (excerpt=None) when no such comment exists.
    Results are cached for 60 s per (repo, kind, number) to avoid GH rate limits.
    """
    cache_key = (repo, kind, number)
    now = time.monotonic()
    if cache_key in _cache:
        ts, payload = _cache[cache_key]
        if now - ts < _CACHE_TTL:
            return payload

    comments = _fetch_comments(repo, number)

    payload: dict[str, Any] = {
        "excerpt": None,
        "model": None,
        "run_id": None,
        "retry_count": 0,
        "timestamp": "",
        "github_comment_url": None,
        "log_path": None,
    }

    for comment in reversed(comments):
        body = comment.get("body") or ""
        if _OPEN not in body:
            continue
        try:
            parsed = _parse_block(body)
        except Exception:
            continue
        if parsed is None:
            continue
        payload.update(parsed)
        payload["timestamp"] = comment.get("created_at") or ""
        payload["github_comment_url"] = comment.get("html_url") or None
        break

    _cache[cache_key] = (now, payload)
    return payload

"""GitHub API helpers — thin wrappers around the `gh` CLI."""

import json
import subprocess
import time

# In-memory cache: (project, kind, number) -> (payload, expires_at)
_FAILURE_CACHE: dict[tuple[str, str, int], tuple[dict, float]] = {}
_CACHE_TTL = 60  # seconds

FAILURE_CONTEXT_START = "<!-- failure-context -->"
FAILURE_CONTEXT_END = "<!-- /failure-context -->"


def _parse_failure_comment(body: str) -> dict:
    """Extract structured fields from a failure-context comment body.

    Returns a dict with all FailureContext fields; excerpt is None if the
    marker is absent or malformed.
    """
    result: dict = {
        "excerpt": None,
        "model": None,
        "run_id": None,
        "retry_count": 0,
        "timestamp": None,
        "github_comment_url": None,
        "log_path": None,
    }
    start = body.find(FAILURE_CONTEXT_START)
    if start == -1:
        return result
    end = body.find(FAILURE_CONTEXT_END, start)
    if end == -1:
        return result
    block = body[start + len(FAILURE_CONTEXT_START):end].strip()
    if not block:
        return result
    try:
        data = json.loads(block)
    except (json.JSONDecodeError, ValueError):
        return result
    result["excerpt"] = data.get("excerpt") or None
    result["model"] = data.get("model") or None
    result["run_id"] = data.get("run_id") or None
    result["retry_count"] = int(data.get("retry_count") or 0)
    result["timestamp"] = data.get("timestamp") or None
    result["log_path"] = data.get("log_path") or None
    return result


def fetch_failure_context(
    repo: str,
    kind: str,
    number: int,
    project: str,
    cache_key: tuple[str, str, int],
) -> dict:
    """Return the most recent failure-context comment for a GH issue/PR.

    Falls back to an empty payload (excerpt=None) on any error.
    Caches results for 60 seconds to stay within GH rate limits.
    """
    now = time.monotonic()
    cached = _FAILURE_CACHE.get(cache_key)
    if cached and now < cached[1]:
        return cached[0]

    entity = "issues" if kind == "issue" else "pulls"
    payload = _empty_payload()

    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/{entity}/{number}/comments",
             "--jq", "[.[] | {body: .body, url: .html_url, created_at: .created_at}]"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        _FAILURE_CACHE[cache_key] = (payload, now + _CACHE_TTL)
        return payload

    if result.returncode != 0:
        _FAILURE_CACHE[cache_key] = (payload, now + _CACHE_TTL)
        return payload

    try:
        comments = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        _FAILURE_CACHE[cache_key] = (payload, now + _CACHE_TTL)
        return payload

    # Walk from most-recent to find the first comment with the marker
    for comment in reversed(comments):
        body = comment.get("body") or ""
        if FAILURE_CONTEXT_START in body:
            parsed = _parse_failure_comment(body)
            parsed["github_comment_url"] = comment.get("url") or None
            if parsed["timestamp"] is None:
                parsed["timestamp"] = comment.get("created_at") or None
            _FAILURE_CACHE[cache_key] = (parsed, now + _CACHE_TTL)
            return parsed

    _FAILURE_CACHE[cache_key] = (payload, now + _CACHE_TTL)
    return payload


def _empty_payload() -> dict:
    return {
        "excerpt": None,
        "model": None,
        "run_id": None,
        "retry_count": 0,
        "timestamp": None,
        "github_comment_url": None,
        "log_path": None,
    }

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger(__name__)

ANTHROPIC_USAGE_URL = "https://api.anthropic.com/v1/organizations/usage_report/messages"

_cache: dict = {"data": None, "fetched_at": None}


def _refresh_seconds() -> int:
    try:
        return max(1, int(os.environ.get("CLAUDE_USAGE_REFRESH_SECONDS", "300")))
    except ValueError:
        return 300


def _enabled() -> bool:
    return os.environ.get("CLAUDE_USAGE_ENABLED", "").lower() in ("1", "true", "yes")


def _fetch_upstream(api_key: str) -> dict:
    """Hit the Anthropic admin usage endpoint. Raises on transport / HTTP failure."""
    req = urllib.request.Request(
        ANTHROPIC_USAGE_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _shape(payload: dict) -> dict:
    """Normalize Anthropic admin usage payload into the dashboard contract."""
    quota_used = payload.get("quota_used") or payload.get("input_tokens", 0) or 0
    quota_limit = payload.get("quota_limit")
    quota_pct = None
    if quota_limit:
        quota_pct = round(100.0 * quota_used / quota_limit, 2)
    cache_hit_pct = payload.get("cache_hit_pct")
    if cache_hit_pct is None:
        cr = payload.get("cache_read_input_tokens")
        ci = payload.get("input_tokens")
        if cr is not None and ci:
            cache_hit_pct = round(100.0 * cr / (cr + ci), 2)
    return {
        "enabled": True,
        "quota_used": quota_used,
        "quota_limit": quota_limit,
        "quota_pct": quota_pct,
        "reset_at": payload.get("reset_at"),
        "cache_hit_pct": cache_hit_pct,
    }


def _cache_fresh() -> bool:
    fetched: Optional[datetime] = _cache["fetched_at"]
    if fetched is None or _cache["data"] is None:
        return False
    age = (datetime.now(timezone.utc) - fetched).total_seconds()
    return age < _refresh_seconds()


@router.get("/api/claude_usage")
def get_claude_usage():
    if not _enabled():
        return {"enabled": False}

    if _cache_fresh():
        return _cache["data"]

    api_key = os.environ.get("ANTHROPIC_ADMIN_KEY")
    if not api_key:
        return {"enabled": True, "error": "ANTHROPIC_ADMIN_KEY not set"}

    try:
        payload = _fetch_upstream(api_key)
        data = _shape(payload)
    except urllib.error.HTTPError as e:
        logger.warning("Anthropic usage HTTP %s", e.code)
        return {"enabled": True, "error": f"upstream HTTP {e.code}"}
    except urllib.error.URLError as e:
        logger.warning("Anthropic usage network error: %s", e.reason)
        return {"enabled": True, "error": "network error"}
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Anthropic usage decode error: %s", e)
        return {"enabled": True, "error": "invalid upstream payload"}

    _cache["data"] = data
    _cache["fetched_at"] = datetime.now(timezone.utc)
    return data

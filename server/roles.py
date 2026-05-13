"""Role / event vocabulary loader.

The dashboard displays a configurable list of roles (pipeline stages). Loaded
at import time from yaml; if no config is present, falls back to the built-in
Loop defaults so existing deployments keep working without action.

See `config/roles.yaml.example` for the file format.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parent.parent

VALID_COLORS = {"violet", "blue", "cyan", "amber", "pink", "green", "indigo", "red", "gray"}


class Role(TypedDict):
    id: str
    label: str
    color: str


# Built-in Loop defaults — used when no config file exists.
DEFAULT_ROLES: list[Role] = [
    {"id": "po",       "label": "PO",       "color": "violet"},
    {"id": "dev",      "label": "Dev",      "color": "blue"},
    {"id": "qa",       "label": "QA",       "color": "amber"},
    {"id": "reviewer", "label": "Reviewer", "color": "pink"},
    {"id": "merge",    "label": "Merge",    "color": "green"},
    {"id": "judge",    "label": "Judge",    "color": "indigo"},
]


def _candidate_config_paths() -> list[Path]:
    env_override = os.environ.get("LOOP_MONITOR_ROLES_CONFIG")
    if env_override:
        return [Path(env_override)]
    return [_REPO_ROOT / "config" / "roles.yaml"]


def _load_roles() -> list[Role]:
    """Load the role vocabulary from yaml. Returns DEFAULT_ROLES on any
    failure (missing file, bad parse, malformed entries) so the server
    always boots with something usable."""
    try:
        import yaml
    except ImportError:
        logger.warning("pyyaml not installed — using built-in role defaults")
        return list(DEFAULT_ROLES)

    for path in _candidate_config_paths():
        if not path.is_file():
            continue
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError as exc:
            logger.error("failed to parse %s: %s — using defaults", path, exc)
            return list(DEFAULT_ROLES)

        raw = data.get("roles") if isinstance(data, dict) else None
        if not isinstance(raw, list):
            logger.warning("%s missing top-level `roles:` list — using defaults", path)
            return list(DEFAULT_ROLES)

        result: list[Role] = []
        seen_ids: set[str] = set()
        for entry in raw:
            if not isinstance(entry, dict):
                logger.warning("skipping non-mapping role entry: %r", entry)
                continue
            rid = entry.get("id")
            label = entry.get("label") or rid
            color = entry.get("color", "gray")
            if not isinstance(rid, str) or not rid:
                logger.warning("skipping role with missing/invalid id: %r", entry)
                continue
            if rid in seen_ids:
                logger.warning("duplicate role id %r — keeping first occurrence", rid)
                continue
            if color not in VALID_COLORS:
                logger.warning(
                    "role %r has unknown color %r — falling back to gray", rid, color
                )
                color = "gray"
            seen_ids.add(rid)
            result.append({"id": rid, "label": str(label), "color": color})

        if not result:
            logger.warning("%s yielded zero valid roles — using defaults", path)
            return list(DEFAULT_ROLES)

        logger.info("loaded %d roles from %s", len(result), path)
        return result

    return list(DEFAULT_ROLES)


ROLES: list[Role] = _load_roles()

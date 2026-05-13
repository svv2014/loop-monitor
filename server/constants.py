"""Static config + project registry.

`PROJECTS` is a dict mapping slug → 'owner/repo' for every project this
loop-monitor instance tracks. It is loaded at import time from (in order):

  1. $LOOP_MONITOR_PROJECTS_CONFIG (path to a yaml file)
  2. ./config/projects.yaml (relative to repo root)

If neither file exists, the registry is empty — loop-monitor still runs, but
project-specific links (issue URLs, repo navigation) will be absent. See
`config/projects.yaml.example` for the file format.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_API_MAJOR = "1"
_version_file = Path(__file__).parent.parent / "VERSION"
MONITOR_VERSION = _version_file.read_text().strip() if _version_file.exists() else "unknown"

HANDLER_TIMEOUT = 30

_REPO_ROOT = Path(__file__).parent.parent


def _candidate_config_paths() -> list[Path]:
    env_override = os.environ.get("LOOP_MONITOR_PROJECTS_CONFIG")
    if env_override:
        return [Path(env_override)]
    return [_REPO_ROOT / "config" / "projects.yaml"]


def _load_projects() -> dict[str, str]:
    """Load the project registry from the first yaml file that exists.

    Each entry is validated as `owner/repo` shape. Malformed entries are
    skipped with a warning so a single typo does not take the whole server
    down.
    """
    try:
        import yaml
    except ImportError:
        logger.warning(
            "pyyaml not installed — project registry will be empty. "
            "Install with: pip install pyyaml"
        )
        return {}

    for path in _candidate_config_paths():
        if not path.is_file():
            continue
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError as exc:
            logger.error("failed to parse %s: %s", path, exc)
            return {}

        raw = data.get("projects") if isinstance(data, dict) else None
        if not isinstance(raw, dict):
            logger.warning("%s missing top-level `projects:` map", path)
            return {}

        result: dict[str, str] = {}
        for slug, repo in raw.items():
            if not isinstance(slug, str) or not isinstance(repo, str):
                logger.warning("skipping non-string entry: %r → %r", slug, repo)
                continue
            if "/" not in repo or repo.count("/") != 1:
                logger.warning("skipping %r — value %r is not owner/repo", slug, repo)
                continue
            result[slug] = repo
        logger.info("loaded %d projects from %s", len(result), path)
        return result

    logger.info(
        "no projects.yaml found at %s — project registry is empty. "
        "Copy config/projects.yaml.example to config/projects.yaml to populate.",
        " or ".join(str(p) for p in _candidate_config_paths()),
    )
    return {}


PROJECTS: dict[str, str] = _load_projects()

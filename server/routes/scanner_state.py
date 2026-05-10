import glob
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import APIRouter

router = APIRouter()

ROLES = ["po", "dev", "qa", "reviewer", "merge"]

# Matches loop's current retry policy; update here if loop ever exposes the limit
RETRY_MAX = 2

CAP_RE = re.compile(r"max=(\d+) \(per-tick emit cap\)")

MAX_TAIL_LINES = 200
MAX_TAIL_BYTES = 5 * 1024 * 1024  # mirror logs.py


def _scanner_log_path() -> Path:
    raw = os.environ.get("LOOP_LOG_DIR") or "~/.openclaw/workspace/logs/loop"
    return Path(os.path.expanduser(raw)) / "loop-scanner.log"


def _read_caps(scanner_log_path: Path) -> dict[str, Optional[int]]:
    result: dict[str, Optional[int]] = {role: None for role in ROLES}
    if not scanner_log_path.exists():
        return result
    try:
        size = os.stat(str(scanner_log_path)).st_size
        start = max(0, size - MAX_TAIL_BYTES)
        with open(scanner_log_path, "rb") as fh:
            fh.seek(start)
            data = fh.read(MAX_TAIL_BYTES)
        text = data.decode("utf-8", errors="replace")
        if start > 0:
            nl = text.find("\n")
            if nl != -1:
                text = text[nl + 1:]
        lines = text.splitlines()[-MAX_TAIL_LINES:]
        # Scan from end; pick most recent cap per role
        found: dict[str, int] = {}
        for line in reversed(lines):
            m = CAP_RE.search(line)
            if m:
                cap = int(m.group(1))
                for role in ROLES:
                    if role not in found and f"loop-{role}-handler" in line:
                        found[role] = cap
            if len(found) == len(ROLES):
                break
        for role, cap in found.items():
            result[role] = cap
    except OSError:
        pass
    return result


def _count_inflight(role: str) -> int:
    try:
        out = subprocess.run(
            ["pgrep", "-f", f"loop-{role}-handler"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        # pgrep returns exit 1 when no matches — not an error
        return sum(1 for line in out.stdout.splitlines() if line.strip())
    except (subprocess.SubprocessError, OSError):
        return 0


def _read_retries(retries_dir: Path = Path("/tmp")) -> list[dict]:
    result: list[dict] = []
    try:
        files = glob.glob(str(retries_dir / "loop-*-retries-*"))
    except OSError:
        return result

    for filepath in files:
        name = Path(filepath).name
        try:
            # split on '-retries-' to isolate role from the project/kind/number tail
            parts = name.split("-retries-", 1)
            if len(parts) != 2:
                continue
            role_part, suffix = parts
            if not role_part.startswith("loop-"):
                continue
            role = role_part[len("loop-"):]
            if not role:
                continue
            # suffix: '{project}-{kind}-{number}'; project may contain dashes
            suffix_parts = suffix.rsplit("-", 2)
            if len(suffix_parts) != 3:
                continue
            project, kind, number_str = suffix_parts
            if not project or not kind:
                continue
            number = int(number_str)
            count = int(Path(filepath).read_text().strip())
            result.append({
                "project": project,
                "kind": kind,
                "number": number,
                "stage": role,
                "count": count,
                "max": RETRY_MAX,
            })
        except (ValueError, OSError):
            continue
    return result


@router.get("/api/scanner_state")
def get_scanner_state():
    caps = _read_caps(_scanner_log_path())
    stages = {}
    for role in ROLES:
        stages[role] = {
            "in_flight": _count_inflight(role),
            "cap": caps[role],
        }

    retries_dir_env = os.environ.get("LOOP_RETRIES_DIR")
    retries_dir = Path(retries_dir_env) if retries_dir_env else Path("/tmp")
    retries = _read_retries(retries_dir)

    return {"stages": stages, "retries": retries}

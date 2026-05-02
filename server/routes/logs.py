import logging
import os
import re
import subprocess
import sys
from collections import deque
from pathlib import Path
from typing import Optional, Tuple

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_HANDLERS = {
    "scanner",
    "reconciler",
    "po-handler",
    "dev-handler",
    "dev-rework-handler",
    "review-handler",
    "qa-handler",
    "merge-handler",
}

MAX_TAIL_BYTES = 5 * 1024 * 1024  # 5 MiB
ORPHAN_THRESHOLD = 1 * 1024 * 1024  # 1 MiB

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}

LINE_RE = re.compile(
    r"^\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] \[(?P<handler>[^\]]+)\] (?P<msg>.*)$"
)


def _exposed() -> bool:
    return os.environ.get("LOOPMON_EXPOSE_LOGS", "").lower() in ("1", "true", "yes")


def _log_dir() -> Path:
    raw = os.environ.get("LOOP_LOG_DIR") or "~/.openclaw/workspace/logs/loop"
    return Path(os.path.expanduser(raw))


def _pid_for_handler(handler: str) -> Optional[int]:
    try:
        out = subprocess.run(
            ["pgrep", "-f", handler],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if out.returncode != 0:
            return None
        for line in out.stdout.splitlines():
            line = line.strip()
            if line.isdigit():
                return int(line)
    except (subprocess.SubprocessError, OSError):
        return None
    return None


def _fd_bytes_for_handler(handler: str, log_path: Path) -> Optional[int]:
    """Return bytes that the running handler has buffered/written via FD to log_path.

    Linux: scan /proc/<pid>/fd/* symlinks for one matching log_path; read fdinfo for pos.
    macOS: lsof -p <pid> -F sn to find FD size.
    Returns None on any failure.
    """
    pid = _pid_for_handler(handler)
    if pid is None:
        return None
    try:
        target = str(log_path.resolve())
    except OSError:
        target = str(log_path)

    try:
        if sys.platform.startswith("linux"):
            fd_dir = Path(f"/proc/{pid}/fd")
            if fd_dir.exists():
                for fd_link in fd_dir.iterdir():
                    try:
                        resolved = os.readlink(str(fd_link))
                    except OSError:
                        continue
                    if resolved == target or resolved.endswith(f"/loop-{handler}.log"):
                        fdinfo = Path(f"/proc/{pid}/fdinfo/{fd_link.name}")
                        try:
                            with open(fdinfo, "r") as fh:
                                for line in fh:
                                    if line.startswith("pos:"):
                                        return int(line.split()[1])
                        except (OSError, ValueError):
                            pass
                        try:
                            return os.stat(str(fd_link)).st_size
                        except OSError:
                            pass
                return None
        # macOS or fallback
        out = subprocess.run(
            ["lsof", "-p", str(pid), "-F", "sn"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if out.returncode != 0:
            return None
        cur_size: Optional[int] = None
        for line in out.stdout.splitlines():
            if not line:
                continue
            tag, val = line[0], line[1:]
            if tag == "s":
                try:
                    cur_size = int(val)
                except ValueError:
                    cur_size = None
            elif tag == "n":
                if val.endswith(f"loop-{handler}.log"):
                    if cur_size is not None:
                        return cur_size
        return None
    except (subprocess.SubprocessError, OSError, ValueError):
        return None


def _orphan_status(handler: str, log_path: Path) -> Tuple[int, Optional[int], bool]:
    try:
        on_disk = os.stat(str(log_path)).st_size
    except OSError:
        on_disk = 0
    fd_bytes = _fd_bytes_for_handler(handler, log_path)
    if fd_bytes is None:
        return on_disk, None, False
    orphaned = abs(fd_bytes - on_disk) > ORPHAN_THRESHOLD
    return on_disk, fd_bytes, orphaned


def _tail_lines(path: Path, tail: str) -> list[str]:
    if not path.exists():
        return []
    if tail == "all":
        try:
            size = os.stat(str(path)).st_size
        except OSError:
            return []
        start = max(0, size - MAX_TAIL_BYTES)
        with open(path, "rb") as fh:
            fh.seek(start)
            data = fh.read(MAX_TAIL_BYTES)
        text = data.decode("utf-8", errors="replace")
        if start > 0:
            nl = text.find("\n")
            if nl != -1:
                text = text[nl + 1 :]
        return text.splitlines()
    try:
        n = int(tail)
    except ValueError:
        n = 200
    n = max(1, min(n, 10000))
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            dq = deque(fh, maxlen=n)
        return [line.rstrip("\n") for line in dq]
    except OSError:
        return []


def _parse_line(raw: str) -> dict:
    m = LINE_RE.match(raw)
    if m:
        return {
            "ts": m.group("ts"),
            "handler": m.group("handler"),
            "msg": m.group("msg"),
            "raw": raw,
        }
    return {"ts": None, "handler": None, "msg": raw, "raw": raw}


@router.get("/api/logs")
def get_logs(
    request: Request,
    handler: str = Query(...),
    filter: str = Query("", alias="filter"),
    tail: str = Query("200"),
):
    # Loopback gate runs before any file access.
    if not _exposed():
        client_host = request.client.host if request.client else None
        if client_host not in LOOPBACK_HOSTS:
            return JSONResponse(status_code=403, content={"error": "logs disabled"})

    if handler not in ALLOWED_HANDLERS:
        raise HTTPException(status_code=400, detail="unknown handler")

    if tail not in ("200", "500", "1000", "all"):
        tail = "200"

    log_path = _log_dir() / f"loop-{handler}.log"

    on_disk, fd_bytes, orphaned = _orphan_status(handler, log_path)

    raw_lines = _tail_lines(log_path, tail)
    if filter:
        raw_lines = [ln for ln in raw_lines if filter in ln]
    parsed = [_parse_line(ln) for ln in raw_lines]

    return {
        "path": str(log_path),
        "on_disk_bytes": on_disk,
        "fd_bytes": fd_bytes,
        "orphaned": orphaned,
        "lines": parsed,
    }

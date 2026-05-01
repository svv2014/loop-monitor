from datetime import datetime, timezone
from typing import Optional

_TS_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S",
)


def parse_ts(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    normalized = s.replace("+00:00", "+0000")
    for fmt in _TS_FORMATS:
        try:
            dt = datetime.strptime(normalized, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def build_timeline_events(history_rows) -> list:
    """Pair *_start and *_done/*_failed rows into stage entries."""
    pending: dict = {}
    result = []
    first_event_ts: Optional[datetime] = None

    for row in history_rows:
        role = row["role"]
        event_type = row["event_type"]
        created_at = row["created_at"]

        if first_event_ts is None:
            first_event_ts = parse_ts(created_at)

        if event_type.endswith("_start"):
            prefix = event_type[: -len("_start")]
            pending[(role, prefix)] = created_at
        elif event_type.endswith("_done") or event_type.endswith("_failed"):
            if event_type.endswith("_done"):
                prefix = event_type[: -len("_done")]
                status = "done"
            else:
                prefix = event_type[: -len("_failed")]
                status = "failed"
            started_at = pending.pop((role, prefix), None)
            duration_seconds = None
            t_end = parse_ts(created_at)
            if started_at and t_end:
                t_start = parse_ts(started_at)
                if t_start:
                    duration_seconds = int((t_end - t_start).total_seconds())
            cumulative_seconds = None
            if first_event_ts and t_end:
                cumulative_seconds = int((t_end - first_event_ts).total_seconds())
            result.append({
                "role": role,
                "event_type": f"{prefix}_{status}",
                "status": status,
                "started_at": started_at,
                "completed_at": created_at,
                "duration_seconds": duration_seconds,
                "cumulative_seconds": cumulative_seconds,
            })

    # Any still-pending starts are running
    for (role, prefix), started_at in pending.items():
        t_start = parse_ts(started_at)
        cumulative_seconds = None
        if first_event_ts and t_start:
            cumulative_seconds = int((t_start - first_event_ts).total_seconds())
        result.append({
            "role": role,
            "event_type": f"{prefix}_start",
            "status": "running",
            "started_at": started_at,
            "completed_at": None,
            "duration_seconds": None,
            "cumulative_seconds": cumulative_seconds,
        })

    result.sort(key=lambda e: e["started_at"] or "")
    return result

def remap_legacy_judge_event(row: dict) -> dict:
    """Map legacy judge rows to the v2 judge_done shape at read time."""
    if row.get("event_type") != "judge":
        return row

    mapped = dict(row)
    mapped["role"] = "judge"
    mapped["event_type"] = "judge_done"
    if "duration_seconds" in mapped:
        mapped["duration_seconds"] = None
    return mapped

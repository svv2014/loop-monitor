def remap_legacy_judge_event(row: dict) -> dict:
    """Map legacy judge rows to the v2 judge_done shape at read time.

    Legacy rows have ``role='dev'`` + ``event_type='judge'`` in the DB
    (a bug in loop's emitter that was fixed in svv2014/loop#349). This
    helper rewrites them to the canonical ``role='judge'`` +
    ``event_type='judge_done'`` shape so the UI's strict filters can see
    them. Idempotent: rows that already have the correct shape pass
    through unchanged.

    TODO: Remove once legacy ``event_type='judge'`` rows age out of
    ``bounty.db`` (post loop#349). Track via grep for legacy rows in
    monthly retention pass.
    """
    if row.get("event_type") != "judge":
        return row

    mapped = dict(row)
    mapped["role"] = "judge"
    mapped["event_type"] = "judge_done"
    if "duration_seconds" in mapped:
        mapped["duration_seconds"] = None
    return mapped

def remap_legacy_judge(row: dict) -> dict:
    """Read-time rewrite: legacy event_type='judge' rows surface as role='judge', event_type='judge_done'.

    After loop#349 ships, new rows already have the correct shape and pass through unchanged.
    This mapping becomes dead code once all legacy rows age out of query windows — remove then.
    """
    if row.get("event_type") == "judge":
        row = dict(row)
        row["event_type"] = "judge_done"
        row["role"] = "judge"
    return row

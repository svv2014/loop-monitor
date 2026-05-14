"""Direct unit tests for server.helpers.event_mapping.remap_legacy_judge_event."""

from server.helpers.event_mapping import remap_legacy_judge_event


def test_remaps_legacy_judge_row():
    row = {"role": "dev", "event_type": "judge", "issue_number": 213}
    out = remap_legacy_judge_event(row)
    assert out["role"] == "judge"
    assert out["event_type"] == "judge_done"
    assert out["issue_number"] == 213


def test_passes_through_non_judge_rows():
    row = {"role": "dev", "event_type": "dev_done"}
    out = remap_legacy_judge_event(row)
    assert out is row  # short-circuit, no copy


def test_passes_through_already_canonical_judge_rows():
    row = {"role": "judge", "event_type": "judge_done"}
    out = remap_legacy_judge_event(row)
    # remapper does not touch event_type 'judge_done'
    assert out is row


def test_nulls_duration_when_present():
    row = {"role": "dev", "event_type": "judge", "duration_seconds": 42}
    out = remap_legacy_judge_event(row)
    assert out["duration_seconds"] is None


def test_does_not_invent_duration_field():
    row = {"role": "dev", "event_type": "judge"}
    out = remap_legacy_judge_event(row)
    assert "duration_seconds" not in out


def test_input_not_mutated():
    row = {"role": "dev", "event_type": "judge"}
    out = remap_legacy_judge_event(row)
    assert row["role"] == "dev"  # original untouched
    assert out["role"] == "judge"  # output remapped

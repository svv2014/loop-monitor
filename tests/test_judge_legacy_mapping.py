from server.event_mapping import remap_legacy_judge


def test_legacy_judge_remapped():
    """(role='dev', event_type='judge') → (role='judge', event_type='judge_done')."""
    row = {"project": "p", "role": "dev", "event_type": "judge", "issue_number": 1}
    result = remap_legacy_judge(row)
    assert result["role"] == "judge"
    assert result["event_type"] == "judge_done"
    assert result["project"] == "p"
    assert result["issue_number"] == 1


def test_new_judge_unchanged():
    """(role='judge', event_type='judge_done') passes through unchanged."""
    row = {"project": "p", "role": "judge", "event_type": "judge_done", "issue_number": 2}
    result = remap_legacy_judge(row)
    assert result["role"] == "judge"
    assert result["event_type"] == "judge_done"


def test_other_event_types_unchanged():
    """Non-judge event types are not affected."""
    row = {"role": "dev", "event_type": "dev_done"}
    result = remap_legacy_judge(row)
    assert result["role"] == "dev"
    assert result["event_type"] == "dev_done"


def test_original_row_not_mutated():
    """The helper returns a new dict; the original is not mutated."""
    row = {"role": "dev", "event_type": "judge"}
    result = remap_legacy_judge(row)
    assert result is not row
    assert row["role"] == "dev"
    assert row["event_type"] == "judge"


def test_idempotent():
    """Applying the mapping twice produces the same result."""
    row = {"role": "dev", "event_type": "judge"}
    once = remap_legacy_judge(row)
    twice = remap_legacy_judge(once)
    assert twice["role"] == "judge"
    assert twice["event_type"] == "judge_done"

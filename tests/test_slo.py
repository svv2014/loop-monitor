"""Tests for SLO config CRUD, stage duration math, rework detection, and breach logic."""
import json
import sqlite3
import time
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

import server
import server.db
from scripts.reconciler import _find_breach_streak_start, check_slo_breaches
from server.routes.stats import (
    _compute_stage_durations,
    _detect_rework_for_run,
    _load_label_transitions,
    _stage_percentile_stats,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_label_transition(conn, project, issue_number, before_labels, after_labels, created_at):
    payload = json.dumps({
        "target_kind": "issue",
        "number": issue_number,
        "before_labels": before_labels,
        "after_labels": after_labels,
        "op": "swap",
        "source": "test",
    })
    conn.execute(
        "INSERT INTO events (project, role, event_type, issue_number, payload, created_at)"
        " VALUES (?, 'scanner', 'label_transition', ?, ?, ?)",
        (project, issue_number, payload, created_at),
    )


def _insert_run(conn, project, issue_number, duration_seconds, started_at=None, completed_at=None):
    started = started_at or "2024-01-01T10:00:00"
    completed = completed_at or "2024-01-01T11:00:00"
    conn.execute(
        """INSERT INTO pipeline_runs
           (project, issue_number, total_duration_seconds, started_at, completed_at, created_at)
           VALUES (?, ?, ?, ?, ?, datetime('now'))""",
        (project, issue_number, duration_seconds, started, completed),
    )


# ---------------------------------------------------------------------------
# Stage duration math
# ---------------------------------------------------------------------------

def test_stage_durations_basic(isolated_client):
    """Stage durations computed from consecutive label_transition events.

    The bucket key (from->to) uses the removed/added labels of each event; the
    duration is the elapsed time from the PREVIOUS event to the CURRENT event
    (i.e. time spent in the 'from' state before transitioning to 'to').
    """
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.row_factory = sqlite3.Row

    # t=10:00 — enter in-progress (swap open → in-progress)
    _insert_label_transition(conn, "proj-sd", 1,
                             ["open"], ["in-progress"],
                             "2024-01-01T10:00:00")
    # t=10:10 — enter review (swap in-progress → review), 600s in in-progress
    _insert_label_transition(conn, "proj-sd", 1,
                             ["in-progress"], ["review"],
                             "2024-01-01T10:10:00")
    # t=10:40 — enter merged (swap review → merged), 1800s in review
    _insert_label_transition(conn, "proj-sd", 1,
                             ["review"], ["merged"],
                             "2024-01-01T10:40:00")
    conn.commit()
    conn.close()

    conn2 = sqlite3.connect(server.db.DB_PATH)
    conn2.row_factory = sqlite3.Row
    by_issue = _load_label_transitions(conn2, "proj-sd")
    conn2.close()

    assert 1 in by_issue
    buckets = _compute_stage_durations(by_issue)

    # Duration from event 1 to event 2 = 600s → bucket key from event 2: "in-progress->review"
    assert "in-progress->review" in buckets
    assert abs(buckets["in-progress->review"][0] - 600) < 2

    # Duration from event 2 to event 3 = 1800s → bucket key from event 3: "review->merged"
    assert "review->merged" in buckets
    assert abs(buckets["review->merged"][0] - 1800) < 2


def test_stage_durations_multiple_runs(isolated_client):
    """Multiple runs contribute to the same bucket."""
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.row_factory = sqlite3.Row

    for issue_num in range(1, 8):
        # t=10:00 — swap open → in-progress
        _insert_label_transition(conn, "proj-mr", issue_num,
                                 ["open"], ["in-progress"],
                                 f"2024-01-{issue_num:02d}T10:00:00")
        # t=10:30 — swap in-progress → merged (1800s elapsed)
        _insert_label_transition(conn, "proj-mr", issue_num,
                                 ["in-progress"], ["merged"],
                                 f"2024-01-{issue_num:02d}T10:30:00")
    conn.commit()
    conn.close()

    conn2 = sqlite3.connect(server.db.DB_PATH)
    conn2.row_factory = sqlite3.Row
    by_issue = _load_label_transitions(conn2, "proj-mr")
    buckets = _compute_stage_durations(by_issue)
    conn2.close()

    # 7 issues, each contributing 1800s to "in-progress->merged"
    assert "in-progress->merged" in buckets
    assert len(buckets["in-progress->merged"]) == 7
    stats = _stage_percentile_stats(buckets["in-progress->merged"])
    assert stats is not None
    assert stats["sample_size"] == 7
    assert stats["p50_seconds"] == pytest.approx(1800, abs=2)


def test_stage_percentile_stats_below_min_returns_none():
    """_stage_percentile_stats returns None for fewer than 5 samples."""
    assert _stage_percentile_stats([]) is None
    assert _stage_percentile_stats([100, 200, 300, 400]) is None


def test_stage_percentile_stats_with_five_samples():
    """Five samples meet the minimum; correct P50/P90 returned."""
    vals = [100, 200, 300, 400, 500]
    stats = _stage_percentile_stats(vals)
    assert stats is not None
    assert stats["sample_size"] == 5
    # int(0.5 * 5) = 2 -> sorted[2] = 300
    assert stats["p50_seconds"] == 300
    # int(0.9 * 5) = 4 -> sorted[4] = 500
    assert stats["p90_seconds"] == 500


def test_cycle_times_includes_stages(isolated_client):
    """GET /api/projects/{slug}/cycle_times response includes stages when data is available."""
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.row_factory = sqlite3.Row

    # Insert 6 issues each with two transitions: open→in-progress, in-progress→done
    for i in range(1, 7):
        _insert_label_transition(conn, "proj-cts", i,
                                 ["open"], ["in-progress"],
                                 f"2024-01-{i:02d}T09:00:00")
        # 1h later: in-progress → done (3600s elapsed)
        _insert_label_transition(conn, "proj-cts", i,
                                 ["in-progress"], ["done"],
                                 f"2024-01-{i:02d}T10:00:00")
        _insert_run(conn, "proj-cts", i, 3600)
    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/projects/proj-cts/cycle_times")
    assert resp.status_code == 200
    data = resp.json()
    assert "stages" in data
    # Duration from event 1→event 2 = 3600s in bucket "in-progress->done"
    # 6 samples >= MIN_STAGE_SAMPLES(5), so stage stats should be populated
    assert "in-progress->done" in data["stages"]
    stage = data["stages"]["in-progress->done"]
    assert "p50_seconds" in stage
    assert "p90_seconds" in stage
    assert stage["sample_size"] == 6


# ---------------------------------------------------------------------------
# Rework detection
# ---------------------------------------------------------------------------

def test_rework_detected_when_label_reappears():
    """A run is flagged as reworked when a removed label reappears."""
    events = [
        {"payload": {"before_labels": ["open"], "after_labels": ["in-progress"]},
         "created_at": "2024-01-01T10:00:00"},
        {"payload": {"before_labels": ["in-progress"], "after_labels": ["review"]},
         "created_at": "2024-01-01T11:00:00"},
        # rework: in-progress reappears after review
        {"payload": {"before_labels": ["review"], "after_labels": ["in-progress"]},
         "created_at": "2024-01-01T12:00:00"},
    ]
    assert _detect_rework_for_run(events) is True


def test_no_rework_for_clean_progression():
    """A clean forward progression is not flagged as rework."""
    events = [
        {"payload": {"before_labels": ["open"], "after_labels": ["in-progress"]},
         "created_at": "2024-01-01T10:00:00"},
        {"payload": {"before_labels": ["in-progress"], "after_labels": ["review"]},
         "created_at": "2024-01-01T11:00:00"},
        {"payload": {"before_labels": ["review"], "after_labels": ["merged"]},
         "created_at": "2024-01-01T12:00:00"},
    ]
    assert _detect_rework_for_run(events) is False


def test_rework_rate_in_cycle_times(isolated_client):
    """rework_rate in GET /api/projects/{slug}/cycle_times reflects actual reworks."""
    conn = sqlite3.connect(server.db.DB_PATH)
    conn.row_factory = sqlite3.Row

    # Issue 1: clean run
    _insert_label_transition(conn, "proj-rw", 1,
                             ["open"], ["in-progress"], "2024-01-01T10:00:00")
    _insert_label_transition(conn, "proj-rw", 1,
                             ["in-progress"], ["done"], "2024-01-01T11:00:00")
    _insert_run(conn, "proj-rw", 1, 3600)

    # Issue 2: rework (in-progress reappears)
    _insert_label_transition(conn, "proj-rw", 2,
                             ["open"], ["in-progress"], "2024-01-02T10:00:00")
    _insert_label_transition(conn, "proj-rw", 2,
                             ["in-progress"], ["review"], "2024-01-02T11:00:00")
    _insert_label_transition(conn, "proj-rw", 2,
                             ["review"], ["in-progress"], "2024-01-02T12:00:00")
    _insert_run(conn, "proj-rw", 2, 7200)

    conn.commit()
    conn.close()

    resp = isolated_client.get("/api/projects/proj-rw/cycle_times")
    assert resp.status_code == 200
    data = resp.json()
    # 1 out of 2 issues reworked = 0.5
    assert data["rework_rate"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# SLO CRUD
# ---------------------------------------------------------------------------

def test_slo_get_returns_defaults_when_not_set(isolated_client):
    """GET /api/projects/{slug}/slo returns defaults for an unconfigured project."""
    resp = isolated_client.get("/api/projects/new-proj/slo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == "new-proj"
    assert data["total_seconds"] is None
    assert data["breach_grace_seconds"] == 3600
    assert data["updated_at"] is None


def test_slo_put_and_get_roundtrip(isolated_client):
    """PUT followed by GET returns the stored SLO values."""
    put_resp = isolated_client.put("/api/projects/my-proj/slo", json={
        "total_seconds": 7200,
        "breach_grace_seconds": 1800,
    })
    assert put_resp.status_code == 200
    put_data = put_resp.json()
    assert put_data["total_seconds"] == 7200
    assert put_data["breach_grace_seconds"] == 1800
    assert put_data["updated_at"] is not None

    get_resp = isolated_client.get("/api/projects/my-proj/slo")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["total_seconds"] == 7200
    assert get_data["breach_grace_seconds"] == 1800


def test_slo_put_update_overwrites(isolated_client):
    """A second PUT updates the existing SLO row."""
    isolated_client.put("/api/projects/proj-ow/slo", json={
        "total_seconds": 3600,
        "breach_grace_seconds": 600,
    })
    isolated_client.put("/api/projects/proj-ow/slo", json={
        "total_seconds": 9000,
        "breach_grace_seconds": 300,
    })
    get_resp = isolated_client.get("/api/projects/proj-ow/slo")
    data = get_resp.json()
    assert data["total_seconds"] == 9000
    assert data["breach_grace_seconds"] == 300


def test_slo_put_null_total_seconds(isolated_client):
    """total_seconds can be set to null (disables the SLO threshold)."""
    isolated_client.put("/api/projects/proj-null/slo", json={
        "total_seconds": 3600,
        "breach_grace_seconds": 600,
    })
    resp = isolated_client.put("/api/projects/proj-null/slo", json={
        "total_seconds": None,
        "breach_grace_seconds": 600,
    })
    assert resp.status_code == 200
    assert resp.json()["total_seconds"] is None


# ---------------------------------------------------------------------------
# Breach detection and dedup
# ---------------------------------------------------------------------------

_RUN_INSERT = (
    "INSERT INTO pipeline_runs"
    " (project, issue_number, total_duration_seconds, started_at, completed_at, created_at)"
    " VALUES (?, ?, ?, ?, ?, ?)"
)


def _make_reconciler_db(tmp_path):
    db_path = str(tmp_path / "breach.db")
    old_path = server.db.DB_PATH
    server.db.DB_PATH = db_path
    server.db.apply_pending_migrations()
    server.db.DB_PATH = old_path
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn, db_path


def test_breach_streak_start_found(tmp_path):
    """_find_breach_streak_start returns the oldest ts in a continuous breach streak."""
    conn, _ = _make_reconciler_db(tmp_path)

    conn.execute(_RUN_INSERT, ("proj", 1, 5000,
                               "2024-01-01T08:00:00", "2024-01-01T09:00:00", "2024-01-01T09:00:00"))
    conn.execute(_RUN_INSERT, ("proj", 2, 9000,
                               "2024-01-02T08:00:00", "2024-01-02T09:30:00", "2024-01-02T09:30:00"))
    conn.execute(_RUN_INSERT, ("proj", 3, 12000,
                               "2024-01-03T08:00:00", "2024-01-03T11:00:00", "2024-01-03T11:00:00"))
    conn.commit()

    # SLO = 7200s; runs 2 and 3 breach, run 1 doesn't
    streak_start = _find_breach_streak_start(conn, "proj", 7200)
    conn.close()

    # The streak includes runs 2 and 3 (DESC order stops at run 1 which doesn't breach)
    assert streak_start is not None
    expected = int(datetime(2024, 1, 2, 8, 0, 0, tzinfo=timezone.utc).timestamp())
    assert streak_start == expected


def test_breach_streak_none_when_no_breach(tmp_path):
    """_find_breach_streak_start returns None when no runs exceed the SLO."""
    conn, _ = _make_reconciler_db(tmp_path)
    conn.execute(_RUN_INSERT, ("proj", 1, 1000,
                               "2024-01-01T08:00:00", "2024-01-01T09:00:00", "2024-01-01T09:00:00"))
    conn.commit()
    result = _find_breach_streak_start(conn, "proj", 7200)
    conn.close()
    assert result is None


def test_check_slo_breaches_sends_alert(tmp_path):
    """check_slo_breaches calls send_signal_alert when breach exceeds grace period."""
    conn, _ = _make_reconciler_db(tmp_path)

    two_hours_ago = time.time() - 7200
    started_iso = datetime.fromtimestamp(two_hours_ago, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute(_RUN_INSERT, ("proj-breach", 1, 9000, started_iso, started_iso, started_iso))
    conn.execute(
        "INSERT INTO project_slos (slug, total_seconds, breach_grace_seconds)"
        " VALUES ('proj-breach', 7200, 3600)"
    )
    conn.commit()

    alerts: list[str] = []
    with patch("scripts.reconciler.send_signal_alert", side_effect=lambda m: alerts.append(m)):
        check_slo_breaches(conn)

    conn.close()
    assert len(alerts) == 1
    assert "proj-breach" in alerts[0]


def test_check_slo_breaches_deduplicates(tmp_path):
    """check_slo_breaches does not send a second alert for the same breach episode."""
    conn, _ = _make_reconciler_db(tmp_path)

    two_hours_ago = time.time() - 7200
    started_iso = datetime.fromtimestamp(two_hours_ago, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute(_RUN_INSERT, ("proj-dd", 1, 9000, started_iso, started_iso, started_iso))
    # last_alerted_at set to now (already alerted for this breach episode)
    conn.execute(
        "INSERT INTO project_slos (slug, total_seconds, breach_grace_seconds, last_alerted_at)"
        " VALUES ('proj-dd', 7200, 3600, ?)",
        (int(time.time()),),
    )
    conn.commit()

    alerts: list[str] = []
    with patch("scripts.reconciler.send_signal_alert", side_effect=lambda m: alerts.append(m)):
        check_slo_breaches(conn)

    conn.close()
    assert len(alerts) == 0


def test_check_slo_breaches_skips_within_grace(tmp_path):
    """check_slo_breaches does not alert when breach duration is within grace period."""
    conn, _ = _make_reconciler_db(tmp_path)

    # Run started 10 minutes ago, grace is 1 hour
    ten_min_ago = time.time() - 600
    started_iso = datetime.fromtimestamp(ten_min_ago, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute(_RUN_INSERT, ("proj-grace", 1, 9000, started_iso, started_iso, started_iso))
    conn.execute(
        "INSERT INTO project_slos (slug, total_seconds, breach_grace_seconds)"
        " VALUES ('proj-grace', 7200, 3600)"
    )
    conn.commit()

    alerts: list[str] = []
    with patch("scripts.reconciler.send_signal_alert", side_effect=lambda m: alerts.append(m)):
        check_slo_breaches(conn)

    conn.close()
    assert len(alerts) == 0

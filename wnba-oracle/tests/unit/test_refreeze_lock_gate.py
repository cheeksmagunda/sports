"""D83: the late re-freeze lock gate.

The re-freeze must never append at or after contest lock (the operator
already acted on the served lineup). Lock known: allow strictly before
lock minus buffer. Lock unknown: allow strictly before the hard deadline;
malformed config fails closed.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from wnba_oracle.scheduler import job2


def _settings(buffer_min: int = 10, deadline: str = "23:30") -> SimpleNamespace:
    return SimpleNamespace(
        refreeze_lock_buffer_min=buffer_min,
        late_refreeze_deadline_utc=deadline,
    )


# --------------------------------------------------------------------------
# E: tip-relative freeze deadline (first_tip - freeze_lead_minutes)
# --------------------------------------------------------------------------
def test_freeze_deadline_subtracts_lead_from_tip() -> None:
    tip = dt.datetime(2026, 6, 14, 23, 30, tzinfo=dt.UTC)
    s = SimpleNamespace(freeze_lead_minutes=90)
    assert job2._freeze_deadline_utc(tip, s) == dt.datetime(2026, 6, 14, 22, 0, tzinfo=dt.UTC)


def test_freeze_deadline_tracks_an_afternoon_tip() -> None:
    # A matinee slate that tips at 17:00 UTC has a 15:30 deadline -- hours
    # before the static evening cutoff would ever look.
    tip = dt.datetime(2026, 6, 14, 17, 0, tzinfo=dt.UTC)
    s = SimpleNamespace(freeze_lead_minutes=90)
    assert job2._freeze_deadline_utc(tip, s) == dt.datetime(2026, 6, 14, 15, 30, tzinfo=dt.UTC)


def test_freeze_deadline_none_when_no_tip() -> None:
    s = SimpleNamespace(freeze_lead_minutes=90)
    assert job2._freeze_deadline_utc(None, s) is None


def test_pre_freeze_window_skips_before_deadline() -> None:
    deadline = dt.datetime(2026, 6, 14, 22, 50, tzinfo=dt.UTC)
    before = dt.datetime(2026, 6, 14, 21, 0, tzinfo=dt.UTC)
    at = dt.datetime(2026, 6, 14, 22, 50, tzinfo=dt.UTC)
    after = dt.datetime(2026, 6, 14, 23, 0, tzinfo=dt.UTC)
    assert job2._in_pre_freeze_window(before, deadline) is True
    assert job2._in_pre_freeze_window(at, deadline) is False  # freeze opens AT T-40
    assert job2._in_pre_freeze_window(after, deadline) is False


def test_pre_freeze_window_never_skips_when_tip_unknown() -> None:
    # None deadline -> static fallback path owns timing; never skip here.
    now = dt.datetime(2026, 6, 14, 12, 0, tzinfo=dt.UTC)
    assert job2._in_pre_freeze_window(now, None) is False


def test_freeze_deadline_default_lead_when_unset() -> None:
    # getattr fallback (40) matches the FREEZE_LEAD_MINUTES setting default.
    tip = dt.datetime(2026, 6, 14, 23, 30, tzinfo=dt.UTC)
    out = job2._freeze_deadline_utc(tip, SimpleNamespace())
    assert out == dt.datetime(2026, 6, 14, 22, 50, tzinfo=dt.UTC)


def test_scheduled_run_skips_optimizer_before_freeze_window() -> None:
    settings = SimpleNamespace(
        env="dev",
        model_artifact_sha="",
        pool_exclude_started_games=False,
    )
    deadline = dt.datetime(2026, 6, 14, 22, 50, tzinfo=dt.UTC)
    with (
        patch.object(job2, "get_settings", return_value=settings),
        patch.object(job2, "_load_enrichment", return_value=[]),
        patch.object(job2, "_load_slate_lock_time", return_value=LOCK),
        patch.object(job2, "_freeze_deadline_utc", return_value=deadline),
        patch.object(job2, "_in_pre_freeze_window", return_value=True),
        patch.object(job2, "_build_specs") as build_specs,
        patch.object(job2, "optimize_lineup") as optimize,
    ):
        result = job2.run("2026-06-14")

    assert result.reason == "pre_freeze_window"
    assert result.exit_code == 0
    build_specs.assert_not_called()
    optimize.assert_not_called()


def test_job2_result_maps_missing_durable_output_to_failure() -> None:
    result = job2.Job2Result(
        slate_date="2026-06-14",
        model_sha="sha",
        recommendation=None,
        frozen=False,
        reason="freeze_not_persisted",
    )
    assert result.exit_code == 1


LOCK = dt.datetime(2026, 6, 8, 23, 30, tzinfo=dt.UTC)


def test_allowed_well_before_lock() -> None:
    now = dt.datetime(2026, 6, 8, 23, 0, tzinfo=dt.UTC)
    allowed, reason = job2._late_refreeze_allowed(now, LOCK, _settings())
    assert allowed is True
    assert reason == "pre_lock"


def test_blocked_inside_buffer() -> None:
    now = dt.datetime(2026, 6, 8, 23, 21, tzinfo=dt.UTC)
    allowed, reason = job2._late_refreeze_allowed(now, LOCK, _settings(buffer_min=10))
    assert allowed is False
    assert reason == "lock_gated"


def test_blocked_exactly_at_buffer_boundary() -> None:
    now = dt.datetime(2026, 6, 8, 23, 20, tzinfo=dt.UTC)
    allowed, _ = job2._late_refreeze_allowed(now, LOCK, _settings(buffer_min=10))
    assert allowed is False


def test_blocked_after_lock() -> None:
    now = dt.datetime(2026, 6, 9, 0, 5, tzinfo=dt.UTC)
    allowed, reason = job2._late_refreeze_allowed(now, LOCK, _settings())
    assert allowed is False
    assert reason == "lock_gated"


def test_unknown_lock_allowed_before_deadline() -> None:
    now = dt.datetime(2026, 6, 8, 23, 5, tzinfo=dt.UTC)
    allowed, reason = job2._late_refreeze_allowed(now, None, _settings(deadline="23:30"))
    assert allowed is True
    assert reason == "pre_deadline_no_locktime"


def test_unknown_lock_blocked_at_deadline() -> None:
    now = dt.datetime(2026, 6, 8, 23, 30, tzinfo=dt.UTC)
    allowed, reason = job2._late_refreeze_allowed(now, None, _settings(deadline="23:30"))
    assert allowed is False
    assert reason == "deadline_no_locktime"


def test_malformed_deadline_fails_closed() -> None:
    now = dt.datetime(2026, 6, 8, 22, 0, tzinfo=dt.UTC)
    allowed, reason = job2._late_refreeze_allowed(now, None, _settings(deadline="nope"))
    assert allowed is False
    assert reason == "bad_deadline_config"


def test_load_slate_lock_time_prefers_explicit_lock() -> None:
    eng = MagicMock()
    conn = MagicMock()
    explicit = dt.datetime(2026, 6, 8, 23, 15, tzinfo=dt.UTC)
    tip = dt.datetime(2026, 6, 8, 23, 30, tzinfo=dt.UTC)
    conn.execute.return_value.first.return_value = (explicit, tip)
    eng.connect.return_value.__enter__.return_value = conn
    with patch.object(job2, "get_engine", return_value=eng):
        out = job2._load_slate_lock_time("2026-06-08")
    assert out == explicit


def test_load_slate_lock_time_falls_back_to_first_tip() -> None:
    eng = MagicMock()
    conn = MagicMock()
    tip = dt.datetime(2026, 6, 8, 23, 30, tzinfo=dt.UTC)
    conn.execute.return_value.first.return_value = (None, tip)
    eng.connect.return_value.__enter__.return_value = conn
    with patch.object(job2, "get_engine", return_value=eng):
        out = job2._load_slate_lock_time("2026-06-08")
    assert out == tip


def test_load_slate_lock_time_none_when_no_row() -> None:
    eng = MagicMock()
    conn = MagicMock()
    conn.execute.return_value.first.return_value = None
    eng.connect.return_value.__enter__.return_value = conn
    with patch.object(job2, "get_engine", return_value=eng):
        assert job2._load_slate_lock_time("2026-06-08") is None


def test_load_slate_lock_time_naive_timestamp_treated_as_utc() -> None:
    eng = MagicMock()
    conn = MagicMock()
    naive = dt.datetime(2026, 6, 8, 23, 30)
    conn.execute.return_value.first.return_value = (naive, None)
    eng.connect.return_value.__enter__.return_value = conn
    with patch.object(job2, "get_engine", return_value=eng):
        out = job2._load_slate_lock_time("2026-06-08")
    assert out == dt.datetime(2026, 6, 8, 23, 30, tzinfo=dt.UTC)

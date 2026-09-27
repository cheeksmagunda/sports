"""Unit tests for advance freeze readiness summarization (#332 / #535)."""

from __future__ import annotations

from wnba_oracle.ops.freeze_readiness import summarize_freeze_readiness


def test_cleared_hard_trigger_in_history_does_not_block() -> None:
    """Live pool recovery must not sticky-block on a prior no_job1_pool (#535)."""
    summary = summarize_freeze_readiness(
        picks_paused=False,
        slate_timing_captured=True,
        lineup_frozen=False,
        job1_status="success",
        job1_exit_code=0,
        events=[{"trigger": "rotowire_empty"}],
        history=[{"trigger": "no_job1_pool"}, {"trigger": "config_drift"}],
    )
    assert summary["ready_for_freeze"] is True
    assert summary["phase"] == "advisory"
    assert summary["blockers"] == []
    assert summary["advisories"] == ["config_drift", "rotowire_empty"]


def test_live_hard_trigger_blocks() -> None:
    summary = summarize_freeze_readiness(
        picks_paused=False,
        slate_timing_captured=True,
        lineup_frozen=False,
        job1_status="success",
        job1_exit_code=0,
        events=[{"trigger": "no_job1_pool"}],
        history=[],
    )
    assert summary["ready_for_freeze"] is False
    assert summary["phase"] == "blocked"
    assert summary["blockers"] == ["no_job1_pool"]


def test_advisory_still_ready_for_freeze() -> None:
    summary = summarize_freeze_readiness(
        picks_paused=False,
        slate_timing_captured=True,
        lineup_frozen=False,
        job1_status="success",
        job1_exit_code=0,
        events=[{"trigger": "config_drift"}],
        history=[],
    )
    assert summary["ready_for_freeze"] is True
    assert summary["phase"] == "advisory"
    assert summary["advisories"] == ["config_drift"]


def test_timing_unknown_blocks_even_without_triggers() -> None:
    summary = summarize_freeze_readiness(
        picks_paused=False,
        slate_timing_captured=False,
        lineup_frozen=False,
        job1_status="success",
        job1_exit_code=0,
        events=[],
        history=[],
    )
    assert summary["ready_for_freeze"] is False
    assert summary["phase"] == "timing_unknown"


def test_already_frozen_is_ready() -> None:
    summary = summarize_freeze_readiness(
        picks_paused=False,
        slate_timing_captured=True,
        lineup_frozen=True,
        job1_status="failed",
        job1_exit_code=1,
        events=[{"trigger": "no_job1_pool"}],
        history=[],
    )
    assert summary["ready_for_freeze"] is True
    assert summary["phase"] == "already_frozen"


def test_running_job1_does_not_block_when_live_clean() -> None:
    summary = summarize_freeze_readiness(
        picks_paused=False,
        slate_timing_captured=True,
        lineup_frozen=False,
        job1_status="running",
        job1_exit_code=None,
        events=[{"trigger": "rotowire_empty"}],
        history=[{"trigger": "no_job1_pool"}],
    )
    assert summary["ready_for_freeze"] is True
    assert summary["phase"] == "advisory"
    assert summary["job1_success"] is None

"""Unit tests for advance freeze readiness summarization (#332)."""

from __future__ import annotations

from wnba_oracle.ops.freeze_readiness import summarize_freeze_readiness


def test_blocked_when_hard_trigger_in_history_only() -> None:
    summary = summarize_freeze_readiness(
        picks_paused=False,
        slate_timing_captured=True,
        lineup_frozen=False,
        job1_status="success",
        job1_exit_code=0,
        events=[],
        history=[{"trigger": "model_artifact_unset"}],
    )
    assert summary["ready_for_freeze"] is False
    assert summary["phase"] == "blocked"
    assert summary["blockers"] == ["model_artifact_unset"]


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

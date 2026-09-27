"""Kickoff slot + home_away context wiring (#523)."""

from __future__ import annotations

from datetime import UTC, datetime

from nfl_oracle.features.live import (
    REQUIRED_LIVE_OK_CONTEXT_FEATURES,
    kickoff_slot_features,
    kickoff_slot_name,
)


def test_kickoff_slot_sunday_windows() -> None:
    early = datetime(2024, 9, 8, 17, 0, tzinfo=UTC)  # 13:00 ET Sunday
    late = datetime(2024, 9, 8, 20, 25, tzinfo=UTC)  # 16:25 ET Sunday
    snf = datetime(2024, 9, 9, 0, 20, tzinfo=UTC)  # 20:20 ET Sunday
    mnf = datetime(2024, 9, 10, 0, 15, tzinfo=UTC)  # 20:15 ET Monday
    assert kickoff_slot_name(early) == "early"
    assert kickoff_slot_name(late) == "late"
    assert kickoff_slot_name(snf) == "snf"
    assert kickoff_slot_name(mnf) == "mnf"
    feats = kickoff_slot_features(early)
    assert feats["kickoff_slot_early"] == 1.0
    assert feats["kickoff_slot_snf"] == 0.0
    assert sum(feats.values()) == 1.0


def test_required_context_includes_kickoff_and_home() -> None:
    required = set(REQUIRED_LIVE_OK_CONTEXT_FEATURES)
    assert "kickoff_slot_early" in required
    assert "home_away" in required
    assert "is_home" in required
    assert "team_pace_prior" in required
    assert "opp_def_value_allowed_prior" in required
    assert "days_rest" in required

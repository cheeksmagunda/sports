"""Feature registry depth for pre-lock decisioning."""

from __future__ import annotations

from nfl_oracle.features.schema import (
    feature_registry,
    features_by_group,
    features_document,
    live_ok_feature_names,
    offline_stub_feature_names,
)
from nfl_oracle.features.stubs import offline_stub_feature_row


def test_feature_registry_pre_lock_depth() -> None:
    specs = {s.name: s for s in feature_registry()}
    assert len(specs) >= 28
    for name in (
        "season",
        "week",
        "gameday",
        "home_away",
        "opponent_team",
        "is_divisional",
        "kickoff_slot",
        "player_prior_mean",
        "player_prior_median",
        "position_prior_mean",
        "team_prior_mean",
        "opponent_adjusted_prior",
        "opp_def_value_allowed_prior",
        "prior_fallback_level",
        "days_rest",
        "position",
        "team_id",
        "injury_status",
        "injury_status_available",
        "weather_temp_f",
        "weather_wind_mph",
        "weather_precip_prob",
        "weather_available",
        "team_pace_prior",
        "opponent_pace_prior",
    ):
        assert name in specs
        assert specs[name].live_ok is True
    assert specs["same_slate_final_value"].live_ok is False
    assert specs["card_boost_post_settlement"].live_ok is False
    live = live_ok_feature_names()
    assert "player_prior_mean" in live
    assert "injury_status" in live
    assert "weather_temp_f" in live
    assert "team_pace_prior" in live
    assert "opponent_adjusted_prior" in live
    assert "same_slate_final_value" not in live
    assert len(live) >= 24
    stubs = offline_stub_feature_names()
    assert "injury_status" in stubs
    assert "opponent_adjusted_prior" in stubs
    assert len(stubs) >= 8
    doc = features_document()
    assert doc["feature_count"] == len(specs)
    assert doc["live_ok_count"] == len(live)
    assert doc["offline_stub_count"] == len(stubs)
    assert doc["group_counts"]["prior"] >= 7
    assert doc["group_counts"]["matchup"] >= 3
    assert doc["group_counts"]["injury"] >= 2
    assert doc["group_counts"]["weather"] >= 3
    assert doc["group_counts"]["pace"] >= 2
    assert doc["contest_entry"] is False
    assert len(features_by_group("calendar")) >= 3


def test_offline_stub_feature_row_nulls() -> None:
    row = offline_stub_feature_row(player_id=1, season=2024, week=1)
    assert row["contest_entry"] is False
    assert row["values_are_stubs"] is True
    assert row["injury_status"] is None
    assert row["injury_status_available"] is False
    assert row["weather_available"] is False
    assert row["opponent_adjusted_prior"] is None
    assert row["team_pace_prior"] is None

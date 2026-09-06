"""Feature registry depth for pre-lock decisioning."""

from __future__ import annotations

from nfl_oracle.features.schema import (
    feature_registry,
    features_by_group,
    features_document,
    live_ok_feature_names,
)


def test_feature_registry_pre_lock_depth() -> None:
    specs = {s.name: s for s in feature_registry()}
    assert len(specs) >= 16
    for name in (
        "season",
        "week",
        "gameday",
        "home_away",
        "opponent_team",
        "kickoff_slot",
        "player_prior_mean",
        "player_prior_median",
        "position_prior_mean",
        "team_prior_mean",
        "prior_fallback_level",
        "days_rest",
        "position",
        "team_id",
    ):
        assert name in specs
        assert specs[name].live_ok is True
    assert specs["same_slate_final_value"].live_ok is False
    assert specs["card_boost_post_settlement"].live_ok is False
    live = live_ok_feature_names()
    assert "player_prior_mean" in live
    assert "same_slate_final_value" not in live
    assert len(live) >= 14
    doc = features_document()
    assert doc["feature_count"] == len(specs)
    assert doc["live_ok_count"] == len(live)
    assert doc["group_counts"]["prior"] >= 6
    assert doc["group_counts"]["matchup"] >= 2
    assert doc["contest_entry"] is False
    assert len(features_by_group("calendar")) >= 3

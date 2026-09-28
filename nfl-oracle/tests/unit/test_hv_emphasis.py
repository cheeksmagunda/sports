"""HV top-10 emphasis names stay on live features and off chalk channels."""

from __future__ import annotations

import json

from nfl_oracle.features.live import REQUIRED_LIVE_OK_CONTEXT_FEATURES, WEATHER_FEATURE_NAMES
from nfl_oracle.recommendations.hv_emphasis import (
    hv_feature_emphasis,
    hv_feature_emphasis_names,
)


def test_emphasis_names_are_live_and_chalk_channels_stay_off() -> None:
    report = hv_feature_emphasis()
    names = [row["name"] for row in report["feature_spec"]]
    assert "prior_started" in names
    assert "opp_def_value_allowed_prior" in names
    assert "position" in names
    assert "team_pace_prior" in names
    assert "overall_rank" in names
    assert "injury_status" in names
    assert "prior_log_count" not in names
    assert "draft_count" not in names
    assert "card_boost_post_settlement" not in names
    assert "prior_log_count" not in report["ridge_core"]
    assert "player_mean_shrunk" in report["ridge_core"]
    assert "opportunity_trend" in report["ridge_core"]
    context = {row["name"] for row in report["ridge_context"]}
    assert context <= set(REQUIRED_LIVE_OK_CONTEXT_FEATURES)
    assert "prior_minutes" in context
    assert "weather_temp_f" not in context
    assert set(WEATHER_FEATURE_NAMES) <= set(report["weather_not_emphasis"])
    assert report["draft_count_is_label"] is False
    assert report["winning_drafts_are_label"] is False
    assert report["boost_interaction"]["ridge_feature"] is False
    assert report["boost_interaction"]["card_boost_post_settlement_live_ok"] is False
    observation = report["observation"]
    assert observation["@type"] == "Observation"
    flags = {item["name"]: item["value"] for item in observation["additionalProperty"]}
    assert flags["draft count is label"] is False
    assert flags["winning drafts are label"] is False
    assert flags["card boost is ridge feature"] is False
    assert "prior_started" in flags["usage"]
    compact = hv_feature_emphasis_names()
    json.dumps(compact)
    assert compact["boost_is_ridge_feature"] is False
    assert "winning_drafts" in compact["chalk_off"]

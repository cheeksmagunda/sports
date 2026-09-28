"""HV top-10 emphasis names stay on live features and off chalk channels."""

from __future__ import annotations

import json

from nfl_oracle.features.live import REQUIRED_LIVE_OK_CONTEXT_FEATURES
from nfl_oracle.features.schema import feature_registry
from nfl_oracle.recommendations.hv_emphasis import (
    hv_feature_emphasis,
    hv_feature_emphasis_names,
)


def _feature_spec_names(node: object) -> set[str]:
    """Names on nested PropertyValues marked oracle:FeatureSpec."""

    found: set[str] = set()
    if isinstance(node, dict):
        if node.get("@type") == "PropertyValue" and node.get("propertyID") == "oracle:FeatureSpec":
            name = node.get("name")
            if isinstance(name, str) and name not in {
                "usage",
                "matchup",
                "role",
                "pace",
                "slate",
                "injury",
                "external_pregame",
                "player_profile",
                "slate_conditions",
                "conditions",
                "FeatureSpec role",
            }:
                found.add(name)
        for value in node.values():
            found |= _feature_spec_names(value)
    elif isinstance(node, list):
        for value in node:
            found |= _feature_spec_names(value)
    return found


def test_emphasis_names_are_live_and_chalk_channels_stay_off() -> None:
    report = hv_feature_emphasis()
    names = [row["name"] for row in report["feature_spec"]]
    live = {
        spec.name
        for spec in feature_registry()
        if spec.live_ok and spec.train_ok and spec.group != "label_only"
    }
    assert set(names) == live
    assert len(names) == len(live)
    assert "global_prior_mean" in names
    assert "prior_started" in names
    assert "opp_def_value_allowed_prior" in names
    assert "position" in names
    assert "team_pace_prior" in names
    assert "overall_rank" in names
    assert "injury_status" in names
    assert "weather_temp_f" in names
    assert "prior_log_count" not in names
    assert "draft_count" not in names
    assert "card_boost_post_settlement" not in names
    assert "prior_log_count" not in report["ridge_core"]
    assert "player_mean_shrunk" in report["ridge_core"]
    assert "opportunity_trend" in report["ridge_core"]
    context = {row["name"] for row in report["ridge_context"]}
    assert context == set(REQUIRED_LIVE_OK_CONTEXT_FEATURES)
    assert "prior_minutes" in context
    assert "weather_temp_f" in context
    assert "weather_available" in context
    assert {row["name"] for row in report["conditions"]} == set(names)
    assert {"position", "player_prior_mean", "prior_started"} <= {
        row["name"] for row in report["conditions"] if row["role"] == "player_profile"
    }
    assert {"season", "kickoff_slot", "days_rest", "team_pace_prior"} <= {
        row["name"] for row in report["conditions"] if row["role"] == "slate_conditions"
    }
    assert {"weather_temp_f", "team_moneyline", "injury_status"} <= {
        row["name"] for row in report["conditions"] if row["role"] == "external_pregame"
    }
    assert "draft_count" not in names
    assert "prior_log_count" not in names
    assert report["draft_count_is_label"] is False
    assert report["winning_drafts_are_label"] is False
    assert report["winning_drafts_are_reference_bar"] is True
    assert report["cash_is_objective"] is False
    assert report["median_is_objective"] is False
    assert report["lineup_size"] == 5
    assert report["objective"] == (
        "5-player lineup maximizing capture of highestBoostedValuePlayers"
    )
    assert report["boost_interaction"]["ridge_feature"] is False
    assert report["boost_interaction"]["card_boost_post_settlement_live_ok"] is False
    observation = report["observation"]
    assert observation["@type"] == "Observation"
    flags = {item["name"]: item["value"] for item in observation["additionalProperty"]}
    assert flags["draft count is label"] is False
    assert flags["winning drafts are label"] is False
    assert flags["winning drafts are a reference bar"] is True
    assert flags["cash is objective"] is False
    assert flags["median is objective"] is False
    assert flags["lineup size"] == 5
    assert flags["card boost is ridge feature"] is False
    prior = next(item for item in observation["additionalProperty"] if item["name"] == "prior")
    assert prior["propertyID"] == "oracle:FeatureSpec"
    nested = prior["valueReference"]
    assert nested["@type"] == "Observation"
    spec_names = {
        item["name"]
        for item in nested["additionalProperty"]
        if item.get("propertyID") == "oracle:FeatureSpec"
    }
    assert "prior_started" in spec_names
    assert "prior_minutes" in spec_names
    assert "global_prior_mean" in spec_names
    walked = _feature_spec_names(observation)
    assert "opp_def_value_allowed_prior" in walked
    assert "position" in walked
    assert "season" in walked
    assert "weather_wind_mph" in walked
    assert "prior_log_count" not in walked
    assert "draft_count" not in walked
    assert "card_boost_post_settlement" not in walked
    conditions = next(
        item for item in observation["additionalProperty"] if item["name"] == "conditions"
    )
    assert conditions["propertyID"] == "oracle:condition"
    assert conditions["valueReference"]["@type"] == "Observation"
    compact = hv_feature_emphasis_names()
    json.dumps(compact)
    assert compact["boost_is_ridge_feature"] is False
    assert compact["winning_drafts_are_reference_bar"] is True
    assert compact["cash_is_objective"] is False
    assert compact["median_is_objective"] is False
    assert compact["lineup_size"] == 5
    assert "winning_drafts" in compact["chalk_off"]
    assert "weather_temp_f" in compact["conditions"]["external_pregame"]
    assert "global_prior_mean" in compact["conditions"]["player_profile"]
    assert "season" in compact["conditions"]["slate_conditions"]

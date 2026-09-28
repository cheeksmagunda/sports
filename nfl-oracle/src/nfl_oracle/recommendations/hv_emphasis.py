"""Live features that can put an HV-board row in the display top 10.

The train sample is every player on the HV/TDV leaderboard. High weight is
that board's display top 10. Draft count, winning drafts, and the ridge
``prior_log_count`` slot are not how a row enters that window.

Card boost is the display rank key and the optimizer score. It is not a
ridge coefficient. ``card_boost_post_settlement`` stays live-forbidden.
"""

from __future__ import annotations

from typing import Any

from oracle_core.schemaorg import observation, property_value, sports_event, with_context

from nfl_oracle.features.live import (
    INJURY_CATEGORIES,
    KICKOFF_SLOT_FEATURE_NAMES,
    REQUIRED_LIVE_OK_CONTEXT_FEATURES,
    WEATHER_FEATURE_NAMES,
)
from nfl_oracle.features.schema import feature_registry
from nfl_oracle.recommendations.model import RatingModel

# (feature name, FeatureSpec.group). The role is the emphasis bucket.
_SPEC_ROLES: dict[str, tuple[tuple[str, str], ...]] = {
    "usage": (
        ("player_prior_mean", "prior"),
        ("player_prior_median", "prior"),
        ("position_prior_mean", "prior"),
        ("position_prior_median", "prior"),
        ("team_prior_mean", "prior"),
        ("prior_n_games", "prior"),
        ("prior_fallback_level", "prior"),
        ("prior_started", "prior"),
        ("prior_minutes", "prior"),
        ("prior_did_not_play", "prior"),
    ),
    "matchup": (
        ("opponent_adjusted_prior", "prior"),
        ("opp_def_value_allowed_prior", "matchup"),
        ("home_away", "matchup"),
        ("opponent_team", "matchup"),
        ("is_divisional", "matchup"),
        ("team_moneyline", "matchup"),
        ("opponent_moneyline", "matchup"),
        ("last_ten_wins", "matchup"),
    ),
    "role": (
        ("position", "identity"),
        ("team_id", "identity"),
    ),
    "pace": (
        ("team_pace_prior", "pace"),
        ("opponent_pace_prior", "pace"),
    ),
    "slate": (
        ("overall_rank", "slate_meta"),
        ("kickoff_slot", "slate_meta"),
        ("days_rest", "calendar"),
    ),
    "injury": (
        ("injury_status", "injury"),
        ("injury_status_available", "injury"),
        ("injury_body_part", "injury"),
    ),
}

_RIDGE_CONTEXT_ROLES: dict[str, tuple[str, ...]] = {
    "usage": ("prior_started", "prior_minutes", "prior_did_not_play"),
    "matchup": (
        "opponent_adjusted_prior",
        "opp_def_value_allowed_prior",
        "home_away",
        "is_home",
        "is_divisional",
        "team_moneyline",
        "opponent_moneyline",
        "moneyline_available",
        "last_ten_wins",
    ),
    "pace": ("team_pace_prior", "opponent_pace_prior"),
    "slate": ("overall_rank", "days_rest", *KICKOFF_SLOT_FEATURE_NAMES),
    "injury": (
        "injury_status_available",
        "injury_body_part_hash",
        "injury_body_part_available",
        *(f"injury_{name}" for name in INJURY_CATEGORIES),
    ),
}

_CHALK_OFF: dict[str, str] = {
    "prior_log_count": "ridge slot exists and its coefficient is forced to 0",
    "draft_count": "not a feature and not a label",
    "winning_drafts": "not a label",
}

_RANK_KEY = "value * (top_slot + card_boost)"
_SCORE_LAW = "value * (slot_multiplier + card_boost)"


def hv_feature_emphasis() -> dict[str, Any]:
    """Catalog used by ``nfl-pipeline train``. Names that are not live fail closed."""

    registry = {spec.name: spec for spec in feature_registry()}
    feature_spec: list[dict[str, str]] = []
    for role, pairs in _SPEC_ROLES.items():
        for name, group in pairs:
            spec = registry.get(name)
            if spec is None or not spec.live_ok or not spec.train_ok or spec.group != group:
                raise ValueError(f"hv_emphasis_feature_invalid:{name}")
            if spec.group == "label_only" or name in {"draft_count", "prior_log_count"}:
                raise ValueError(f"hv_emphasis_feature_invalid:{name}")
            feature_spec.append({"name": name, "group": spec.group, "role": role})

    live_context = set(REQUIRED_LIVE_OK_CONTEXT_FEATURES)
    ridge_context: list[dict[str, str]] = []
    for role, names in _RIDGE_CONTEXT_ROLES.items():
        for name in names:
            if name not in live_context:
                raise ValueError(f"hv_emphasis_context_invalid:{name}")
            ridge_context.append({"name": name, "role": role})

    model_names = set(RatingModel.model_fields["feature_names"].default)
    if "prior_log_count" not in model_names:
        raise ValueError("hv_emphasis_chalk_slot_missing")
    ridge_core = tuple(
        name
        for name in RatingModel.model_fields["feature_names"].default
        if name not in {"intercept", "prior_log_count"}
    )
    settlement = registry["card_boost_post_settlement"]
    if settlement.live_ok:
        raise ValueError("hv_emphasis_post_settlement_boost_live")

    weather = tuple(name for name in (*WEATHER_FEATURE_NAMES, "weather_available"))
    report = {
        "sample": "every HV/TDV leaderboard row",
        "high_weight": f"display top 10 by {_RANK_KEY}",
        "draft_count_is_label": False,
        "winning_drafts_are_label": False,
        "feature_spec": feature_spec,
        "ridge_core": list(ridge_core),
        "ridge_context": ridge_context,
        "weather_not_emphasis": list(weather),
        "chalk_off": dict(_CHALK_OFF),
        "boost_interaction": {
            "rank_key": _RANK_KEY,
            "optimizer_score": _SCORE_LAW,
            "ridge_feature": False,
            "card_boost_post_settlement_live_ok": False,
        },
    }
    report["observation"] = _observation(report)
    return report


def hv_feature_emphasis_names() -> dict[str, Any]:
    """Compact name lists for the train JSON report."""

    full = hv_feature_emphasis()
    by_role: dict[str, list[str]] = {}
    for row in full["feature_spec"]:
        by_role.setdefault(row["role"], []).append(row["name"])
    context_by_role: dict[str, list[str]] = {}
    for row in full["ridge_context"]:
        context_by_role.setdefault(row["role"], []).append(row["name"])
    return {
        "feature_spec": by_role,
        "ridge_core": list(full["ridge_core"]),
        "ridge_context": context_by_role,
        "chalk_off": list(full["chalk_off"]),
        "boost_is_ridge_feature": False,
    }


def _observation(report: dict[str, Any]) -> dict[str, Any]:
    by_role: dict[str, list[str]] = {}
    for row in report["feature_spec"]:
        by_role.setdefault(str(row["role"]), []).append(str(row["name"]))
    properties = [
        property_value(name="draft count is label", value=False),
        property_value(name="winning drafts are label", value=False),
        property_value(name="prior_log_count coefficient", value=0),
        property_value(name="card boost is ridge feature", value=False),
        property_value(name="rank key", value=_RANK_KEY),
        property_value(name="score law", value=_SCORE_LAW),
        property_value(name="sample", value=report["sample"]),
        property_value(name="ridge core", value=", ".join(report["ridge_core"])),
    ]
    for role, names in by_role.items():
        properties.append(property_value(name=role, value=", ".join(names)))
    node = observation(
        about=sports_event(identifier="hv-tdv-leaderboard", name="HV/TDV contest board"),
        measured_property=property_value(name="HV top-10 feature emphasis"),
        value=len(report["feature_spec"]),
        unit_text="feature",
        additional_properties=properties,
    )
    return with_context(node)

"""Every pre-game feature mapped onto post-game HV/TDV leaderboard rows.

The train sample is every player on the HV/TDV leaderboard. High weight is
that board's display top 10. The feature set is every live pre-game
FeatureSpec, not a hand-picked subset: player profile, slate conditions,
and external pre-game factors. Draft count, winning drafts, and the ridge
``prior_log_count`` slot are not how a row enters that window.

Card boost is the display rank key and the optimizer score. It is not a
ridge coefficient. ``card_boost_post_settlement`` stays live-forbidden.
"""

from __future__ import annotations

from typing import Any

from oracle_core.contest_max import hv_objective_flags
from oracle_core.schemaorg import observation, property_value, sports_event, with_context

from nfl_oracle.features.live import (
    REQUIRED_LIVE_OK_CONTEXT_FEATURES,
    WEATHER_FEATURE_NAMES,
)
from nfl_oracle.features.schema import FeatureSpec, feature_registry
from nfl_oracle.labels.schema import LIVE_FEATURE_BLACKLIST
from nfl_oracle.recommendations.model import RatingModel

_LEAKAGE_NAMES = frozenset(
    {
        "card_boost_post_settlement",
        "same_slate_final_value",
        "base_boosted_value",
        "draft_stats_score",
        "draft_stats_rank",
        *LIVE_FEATURE_BLACKLIST,
    }
)

_CHALK_OFF: dict[str, str] = {
    "prior_log_count": "ridge slot exists and its coefficient is forced to 0",
    "draft_count": "not a feature and not a label",
    "winning_drafts": "not a label",
}

_RANK_KEY = "value * (top_slot + card_boost)"
_SCORE_LAW = "value * (slot_multiplier + card_boost)"


def _is_pregame(spec: FeatureSpec) -> bool:
    """Live train feature. Same-slate finals and chalk channels stay out."""

    if spec.name in _LEAKAGE_NAMES or spec.name in {"draft_count", "prior_log_count"}:
        return False
    if spec.group == "label_only" or not spec.live_ok or not spec.train_ok:
        return False
    return True


def _condition_bucket(spec: FeatureSpec) -> str:
    """One condition class per pre-game spec. The classes cover the registry."""

    if spec.group in {"weather", "injury"} or spec.name in {
        "team_moneyline",
        "opponent_moneyline",
        "last_ten_wins",
    }:
        return "external_pregame"
    if spec.group == "identity" or spec.name.startswith(
        ("player_", "prior_", "position_prior", "global_prior", "team_prior")
    ):
        return "player_profile"
    return "slate_conditions"


def _ridge_role(name: str) -> str:
    if name in {*WEATHER_FEATURE_NAMES, "weather_available"}:
        return "external_pregame"
    if name.startswith("injury"):
        return "injury"
    if name in {"team_pace_prior", "opponent_pace_prior"}:
        return "pace"
    if name in {"overall_rank", "days_rest"} or name.startswith("kickoff_slot_"):
        return "slate"
    if name in {"prior_started", "prior_minutes", "prior_did_not_play"}:
        return "usage"
    return "matchup"


def hv_feature_emphasis() -> dict[str, Any]:
    """Catalog used by ``nfl-pipeline train``. A missing live spec fails closed."""

    specs = feature_registry()
    feature_spec = [
        {"name": spec.name, "group": spec.group, "role": spec.group}
        for spec in specs
        if _is_pregame(spec)
    ]
    pregame_names = {row["name"] for row in feature_spec}
    live_names = {spec.name for spec in specs if spec.live_ok and spec.train_ok}
    if pregame_names != live_names - _LEAKAGE_NAMES:
        missing = sorted(live_names - _LEAKAGE_NAMES - pregame_names)
        raise ValueError(f"hv_emphasis_pregame_incomplete:{','.join(missing)}")
    for spec in specs:
        if spec.group == "label_only" and spec.live_ok:
            raise ValueError(f"hv_emphasis_leakage_live:{spec.name}")
    conditions = [
        {
            "name": row["name"],
            "group": row["group"],
            "role": _condition_bucket(next(spec for spec in specs if spec.name == row["name"])),
        }
        for row in feature_spec
    ]
    if {row["name"] for row in conditions} != pregame_names:
        raise ValueError("hv_emphasis_conditions_incomplete")
    if len(conditions) != len(pregame_names):
        raise ValueError("hv_emphasis_conditions_duplicate")

    ridge_context = [
        {"name": name, "role": _ridge_role(name)} for name in REQUIRED_LIVE_OK_CONTEXT_FEATURES
    ]
    if {row["name"] for row in ridge_context} != set(REQUIRED_LIVE_OK_CONTEXT_FEATURES):
        raise ValueError("hv_emphasis_context_incomplete")

    model_names = set(RatingModel.model_fields["feature_names"].default)
    if "prior_log_count" not in model_names:
        raise ValueError("hv_emphasis_chalk_slot_missing")
    ridge_core = tuple(
        name
        for name in RatingModel.model_fields["feature_names"].default
        if name not in {"intercept", "prior_log_count"}
    )
    settlement = next(spec for spec in specs if spec.name == "card_boost_post_settlement")
    if settlement.live_ok:
        raise ValueError("hv_emphasis_post_settlement_boost_live")

    report = {
        "sample": "every post-game HV/TDV leaderboard row",
        "high_weight": f"display top 10 by {_RANK_KEY}",
        "draft_count_is_label": False,
        **hv_objective_flags(),
        "feature_spec": feature_spec,
        "conditions": conditions,
        "ridge_core": list(ridge_core),
        "ridge_context": ridge_context,
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
    by_condition: dict[str, list[str]] = {}
    for row in full["conditions"]:
        by_condition.setdefault(row["role"], []).append(row["name"])
    context_by_role: dict[str, list[str]] = {}
    for row in full["ridge_context"]:
        context_by_role.setdefault(row["role"], []).append(row["name"])
    return {
        "feature_spec": by_role,
        "conditions": by_condition,
        "ridge_core": list(full["ridge_core"]),
        "ridge_context": context_by_role,
        "chalk_off": list(full["chalk_off"]),
        "boost_is_ridge_feature": False,
        "objective": full["objective"],
        "shape_condition_objective": full["shape_condition_objective"],
        "lineup_size": full["lineup_size"],
        "winning_drafts_are_reference_bar": full["winning_drafts_are_reference_bar"],
        "cash_is_objective": full["cash_is_objective"],
        "median_is_objective": full["median_is_objective"],
    }


def _feature_spec_property(row: dict[str, str]) -> dict[str, Any]:
    """One live FeatureSpec as a schema.org PropertyValue."""

    return property_value(
        name=row["name"],
        value=True,
        property_id="oracle:FeatureSpec",
        additional={"group": row["group"], "role": row["role"], "live_ok": True},
    )


def _role_observation(role: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    """Observation whose properties are the FeatureSpecs in one emphasis role."""

    return observation(
        about=sports_event(identifier=f"hv-tdv-{role}", name=f"HV/TDV {role}"),
        measured_property=property_value(name="FeatureSpec role", property_id="oracle:FeatureSpec"),
        value=len(rows),
        unit_text="feature",
        additional_properties=[_feature_spec_property(row) for row in rows],
    )


def _observation(report: dict[str, Any]) -> dict[str, Any]:
    """Parent Observation. Each role recurses to its own FeatureSpec Observation."""

    by_role: dict[str, list[dict[str, str]]] = {}
    for row in report["feature_spec"]:
        by_role.setdefault(str(row["role"]), []).append(row)
    properties = [
        property_value(name="objective", value=report["objective"]),
        property_value(
            name="shape and condition objective",
            value=report["shape_condition_objective"],
        ),
        property_value(name="lineup size", value=report["lineup_size"]),
        property_value(name="draft count is label", value=False),
        property_value(name="winning drafts are label", value=False),
        property_value(name="winning drafts are a reference bar", value=True),
        property_value(name="cash is objective", value=False),
        property_value(name="median is objective", value=False),
        property_value(name="prior_log_count coefficient", value=0),
        property_value(name="card boost is ridge feature", value=False),
        property_value(name="rank key", value=_RANK_KEY),
        property_value(name="score law", value=_SCORE_LAW),
        property_value(name="sample", value=report["sample"]),
        property_value(
            name="ridge core",
            value=len(report["ridge_core"]),
            value_reference=observation(
                about=sports_event(identifier="hv-tdv-ridge-core", name="HV/TDV ridge core"),
                measured_property=property_value(name="ridge core"),
                value=len(report["ridge_core"]),
                unit_text="feature",
                additional_properties=[
                    property_value(name=name, value=True, property_id="oracle:ridge-slot")
                    for name in report["ridge_core"]
                ],
            ),
        ),
    ]
    for role, rows in by_role.items():
        properties.append(
            property_value(
                name=role,
                value=len(rows),
                property_id="oracle:FeatureSpec",
                value_reference=_role_observation(role, rows),
            )
        )
    by_condition: dict[str, list[dict[str, str]]] = {}
    for row in report["conditions"]:
        by_condition.setdefault(str(row["role"]), []).append(row)
    condition_properties = [
        property_value(
            name=condition,
            value=len(rows),
            property_id="oracle:condition",
            value_reference=_role_observation(condition, rows),
        )
        for condition, rows in by_condition.items()
    ]
    properties.append(
        property_value(
            name="conditions",
            value=len(report["conditions"]),
            property_id="oracle:condition",
            value_reference=observation(
                about=sports_event(
                    identifier="hv-tdv-conditions",
                    name="HV/TDV conditions",
                ),
                measured_property=property_value(name="conditions that produced the board"),
                value=len(by_condition),
                unit_text="condition",
                additional_properties=condition_properties,
            ),
        )
    )
    node = observation(
        about=sports_event(identifier="hv-tdv-leaderboard", name="HV/TDV contest board"),
        measured_property=property_value(name="pre-game features of the HV/TDV board"),
        value=len(report["feature_spec"]),
        unit_text="feature",
        additional_properties=properties,
    )
    return with_context(node)

"""Own-model feature map for WNBA EB + serving_features (#523).

LightGBM heads remain optional behind ``WNBA_SERVE_PRIMARY=heads``; the
default forward path is EBHierarchicalBaseline (cohort + player alpha +
pace / vegas / boost terms) fed by serve-time ``head_features`` and pool
``card_boost``. Starter confirmation is a serve-time multiplier, not a
raw EB float.
"""

from __future__ import annotations

from typing import Literal

from wnba_oracle.features.spec import _BASE_FEATURES, COHORT_EXTRA_FEATURES

WnbaOwnStatus = Literal[
    "eb_core",
    "eb_pace",
    "eb_vegas",
    "eb_boost",
    "serve_starter_multiplier",
    "serving_to_picker_via_minutes",
    "lgbm_optional",
    "monotone_documented",
]


EB_CORE_FEATURES: frozenset[str] = frozenset({"cohort", "player_id"})
EB_PACE_FEATURES: frozenset[str] = frozenset({"team_pace", "opp_pace", "game_pace_implied"})
# Fused from Job 1 enrichment into head_features (#523) so they enter the
# design matrix for optional LGBM heads and future EB/ridge terms.
ENRICHMENT_FUSED_FEATURES: frozenset[str] = frozenset(
    {
        "card_boost",
        "primary_ranking",
        "vegas_total",
        "vegas_spread",
        "is_home",
        "is_starter",
        "starter_slot",
        "is_confirmed_starter",
    }
)
EB_VEGAS_FEATURES: frozenset[str] = frozenset({"vegas_total", "implied_team_total", "vegas_spread"})
EB_BOOST_FEATURES: frozenset[str] = frozenset({"card_boost"})
STARTER_SERVE_FEATURES: frozenset[str] = frozenset({"is_confirmed_starter", "starter_slot"})

MONOTONE_CONSTRAINT_NAMES: frozenset[str] = frozenset(
    {
        "mins_l5",
        "mins_l10",
        "pred_minutes",
        "usg_pct_l10",
        "opp_def_rtg",
        "is_back_to_back",
        "vegas_total",
        "implied_team_total",
    }
)


def monotone_constraint_names() -> frozenset[str]:
    return MONOTONE_CONSTRAINT_NAMES


def serving_base_feature_names() -> frozenset[str]:
    extras = {name for names in COHORT_EXTRA_FEATURES.values() for name in names}
    return frozenset(_BASE_FEATURES) | extras


def classify_serving_feature(name: str) -> WnbaOwnStatus:
    if name in EB_PACE_FEATURES:
        return "eb_pace"
    if name in EB_VEGAS_FEATURES:
        return "eb_vegas"
    if name in EB_BOOST_FEATURES:
        return "eb_boost"
    if name in STARTER_SERVE_FEATURES:
        return "serve_starter_multiplier"
    if name in ENRICHMENT_FUSED_FEATURES:
        # is_home / primary_ranking / is_starter land in head_features via job1
        # fuse even when they are not EB linear terms yet.
        return "lgbm_optional"
    if name in {"cohort"}:
        return "eb_core"
    if name in {
        "mins_l5",
        "mins_l10",
        "days_rest",
        "is_back_to_back",
        "season_game_number",
    }:
        return "serving_to_picker_via_minutes"
    if name in MONOTONE_CONSTRAINT_NAMES:
        return "monotone_documented"
    return "lgbm_optional"


def wnba_own_model_gap_matrix() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name in sorted(serving_base_feature_names()):
        status = classify_serving_feature(name)
        rows.append({"feature": name, "status": status, "surface": _surface(status)})
    rows.extend(
        {
            "feature": name,
            "status": "monotone_documented",
            "surface": "models.yaml monotone; serve via head_features when present",
        }
        for name in sorted(MONOTONE_CONSTRAINT_NAMES - serving_base_feature_names())
    )
    return rows


def _surface(status: WnbaOwnStatus) -> str:
    if status == "eb_core":
        return "EBHierarchicalBaseline cohort+alpha"
    if status == "eb_pace":
        return "EBHierarchicalBaseline pace terms"
    if status == "eb_vegas":
        return "EBHierarchicalBaseline vegas_total term (+ implied via head)"
    if status == "eb_boost":
        return "EBHierarchicalBaseline card_boost term"
    if status == "serve_starter_multiplier":
        return "serve _starter_multiplier on EB / ladder"
    if status == "serving_to_picker_via_minutes":
        return "minutes blend / schedule path"
    if status == "monotone_documented":
        return "models.yaml monotone (LGBM optional)"
    return "LGBM head optional; skipped when serve_primary=eb"

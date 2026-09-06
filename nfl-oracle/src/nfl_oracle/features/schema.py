"""FeatureSpec v1 — availability clocks + train/live flags."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from nfl_oracle.labels.schema import LIVE_FEATURE_BLACKLIST

DType = Literal["float", "int", "str", "bool", "categorical"]
FeatureGroup = Literal[
    "calendar",
    "identity",
    "prior",
    "slate_meta",
    "matchup",
    "label_only",
]


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    dtype: DType
    train_ok: bool
    live_ok: bool
    availability_rule: str
    description: str = ""
    group: FeatureGroup = "prior"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def feature_registry() -> tuple[FeatureSpec, ...]:
    """Honest registry — expand carefully; keep same-slate finals live-forbidden."""

    return (
        FeatureSpec(
            name="season",
            dtype="int",
            train_ok=True,
            live_ok=True,
            availability_rule="known_at_slate_construction",
            description="NFL season year for the game/slate.",
            group="calendar",
        ),
        FeatureSpec(
            name="week",
            dtype="int",
            train_ok=True,
            live_ok=True,
            availability_rule="known_from_public_schedule_or_slate_meta",
            description="Season week when schedule/slate is known.",
            group="calendar",
        ),
        FeatureSpec(
            name="gameday",
            dtype="str",
            train_ok=True,
            live_ok=True,
            availability_rule="known_from_public_schedule_or_slate_meta",
            description="ISO gameday from offline schedule when available.",
            group="calendar",
        ),
        FeatureSpec(
            name="kickoff_slot",
            dtype="categorical",
            train_ok=True,
            live_ok=True,
            availability_rule="known_from_public_schedule_or_slate_meta",
            description="Coarse kickoff bucket (early/late/snf/mnf) when slate meta known.",
            group="slate_meta",
        ),
        FeatureSpec(
            name="home_away",
            dtype="categorical",
            train_ok=True,
            live_ok=True,
            availability_rule="known_from_public_schedule_or_slate_meta",
            description="Player team home/away vs opponent from schedule.",
            group="matchup",
        ),
        FeatureSpec(
            name="opponent_team",
            dtype="str",
            train_ok=True,
            live_ok=True,
            availability_rule="known_from_public_schedule_or_slate_meta",
            description="Opponent team abbreviation from offline schedule.",
            group="matchup",
        ),
        FeatureSpec(
            name="position",
            dtype="categorical",
            train_ok=True,
            live_ok=True,
            availability_rule="known_from_identity_or_slate_meta",
            description="Player position from identity map / slate.",
            group="identity",
        ),
        FeatureSpec(
            name="team_id",
            dtype="int",
            train_ok=True,
            live_ok=True,
            availability_rule="known_from_identity_or_slate_meta",
            description="Real team id from identity map when present.",
            group="identity",
        ),
        FeatureSpec(
            name="player_prior_mean",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule="fit_on_seasons_strictly_earlier_than_decision_season",
            description="Walk-forward player mean prior; falls back to position/global.",
            group="prior",
        ),
        FeatureSpec(
            name="player_prior_median",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule="fit_on_seasons_strictly_earlier_than_decision_season",
            description="Walk-forward player median Real value prior when sample allows.",
            group="prior",
        ),
        FeatureSpec(
            name="position_prior_mean",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule="fit_on_seasons_strictly_earlier_than_decision_season",
            description="Walk-forward position mean Real value prior.",
            group="prior",
        ),
        FeatureSpec(
            name="position_prior_median",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule="fit_on_seasons_strictly_earlier_than_decision_season",
            description="Walk-forward position median Real value prior.",
            group="prior",
        ),
        FeatureSpec(
            name="global_prior_mean",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule="fit_on_seasons_strictly_earlier_than_decision_season",
            description="Walk-forward global mean Real value prior.",
            group="prior",
        ),
        FeatureSpec(
            name="team_prior_mean",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule="fit_on_seasons_strictly_earlier_than_decision_season",
            description="Walk-forward mean Real value for player's team_id when known.",
            group="prior",
        ),
        FeatureSpec(
            name="prior_n_games",
            dtype="int",
            train_ok=True,
            live_ok=True,
            availability_rule="count_of_train_labels_strictly_earlier_than_decision_season",
            description="Sample size supporting the player prior (0 if fallback).",
            group="prior",
        ),
        FeatureSpec(
            name="prior_fallback_level",
            dtype="categorical",
            train_ok=True,
            live_ok=True,
            availability_rule="derived_from_walk_forward_prior_fit",
            description="Which prior tier fired: player|position|team|global.",
            group="prior",
        ),
        FeatureSpec(
            name="days_rest",
            dtype="int",
            train_ok=True,
            live_ok=True,
            availability_rule="known_from_public_schedule_when_prior_game_mapped",
            description="Days since player's previous scheduled game when history known.",
            group="calendar",
        ),
        FeatureSpec(
            name="card_boost_post_settlement",
            dtype="float",
            train_ok=True,
            live_ok=False,
            availability_rule="post_settlement_contest_stats_only_pre_lock_unobserved",
            description=(
                "multiplierBonus from finalized contest stats. Search showed zeros "
                "pregame; not a live feature until pre-lock visibility is proven."
            ),
            group="label_only",
        ),
        FeatureSpec(
            name="same_slate_final_value",
            dtype="float",
            train_ok=True,
            live_ok=False,
            availability_rule="post_finalization_label_only",
            description="Realized Real value — train label; live forbidden.",
            group="label_only",
        ),
    )


def features_document() -> dict[str, Any]:
    specs = feature_registry()
    by_group: dict[str, int] = {}
    for spec in specs:
        by_group[spec.group] = by_group.get(spec.group, 0) + 1
    live = live_ok_feature_names()
    return {
        "name": "nfl_feature_schema",
        "version": 1,
        "features": [s.to_dict() for s in specs],
        "feature_count": len(specs),
        "live_ok_count": len(live),
        "live_ok": list(live),
        "group_counts": dict(sorted(by_group.items())),
        "live_blacklist": list(LIVE_FEATURE_BLACKLIST),
        "observation_only": True,
        "contest_entry": False,
    }


def live_ok_feature_names() -> tuple[str, ...]:
    """Names marked live_ok and not on the same-slate blacklist."""

    return tuple(
        spec.name
        for spec in feature_registry()
        if spec.live_ok and spec.name not in LIVE_FEATURE_BLACKLIST
    )


def features_by_group(group: FeatureGroup) -> tuple[FeatureSpec, ...]:
    return tuple(spec for spec in feature_registry() if spec.group == group)

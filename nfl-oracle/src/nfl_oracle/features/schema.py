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
    "injury",
    "weather",
    "pace",
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
    # Offline stub marker: True means values may be null/placeholder until a
    # live capture path is wired. Does not affect live_ok gating.
    offline_stub: bool = False

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
            name="is_divisional",
            dtype="bool",
            train_ok=True,
            live_ok=True,
            availability_rule="known_from_public_schedule_team_divisions",
            description="True when opponent is in the same division (offline schedule join).",
            group="matchup",
            offline_stub=True,
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
            name="opponent_adjusted_prior",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule=(
                "fit_on_seasons_strictly_earlier_than_decision_season;"
                "offline_stub_until_opp_def_join_wired"
            ),
            description=(
                "Player/position prior adjusted by opponent defensive value-allowed "
                "prior. Offline stub may emit null until join is wired."
            ),
            group="prior",
            offline_stub=True,
        ),
        FeatureSpec(
            name="opp_def_value_allowed_prior",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule=(
                "fit_on_seasons_strictly_earlier_than_decision_season;"
                "offline_stub_until_opponent_defense_table_wired"
            ),
            description=(
                "Walk-forward mean Real value allowed by opponent defense (by "
                "position when available). Offline stub until table exists."
            ),
            group="matchup",
            offline_stub=True,
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
            name="injury_status",
            dtype="categorical",
            train_ok=True,
            live_ok=True,
            availability_rule=("public_injury_report_when_captured_pre_lock_else_null_stub"),
            description=(
                "Coarse injury designation (out/doubtful/questionable/probable/"
                "healthy/unknown). Offline stub emits null until capture wired."
            ),
            group="injury",
            offline_stub=True,
        ),
        FeatureSpec(
            name="injury_status_available",
            dtype="bool",
            train_ok=True,
            live_ok=True,
            availability_rule="true_when_injury_status_source_captured_pre_lock",
            description="Whether injury_status was observed pre-lock (not inferred).",
            group="injury",
            offline_stub=True,
        ),
        FeatureSpec(
            name="weather_temp_f",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule=("public_forecast_for_outdoor_stadium_pre_lock_else_null_stub"),
            description="Forecast kickoff temperature °F when outdoor and available.",
            group="weather",
            offline_stub=True,
        ),
        FeatureSpec(
            name="weather_wind_mph",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule=("public_forecast_for_outdoor_stadium_pre_lock_else_null_stub"),
            description="Forecast kickoff wind mph when outdoor and available.",
            group="weather",
            offline_stub=True,
        ),
        FeatureSpec(
            name="weather_precip_prob",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule=("public_forecast_for_outdoor_stadium_pre_lock_else_null_stub"),
            description="Forecast precipitation probability [0,1] when available.",
            group="weather",
            offline_stub=True,
        ),
        FeatureSpec(
            name="weather_available",
            dtype="bool",
            train_ok=True,
            live_ok=True,
            availability_rule="true_when_weather_forecast_captured_pre_lock",
            description="Whether weather fields were observed pre-lock.",
            group="weather",
            offline_stub=True,
        ),
        FeatureSpec(
            name="team_pace_prior",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule=(
                "fit_on_seasons_strictly_earlier_than_decision_season;"
                "offline_stub_until_pace_table_wired"
            ),
            description=(
                "Team offensive pace prior (plays/game or Real-value proxy). "
                "Offline stub until pace table is wired."
            ),
            group="pace",
            offline_stub=True,
        ),
        FeatureSpec(
            name="opponent_pace_prior",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule=(
                "fit_on_seasons_strictly_earlier_than_decision_season;"
                "offline_stub_until_pace_table_wired"
            ),
            description="Opponent pace prior for matchup context. Offline stub.",
            group="pace",
            offline_stub=True,
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
    stub_names: list[str] = []
    for spec in specs:
        by_group[spec.group] = by_group.get(spec.group, 0) + 1
        if spec.offline_stub:
            stub_names.append(spec.name)
    live = live_ok_feature_names()
    return {
        "name": "nfl_feature_schema",
        "version": 1,
        "features": [s.to_dict() for s in specs],
        "feature_count": len(specs),
        "live_ok_count": len(live),
        "live_ok": list(live),
        "offline_stub_features": stub_names,
        "offline_stub_count": len(stub_names),
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


def offline_stub_feature_names() -> tuple[str, ...]:
    return tuple(spec.name for spec in feature_registry() if spec.offline_stub)

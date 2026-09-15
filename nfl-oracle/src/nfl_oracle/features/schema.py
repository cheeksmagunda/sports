"""FeatureSpec v1: availability clocks + train/live flags."""

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
    """Honest registry. Expand carefully; keep same-slate finals live-forbidden."""

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
            description=(
                "True when opponent shares the player's division. Static 2002+ "
                "division map in nfl_oracle.features.matchup, joined in "
                "recommendations.context (#189)."
            ),
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
            name="opponent_adjusted_prior",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule=(
                "fit_on_seasons_strictly_earlier_than_decision_season;"
                "from_historical_context_opponent_value_allowed_join"
            ),
            description=(
                "Player (else position) Real value prior scaled by the clamped "
                "opponent-defense factor. Absent when either side lacks "
                "walk-forward support; never emitted as zero (#189)."
            ),
            group="prior",
        ),
        FeatureSpec(
            name="opp_def_value_allowed_prior",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule=(
                "fit_on_seasons_strictly_earlier_than_decision_season;"
                "from_corpus_g_real_value_allowed_by_opponent_defense"
            ),
            description=(
                "Walk-forward mean Real value allowed by the opponent defense "
                "(position split when it has support), built from finalized "
                "Corpus G box rows keyed by opponent_team_id (#189)."
            ),
            group="matchup",
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
            availability_rule="real_card_injury_status_when_captured_pre_lock_else_null",
            description=(
                "Coarse injury designation (active/questionable/doubtful/out/"
                "inactive/ir/suspended/limited/dnp/full/unknown) from the Real "
                "card injuryStatus field. Null when the field is absent."
            ),
            group="injury",
        ),
        FeatureSpec(
            name="injury_status_available",
            dtype="bool",
            train_ok=True,
            live_ok=True,
            availability_rule="true_when_injury_status_source_captured_pre_lock",
            description=(
                "Whether the Real card actually carried injuryStatus pre-lock. "
                "An unrecognized designation is still an observation."
            ),
            group="injury",
        ),
        FeatureSpec(
            name="weather_temp_f",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule="nws_forecast_for_outdoor_stadium_pre_lock_else_null",
            description=(
                "Forecast kickoff temperature in F from the NWS capture in "
                "recommendations.sources. Null indoors or when uncaptured."
            ),
            group="weather",
        ),
        FeatureSpec(
            name="weather_wind_mph",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule="nws_forecast_for_outdoor_stadium_pre_lock_else_null",
            description=(
                "Forecast kickoff wind mph from the NWS capture. Null indoors or when uncaptured."
            ),
            group="weather",
        ),
        FeatureSpec(
            name="weather_precip_prob",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule="nws_forecast_for_outdoor_stadium_pre_lock_else_null",
            description=(
                "Forecast precipitation probability [0,1] from the NWS "
                "capture. Null indoors or when uncaptured."
            ),
            group="weather",
        ),
        FeatureSpec(
            name="weather_available",
            dtype="bool",
            train_ok=True,
            live_ok=True,
            availability_rule="true_when_weather_forecast_captured_pre_lock",
            description=(
                "Whether any weather field was observed pre-lock. False "
                "indoors and when no forecast was captured; magnitudes are "
                "never invented to fill the gap."
            ),
            group="weather",
        ),
        FeatureSpec(
            name="team_pace_prior",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule=(
                "fit_on_seasons_strictly_earlier_than_decision_season;"
                "from_historical_context_team_plays_prior"
            ),
            description=(
                "Team offensive pace prior (plays/game proxy from earlier "
                "attempts/carries/sacks). Wired via recommendations.context "
                "HistoricalContext (#185 enable historical linking)."
            ),
            group="pace",
            offline_stub=False,
        ),
        FeatureSpec(
            name="opponent_pace_prior",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule=(
                "fit_on_seasons_strictly_earlier_than_decision_season;"
                "from_historical_context_opponent_plays_prior"
            ),
            description=(
                "Opponent pace prior for matchup context. Wired via "
                "recommendations.context HistoricalContext (#185)."
            ),
            group="pace",
            offline_stub=False,
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
            description="Realized Real value: train label only; live forbidden.",
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

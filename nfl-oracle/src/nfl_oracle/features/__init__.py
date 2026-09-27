"""Feature schema scaffolding for nfl-oracle."""

from nfl_oracle.features.live import (
    REQUIRED_LIVE_OK_CONTEXT_FEATURES,
    REQUIRED_SLATE_CONTEXT_FEATURES,
    injury_category,
    injury_features,
    injury_indicator_features,
    kickoff_slot_features,
    weather_features,
)
from nfl_oracle.features.matchup import (
    NFL_DIVISIONS,
    division_for_team,
    is_divisional_matchup,
)
from nfl_oracle.features.opponent_defense import (
    RealValueHistoryIndex,
    observations_from_history,
    opponent_adjusted_prior,
    opponent_defense_factor,
)
from nfl_oracle.features.own_model_map import own_model_gap_matrix
from nfl_oracle.features.rows import build_prior_rows_for_players, prior_feature_row
from nfl_oracle.features.rs_aliases import (
    REQUIRED_RS_POOL_CONTEXT_FEATURES,
    RS_FEATURE_ALIASES,
    extract_pool_card_features,
)
from nfl_oracle.features.rs_field_map import rs_field_matrix
from nfl_oracle.features.schema import (
    FeatureSpec,
    feature_registry,
    features_by_group,
    features_document,
    live_ok_feature_names,
    offline_stub_feature_names,
)
from nfl_oracle.features.stubs import offline_stub_feature_row

__all__ = [
    "NFL_DIVISIONS",
    "REQUIRED_LIVE_OK_CONTEXT_FEATURES",
    "REQUIRED_RS_POOL_CONTEXT_FEATURES",
    "REQUIRED_SLATE_CONTEXT_FEATURES",
    "RS_FEATURE_ALIASES",
    "FeatureSpec",
    "RealValueHistoryIndex",
    "build_prior_rows_for_players",
    "division_for_team",
    "extract_pool_card_features",
    "feature_registry",
    "features_by_group",
    "features_document",
    "injury_category",
    "injury_features",
    "injury_indicator_features",
    "is_divisional_matchup",
    "kickoff_slot_features",
    "live_ok_feature_names",
    "observations_from_history",
    "offline_stub_feature_names",
    "offline_stub_feature_row",
    "opponent_adjusted_prior",
    "opponent_defense_factor",
    "own_model_gap_matrix",
    "prior_feature_row",
    "rs_field_matrix",
    "weather_features",
]

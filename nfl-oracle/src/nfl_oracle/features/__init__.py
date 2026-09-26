"""Feature schema scaffolding for nfl-oracle."""

from nfl_oracle.features.live import (
    canonical_live_context_feature_names,
    injury_category,
    injury_features,
    injury_indicator_features,
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
from nfl_oracle.features.rows import build_prior_rows_for_players, prior_feature_row
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
    "FeatureSpec",
    "RealValueHistoryIndex",
    "build_prior_rows_for_players",
    "canonical_live_context_feature_names",
    "division_for_team",
    "feature_registry",
    "features_by_group",
    "features_document",
    "injury_category",
    "injury_features",
    "injury_indicator_features",
    "is_divisional_matchup",
    "live_ok_feature_names",
    "observations_from_history",
    "offline_stub_feature_names",
    "offline_stub_feature_row",
    "opponent_adjusted_prior",
    "opponent_defense_factor",
    "prior_feature_row",
    "weather_features",
]

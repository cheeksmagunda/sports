"""Feature schema scaffolding for nfl-oracle."""

from nfl_oracle.features.rows import build_prior_rows_for_players, prior_feature_row
from nfl_oracle.features.schema import (
    FeatureSpec,
    feature_registry,
    features_by_group,
    features_document,
    live_ok_feature_names,
)

__all__ = [
    "FeatureSpec",
    "build_prior_rows_for_players",
    "feature_registry",
    "features_by_group",
    "features_document",
    "live_ok_feature_names",
    "prior_feature_row",
]

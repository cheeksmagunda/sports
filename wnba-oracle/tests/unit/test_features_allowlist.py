"""Pre-game feature allowlist tests."""

from __future__ import annotations

import pytest

from wnba_oracle.features.allowlist import (
    FeatureLeakageError,
    assert_predict_features_allowed,
)


def test_allowed_columns_pass() -> None:
    assert_predict_features_allowed(
        ["player_id", "team", "card_boost", "mins_l10", "vegas_total"]
    )


def test_unknown_column_raises_leakage_error() -> None:
    with pytest.raises(FeatureLeakageError, match="post_game_real_score"):
        assert_predict_features_allowed(
            ["player_id", "post_game_real_score"]
        )


def test_post_game_feature_blocked() -> None:
    """real_score must NEVER appear in the predict feature matrix."""
    with pytest.raises(FeatureLeakageError):
        assert_predict_features_allowed(["player_id", "real_score"])

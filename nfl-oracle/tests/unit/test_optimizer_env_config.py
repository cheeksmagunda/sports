"""Env-driven optimizer construction config (max-value / race mode) for #453.

Serving defaults via ``optimizer_config_from_env`` are win-draft ``max_value``
(#505 / #552). Bare ``OptimizerConfig()`` stays diversified for call sites that
construct configs in-process. The ``max_value`` profile drops the diversity
floor to 1/1; upside/field weight knobs tune the contest-utility re-rank.
"""

from __future__ import annotations

import pytest

from nfl_oracle.recommendations.optimizer import (
    OPTIMIZER_PROFILE_PRESETS,
    OptimizerConfig,
    optimizer_config_from_env,
)


def test_empty_env_reproduces_production_defaults() -> None:
    cfg = optimizer_config_from_env({})
    default = OptimizerConfig()
    # #505 / #453: unset env serves max_value (win-draft), not diversified.
    assert cfg.profile == "max_value"
    assert cfg.min_distinct_teams == 1
    assert cfg.min_distinct_games == 1
    assert cfg.upside_weight == default.upside_weight
    assert cfg.field_weight == default.field_weight
    assert cfg.objective == "total_value"


def test_max_value_profile_drops_diversity_floor_to_one() -> None:
    cfg = optimizer_config_from_env({"NFL_OPTIMIZER_PROFILE": "max_value"})
    assert cfg.profile == "max_value"
    assert cfg.min_distinct_teams == 1
    assert cfg.min_distinct_games == 1
    assert OPTIMIZER_PROFILE_PRESETS["max_value"] == (1, 1)


def test_explicit_diversity_overrides_win_over_profile_preset() -> None:
    cfg = optimizer_config_from_env(
        {
            "NFL_OPTIMIZER_PROFILE": "max_value",
            "NFL_OPTIMIZER_MIN_DISTINCT_TEAMS": "2",
            "NFL_OPTIMIZER_MIN_DISTINCT_GAMES": "2",
        }
    )
    assert cfg.min_distinct_teams == 2
    assert cfg.min_distinct_games == 2
    assert cfg.profile == "max_value"


def test_weight_knobs_are_read_and_range_checked() -> None:
    cfg = optimizer_config_from_env(
        {"NFL_OPTIMIZER_UPSIDE_WEIGHT": "1.0", "NFL_OPTIMIZER_FIELD_WEIGHT": "0.0"}
    )
    assert cfg.upside_weight == 1.0
    assert cfg.field_weight == 0.0


@pytest.mark.parametrize(
    "env",
    [
        {"NFL_OPTIMIZER_PROFILE": "bogus"},
        {"NFL_OPTIMIZER_MIN_DISTINCT_TEAMS": "0"},
        {"NFL_OPTIMIZER_MIN_DISTINCT_TEAMS": "9"},
        {"NFL_OPTIMIZER_MIN_DISTINCT_GAMES": "not-an-int"},
        {"NFL_OPTIMIZER_UPSIDE_WEIGHT": "9"},
        {"NFL_OPTIMIZER_FIELD_WEIGHT": "-1"},
        {"NFL_OPTIMIZER_UPSIDE_WEIGHT": "abc"},
    ],
)
def test_invalid_env_fails_closed(env: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        optimizer_config_from_env(env)


def test_profile_is_recorded_on_the_recommendation_artifact() -> None:
    from datetime import timedelta

    from nfl_oracle.recommendations.optimizer import ScoringPolicy, optimize
    from tests.unit.test_recommendation_model_optimizer import BASE, projections, slate

    target = slate(one_team=True, one_game=True)
    default_cfg = optimize(
        target,
        projections(target),
        decision_at=BASE + timedelta(days=8),
        scoring_policy=ScoringPolicy(),
        config=optimizer_config_from_env({"NFL_OPTIMIZER_PROFILE": "diversified"}),
    )
    assert default_cfg.construction_profile == "max_value"
    assert default_cfg.requested_distinct_teams == 1
    assert default_cfg.requested_distinct_games == 1
    assert default_cfg.diversity_relaxed is False

    diversified = optimize(
        target,
        projections(target),
        decision_at=BASE + timedelta(days=8),
        scoring_policy=ScoringPolicy(),
        config=optimizer_config_from_env({"NFL_OPTIMIZER_PROFILE": "diversified"}),
    )
    assert diversified.construction_profile == "diversified"

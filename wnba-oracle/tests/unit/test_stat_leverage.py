"""Stat-leverage concentration analysis."""

from __future__ import annotations

from wnba_oracle.predict.stat_leverage import (
    HIGH_LEVERAGE_SHARE,
    is_leverage_efficient,
    stat_leverage_score,
)


def test_pure_scorer_gets_low_leverage() -> None:
    """A player who only scores points has zero leverage concentration."""
    score = stat_leverage_score(pts_per_min=0.5, ast_per_min=0.0, stl_blk_per_min=0.0)
    assert score < 0.1


def test_pure_facilitator_gets_high_leverage() -> None:
    """A player who only assists has high leverage concentration."""
    score = stat_leverage_score(pts_per_min=0.0, ast_per_min=0.3, stl_blk_per_min=0.0)
    assert score > 0.9


def test_defensive_specialist_gets_high_leverage() -> None:
    """A player heavy on steals and blocks."""
    score = stat_leverage_score(pts_per_min=0.1, ast_per_min=0.05, stl_blk_per_min=0.15)
    assert score > 0.5


def test_balanced_player_is_moderate() -> None:
    """A balanced player with production across all categories."""
    score = stat_leverage_score(
        pts_per_min=0.3, ast_per_min=0.1, stl_blk_per_min=0.05, reb_per_min=0.2
    )
    assert 0.2 < score < 0.6


def test_zero_production_returns_zero() -> None:
    assert stat_leverage_score() == 0.0


def test_leverage_score_bounded_zero_one() -> None:
    """Score is always in [0, 1] regardless of inputs."""
    for pts in (0.0, 0.5, 1.0):
        for ast in (0.0, 0.5, 1.0):
            for stl in (0.0, 0.5, 1.0):
                s = stat_leverage_score(pts_per_min=pts, ast_per_min=ast, stl_blk_per_min=stl)
                assert 0.0 <= s <= 1.0


def test_is_leverage_efficient_threshold() -> None:
    """Threshold correctly gates the boolean."""
    assert is_leverage_efficient(
        pts_per_min=0.0, ast_per_min=0.3, stl_blk_per_min=0.1, threshold=0.4
    )
    assert not is_leverage_efficient(
        pts_per_min=0.5, ast_per_min=0.0, stl_blk_per_min=0.0, threshold=0.4
    )


def test_high_leverage_share_is_sensible() -> None:
    """The formula-level share of high-leverage weights should be > 0.5."""
    assert 0.4 < HIGH_LEVERAGE_SHARE < 0.8


def test_more_assists_increases_leverage() -> None:
    """Adding assists to a scorer raises the leverage score."""
    scorer = stat_leverage_score(pts_per_min=0.4, ast_per_min=0.0)
    facilitating_scorer = stat_leverage_score(pts_per_min=0.4, ast_per_min=0.15)
    assert facilitating_scorer > scorer

"""Hot-streak quality assessment."""

from __future__ import annotations

from wnba_oracle.predict.streak_quality import streak_quality


def test_not_hot_when_l5_equals_l10() -> None:
    """No streak when recent and baseline production are equal."""
    result = streak_quality(fantasy_pts_l5=20.0, fantasy_pts_l10=20.0)
    assert not result.is_hot
    assert result.driver == "none"


def test_not_hot_when_slightly_above() -> None:
    """Mild uptick does not count as a streak (below 15% threshold)."""
    result = streak_quality(fantasy_pts_l5=22.0, fantasy_pts_l10=20.0)
    assert not result.is_hot


def test_hot_when_well_above_threshold() -> None:
    """Clear hot streak when L5 is 30% above L10."""
    result = streak_quality(
        fantasy_pts_l5=26.0,
        fantasy_pts_l10=20.0,
        pts_per_min_l5=0.4,
        pts_per_min_l10=0.35,
        ts_pct_l10=0.52,
    )
    assert result.is_hot


def test_high_leverage_driver_when_defensive_stats_dominate() -> None:
    """A streak driven by steals/blocks/assists is sustainable."""
    result = streak_quality(
        fantasy_pts_l5=30.0,
        fantasy_pts_l10=20.0,
        pts_per_min_l5=0.2,
        pts_per_min_l10=0.15,
        ast_per_min_l10=0.2,
        stl_blk_per_min_l10=0.1,
        reb_per_min_l10=0.1,
        ts_pct_l10=0.55,
    )
    assert result.is_hot
    assert result.driver == "high_leverage"
    assert result.quality > 0.3


def test_regressive_when_low_efficiency() -> None:
    """A streak on poor shooting is flagged as regressive."""
    result = streak_quality(
        fantasy_pts_l5=26.0,
        fantasy_pts_l10=20.0,
        pts_per_min_l5=0.5,
        pts_per_min_l10=0.45,
        ast_per_min_l10=0.02,
        stl_blk_per_min_l10=0.01,
        reb_per_min_l10=0.2,
        ts_pct_l10=0.38,
    )
    assert result.is_hot
    assert result.driver == "regressive"
    assert result.quality < 0.3


def test_efficient_scoring_driver() -> None:
    """High TS% without high-leverage stats -> efficient scoring."""
    result = streak_quality(
        fantasy_pts_l5=26.0,
        fantasy_pts_l10=20.0,
        pts_per_min_l5=0.45,
        pts_per_min_l10=0.4,
        ast_per_min_l10=0.05,
        stl_blk_per_min_l10=0.02,
        reb_per_min_l10=0.2,
        ts_pct_l10=0.60,
    )
    assert result.is_hot
    assert result.driver == "efficient_scoring"


def test_zero_baseline_not_hot() -> None:
    """Zero baseline production avoids division by zero."""
    result = streak_quality(fantasy_pts_l5=10.0, fantasy_pts_l10=0.0)
    assert not result.is_hot


def test_both_zero_not_hot() -> None:
    result = streak_quality(fantasy_pts_l5=0.0, fantasy_pts_l10=0.0)
    assert not result.is_hot


def test_quality_bounded() -> None:
    """Quality is always in [0, 1]."""
    extreme = streak_quality(
        fantasy_pts_l5=100.0,
        fantasy_pts_l10=10.0,
        pts_per_min_l5=1.0,
        pts_per_min_l10=0.5,
        ast_per_min_l10=0.5,
        stl_blk_per_min_l10=0.5,
        ts_pct_l10=0.70,
    )
    assert 0.0 <= extreme.quality <= 1.0


def test_custom_hot_threshold() -> None:
    """Custom threshold changes what counts as hot."""
    strict = streak_quality(fantasy_pts_l5=24.0, fantasy_pts_l10=20.0, hot_threshold=1.25)
    assert not strict.is_hot  # 1.2 < 1.25

    lenient = streak_quality(fantasy_pts_l5=24.0, fantasy_pts_l10=20.0, hot_threshold=1.10)
    assert lenient.is_hot  # 1.2 >= 1.10

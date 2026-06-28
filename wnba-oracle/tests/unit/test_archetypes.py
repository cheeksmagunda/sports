"""DFS value archetype classification."""

from __future__ import annotations

from wnba_oracle.predict.archetypes import (
    ArchetypeInput,
    ArchetypeLabel,
    classify_archetype,
    classify_pool,
)


def _make_input(**overrides) -> ArchetypeInput:
    """Factory with sane defaults for a generic starter."""
    defaults = {
        "player_id": 1,
        "card_boost": 1.0,
        "is_confirmed_starter": True,
        "is_anchor": True,
        "mins_l10": 28.0,
        "pts_per_min_l10": 0.35,
        "ast_per_min_l10": 0.08,
        "stl_blk_per_min_l10": 0.04,
        "reb_per_min_l10": 0.15,
        "ts_pct_l10": 0.52,
        "fantasy_pts_l5": 22.0,
        "fantasy_pts_l10": 20.0,
        "pts_per_min_l5": 0.36,
        "implied_team_total": 43.0,
        "vegas_total": 160.0,
        "usg_pct_l10": 0.22,
    }
    defaults.update(overrides)
    return ArchetypeInput(**defaults)


class TestCeilingAnchor:
    def test_high_usage_starter_on_high_total_team(self) -> None:
        """Confirmed starter with high usage and high implied total."""
        label = classify_archetype(_make_input(
            is_confirmed_starter=True,
            mins_l10=30.0,
            usg_pct_l10=0.25,
            implied_team_total=45.0,
        ))
        assert label.primary == "ceiling_anchor"
        assert label.confidence > 0.5

    def test_anchor_on_fast_paced_team(self) -> None:
        """Anchor player on a high-total team qualifies even with
        moderate usage."""
        label = classify_archetype(_make_input(
            is_anchor=True,
            is_confirmed_starter=False,
            mins_l10=26.0,
            vegas_total=170.0,
            usg_pct_l10=0.18,
        ))
        assert label.primary == "ceiling_anchor"

    def test_starter_low_minutes_not_ceiling(self) -> None:
        """A starter with low minutes is not a ceiling anchor."""
        label = classify_archetype(_make_input(
            is_confirmed_starter=True,
            mins_l10=18.0,
            usg_pct_l10=0.25,
        ))
        assert label.primary != "ceiling_anchor"


class TestEfficientProducer:
    def test_high_assist_rate_player(self) -> None:
        """A facilitator with high assist rate is an efficient producer."""
        label = classify_archetype(_make_input(
            is_confirmed_starter=False,
            is_anchor=False,
            mins_l10=22.0,
            pts_per_min_l10=0.15,
            ast_per_min_l10=0.25,
            stl_blk_per_min_l10=0.08,
            usg_pct_l10=0.15,
            implied_team_total=38.0,
            vegas_total=150.0,
        ))
        assert label.primary == "efficient_producer"

    def test_defensive_specialist(self) -> None:
        """High stl/blk per minute with moderate scoring."""
        label = classify_archetype(_make_input(
            is_confirmed_starter=False,
            is_anchor=False,
            mins_l10=22.0,
            pts_per_min_l10=0.10,
            ast_per_min_l10=0.05,
            stl_blk_per_min_l10=0.15,
            usg_pct_l10=0.12,
            implied_team_total=38.0,
            vegas_total=150.0,
        ))
        assert label.primary == "efficient_producer"


class TestLeverageSpike:
    def test_cheap_confirmed_starter(self) -> None:
        """High-boost (cheap) player confirmed to start."""
        label = classify_archetype(_make_input(
            card_boost=2.5,
            is_confirmed_starter=True,
            is_anchor=False,
            mins_l10=20.0,
            pts_per_min_l10=0.25,
            ast_per_min_l10=0.04,
            stl_blk_per_min_l10=0.02,
            usg_pct_l10=0.14,
            implied_team_total=38.0,
            vegas_total=150.0,
        ))
        assert label.primary == "leverage_spike"

    def test_cheap_non_starter_is_baseline(self) -> None:
        """High boost without confirmed role falls to baseline."""
        label = classify_archetype(_make_input(
            card_boost=3.0,
            is_confirmed_starter=False,
            is_anchor=False,
            mins_l10=10.0,
            pts_per_min_l10=0.15,
            ast_per_min_l10=0.03,
            stl_blk_per_min_l10=0.02,
            usg_pct_l10=0.10,
            implied_team_total=38.0,
            vegas_total=150.0,
        ))
        assert label.primary == "baseline"


class TestStreakingTag:
    def test_hot_streak_sets_flag(self) -> None:
        label = classify_archetype(_make_input(
            fantasy_pts_l5=30.0,
            fantasy_pts_l10=20.0,
            pts_per_min_l5=0.5,
        ))
        assert label.is_streaking

    def test_no_streak_clears_flag(self) -> None:
        label = classify_archetype(_make_input(
            fantasy_pts_l5=20.0,
            fantasy_pts_l10=20.0,
        ))
        assert not label.is_streaking


class TestConfidence:
    def test_more_signals_higher_confidence(self) -> None:
        """Stacking confirmed starter + high minutes + high total + high
        usage should produce higher confidence than any single signal."""
        strong = classify_archetype(_make_input(
            is_confirmed_starter=True,
            mins_l10=32.0,
            usg_pct_l10=0.28,
            implied_team_total=46.0,
        ))
        weak = classify_archetype(_make_input(
            is_confirmed_starter=True,
            mins_l10=25.0,
            usg_pct_l10=0.20,
            implied_team_total=42.0,
            vegas_total=155.0,
        ))
        assert strong.confidence >= weak.confidence

    def test_regressive_streak_lowers_confidence(self) -> None:
        """A regressive streak should reduce confidence."""
        no_streak = classify_archetype(_make_input(
            fantasy_pts_l5=20.0,
            fantasy_pts_l10=20.0,
        ))
        regressive_streak = classify_archetype(_make_input(
            fantasy_pts_l5=30.0,
            fantasy_pts_l10=20.0,
            pts_per_min_l5=0.6,
            pts_per_min_l10=0.5,
            ast_per_min_l10=0.02,
            stl_blk_per_min_l10=0.01,
            ts_pct_l10=0.35,
        ))
        assert regressive_streak.confidence <= no_streak.confidence

    def test_confidence_bounded(self) -> None:
        """Confidence is always in [0, 1]."""
        label = classify_archetype(_make_input())
        assert 0.0 <= label.confidence <= 1.0


class TestClassifyPool:
    def test_returns_dict_keyed_by_player_id(self) -> None:
        pool = [
            _make_input(player_id=101),
            _make_input(player_id=102, card_boost=3.0, is_confirmed_starter=False,
                        is_anchor=False, mins_l10=10.0, usg_pct_l10=0.10,
                        implied_team_total=38.0, vegas_total=150.0),
        ]
        result = classify_pool(pool)
        assert set(result.keys()) == {101, 102}
        assert isinstance(result[101], ArchetypeLabel)

    def test_empty_pool(self) -> None:
        assert classify_pool([]) == {}

    def test_all_archetypes_representable(self) -> None:
        """A diverse pool should produce more than one archetype."""
        pool = [
            _make_input(player_id=1, mins_l10=32.0, usg_pct_l10=0.28,
                        implied_team_total=46.0),
            _make_input(player_id=2, is_confirmed_starter=False, is_anchor=False,
                        mins_l10=22.0, pts_per_min_l10=0.10, ast_per_min_l10=0.25,
                        stl_blk_per_min_l10=0.10, usg_pct_l10=0.12,
                        implied_team_total=38.0, vegas_total=150.0),
            _make_input(player_id=3, card_boost=2.5, is_anchor=False,
                        mins_l10=20.0, pts_per_min_l10=0.20, ast_per_min_l10=0.04,
                        stl_blk_per_min_l10=0.02, usg_pct_l10=0.14,
                        implied_team_total=38.0, vegas_total=150.0),
            _make_input(player_id=4, card_boost=3.0, is_confirmed_starter=False,
                        is_anchor=False, mins_l10=8.0, pts_per_min_l10=0.12,
                        ast_per_min_l10=0.03, stl_blk_per_min_l10=0.01,
                        usg_pct_l10=0.08, implied_team_total=36.0, vegas_total=145.0),
        ]
        result = classify_pool(pool)
        labels = {v.primary for v in result.values()}
        assert len(labels) >= 3

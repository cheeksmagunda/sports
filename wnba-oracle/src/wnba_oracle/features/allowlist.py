"""Pre-game feature allowlist.

This is an explicit ALLOW list. A feature must be registered here to be
permitted at predict time. The default for an unknown column is REJECT,
which prevents post-game leakage from accidentally being read into the
serving feature matrix.

Adding a feature is a deliberate act, recorded in DECISIONS.md.

The allowlist is enforced by `assert_predict_features_allowed(df)` which
the predict pipeline calls before the LightGBM heads see the matrix.
"""

from __future__ import annotations

from typing import Final

# Pre-game features. Anything that is computable before tipoff with the
# data available at Job 1 / Job 2 time.
PREGAME_FEATURES: Final[frozenset[str]] = frozenset(
    {
        # Identity (kept categorical / for joins)
        "slate_date",
        "player_id",
        "platform_player_id",
        "team",
        "opponent",
        "position",
        "cohort",
        "is_home",
        # Real Sports
        "card_boost",
        "primary_ranking",
        # Schedule context
        "days_rest",
        "is_back_to_back",
        "season_game_number",
        "travel_distance_miles",
        # Rolling player rates (computed strictly before slate_date)
        "mins_l5",
        "mins_l10",
        "mins_l20",
        "pts_l5",
        "pts_l10",
        "reb_l5",
        "reb_l10",
        "ast_l5",
        "ast_l10",
        "stl_l5",
        "stl_l10",
        "blk_l5",
        "blk_l10",
        "tov_l5",
        "tov_l10",
        "fg3m_l5",
        "fg3m_l10",
        "fantasy_pts_l5",
        "fantasy_pts_l10",
        "plus_minus_l10",
        "pts_per_min_l5",
        "pts_per_min_l10",
        "reb_per_min_l10",
        "ast_per_min_l10",
        "stl_blk_per_min_l10",
        "ts_pct_l10",
        "efg_pct_l10",
        "usg_pct_l10",
        "ast_to_tov_l10",
        "fg3_pct_l10",
        # Season aggregates (carried forward from start of season)
        "ts_pct",
        "efg_pct",
        "usg_pct",
        "ast_pct",
        "tov_pct",
        "oreb_pct",
        "dreb_pct",
        "stl_pct",
        "blk_pct",
        "per",
        "bpm",
        "pie",
        "fg3a_rate",
        "ftr",
        # Team / opponent context
        "team_pace",
        "opp_pace",
        "game_pace_implied",
        "team_off_rtg",
        "team_def_rtg",
        "opp_off_rtg",
        "opp_def_rtg",
        "opp_dvp_guard",
        "opp_dvp_forward",
        "opp_dvp_center",
        "team_l10_wins",
        "opp_l10_wins",
        # Vegas
        "vegas_total",
        "vegas_spread",
        "implied_team_total",
        "home_moneyline",
        "away_moneyline",
        # Lineups
        "is_confirmed_starter",
        "is_expected_starter",
        "starter_slot",
        "is_injury_flag",
        # Minutes-prediction head features (recompose at predict-time)
        "foul_rate_l10",
        "coach_rotation_consistency_l20",
        "team_starter_status",
    }
)


class FeatureLeakageError(RuntimeError):
    """Predict-time feature matrix contains a column outside the allowlist."""


def assert_predict_features_allowed(columns: list[str]) -> None:
    bad = sorted(c for c in columns if c not in PREGAME_FEATURES)
    if bad:
        raise FeatureLeakageError(
            f"feature(s) not in PREGAME_FEATURES allowlist: {bad}. "
            "Add to allowlist.py (and DECISIONS.md) if intentional; otherwise drop."
        )

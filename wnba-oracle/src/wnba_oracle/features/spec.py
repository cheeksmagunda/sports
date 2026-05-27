"""Feature spec registry.

For each model head, list the feature columns it consumes. The training
pipeline reads from here to assemble per-cohort design matrices; the
predict pipeline reads from here to ensure column ordering matches the
pickled artifact.

Cohorts: Guard (G), Forward (F), Center (C). Position strings from
Real Sports may be hyphenated (e.g. "G-F"); `cohort_for_position`
reduces to the primary single-letter cohort.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Cohort = Literal["G", "F", "C"]


@dataclass(frozen=True)
class HeadSpec:
    name: str
    target: str
    feature_columns: tuple[str, ...]


_BASE_FEATURES = (
    "card_boost",
    "primary_ranking",
    "days_rest",
    "is_back_to_back",
    "season_game_number",
    "is_home",
    "is_confirmed_starter",
    "starter_slot",
    "mins_l5",
    "mins_l10",
    "mins_l20",
    "fantasy_pts_l5",
    "fantasy_pts_l10",
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
    "plus_minus_l10",
    "ts_pct",
    "usg_pct",
    "team_pace",
    "opp_pace",
    "game_pace_implied",
    "team_off_rtg",
    "team_def_rtg",
    "opp_off_rtg",
    "opp_def_rtg",
    "vegas_total",
    "vegas_spread",
    "implied_team_total",
    "team_l10_wins",
    "opp_l10_wins",
    "foul_rate_l10",
    "coach_rotation_consistency_l20",
)

# Each head consumes a slightly different feature column set.
HEAD_SPECS: dict[str, HeadSpec] = {
    "minutes": HeadSpec(
        name="minutes",
        target="minutes_played",
        feature_columns=_BASE_FEATURES,
    ),
    "points_per_min": HeadSpec(
        name="points_per_min",
        target="pts_per_min",
        feature_columns=_BASE_FEATURES,
    ),
    "reb_per_min": HeadSpec(
        name="reb_per_min",
        target="reb_per_min",
        feature_columns=_BASE_FEATURES,
    ),
    "ast_per_min": HeadSpec(
        name="ast_per_min",
        target="ast_per_min",
        feature_columns=_BASE_FEATURES,
    ),
    "stl_blk_per_min": HeadSpec(
        name="stl_blk_per_min",
        target="stl_blk_per_min",
        feature_columns=_BASE_FEATURES,
    ),
    "real_score_residual": HeadSpec(
        name="real_score_residual",
        target="real_score_residual",
        feature_columns=_BASE_FEATURES,
    ),
}

# DvP (defense vs position) columns are added per cohort because the
# relevant opponent metric differs by position.
COHORT_EXTRA_FEATURES: dict[Cohort, tuple[str, ...]] = {
    "G": ("opp_dvp_guard",),
    "F": ("opp_dvp_forward",),
    "C": ("opp_dvp_center",),
}


def cohort_for_position(position: str | None) -> Cohort:
    """Reduce a Real Sports position string ('G', 'F', 'C', 'G-F', 'F-C', ...)
    to the primary cohort. Falls back to 'F' for unknown / blank.
    """
    if not position:
        return "F"
    p = position.upper().strip()
    if p.startswith("G"):
        return "G"
    if p.startswith("C"):
        return "C"
    return "F"


def feature_columns_for_head(head: str, cohort: Cohort) -> tuple[str, ...]:
    spec = HEAD_SPECS[head]
    return spec.feature_columns + COHORT_EXTRA_FEATURES[cohort]

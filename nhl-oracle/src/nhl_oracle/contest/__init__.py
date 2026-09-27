"""NHL contest algebra package (five-card scoring + pick; observation only)."""

from nhl_oracle.contest.algebra import (
    DEFAULT_SLOT_MULTIPLIERS,
    ROSTER_SIZE,
    CardContribution,
    LineupScore,
    effective_card_boost,
    hindsight_optimal_assignment,
    item_score,
    score_ordered_lineup,
)
from nhl_oracle.contest.pick import FivePlayerPick, select_five_player_pick

__all__ = [
    "DEFAULT_SLOT_MULTIPLIERS",
    "ROSTER_SIZE",
    "CardContribution",
    "FivePlayerPick",
    "LineupScore",
    "effective_card_boost",
    "hindsight_optimal_assignment",
    "item_score",
    "score_ordered_lineup",
    "select_five_player_pick",
]

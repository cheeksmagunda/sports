"""Replay the saved Corpus C contest archive against the verified scoring law.

Turns STATUS.md's prose claims about slot-order optimality, slot regret, and
winner capture ratio into re-derivable code. See :mod:`nfl_oracle.replay.harness`.
"""

from nfl_oracle.replay.harness import (
    ContestReplayResult,
    HindsightLineup,
    PooledReplaySummary,
    eligible_pool_values,
    hindsight_best_lineup,
    is_optimally_ordered,
    pooled_summary,
    replay_all,
    replay_contest,
    slot_regret,
)

__all__ = [
    "ContestReplayResult",
    "HindsightLineup",
    "PooledReplaySummary",
    "eligible_pool_values",
    "hindsight_best_lineup",
    "is_optimally_ordered",
    "pooled_summary",
    "replay_all",
    "replay_contest",
    "slot_regret",
]

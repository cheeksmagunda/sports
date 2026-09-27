"""Five-player NHL pick under verified contest algebra (observation only).

Selects five distinct players by descending projected value, then assigns
them to ordered slots ``(2.0, 1.8, 1.6, 1.4, 1.2)``. Coherent with the T-40
freeze path: a freeze prepare step may call ``select_five_player_pick`` on
pre-lock projections only. No contest entry. No LightGBM.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from nhl_oracle.contest.algebra import (
    DEFAULT_SLOT_MULTIPLIERS,
    ROSTER_SIZE,
    LineupScore,
    score_ordered_lineup,
)
from nhl_oracle.contract.boost_gate import BoostEligibility
from nhl_oracle.contract.schema import NhlContestContract


@dataclass(frozen=True)
class FivePlayerPick:
    """Ordered five-card recommendation before freeze publish."""

    player_ids: tuple[int, ...]
    projected_values: Mapping[int, float]
    slot_multipliers: tuple[float, ...]
    lineup_score: LineupScore
    source: str = "projected_value_desc"

    def to_dict(self) -> dict[str, Any]:
        return {
            "player_ids": list(self.player_ids),
            "projected_values": {str(k): v for k, v in self.projected_values.items()},
            "slot_multipliers": list(self.slot_multipliers),
            "lineup_score": self.lineup_score.to_dict(),
            "source": self.source,
            "roster_size": ROSTER_SIZE,
            "contest_entry": False,
            "observation_only": True,
        }


def select_five_player_pick(
    projected_values: Mapping[int, float],
    *,
    card_boosts: Mapping[int, float] | None = None,
    contract: NhlContestContract | None = None,
    slot_multipliers: Sequence[float] | None = None,
    eligibility: BoostEligibility | None = None,
    boost_multiplier: float | None = None,
) -> FivePlayerPick:
    """Pick top-5 by projected value and score under NHL contest algebra."""

    usable = {int(pid): float(val) for pid, val in projected_values.items()}
    if len(usable) < ROSTER_SIZE:
        raise ValueError("insufficient_candidates_for_five_player_pick")
    ranked = tuple(pid for pid, _ in sorted(usable.items(), key=lambda kv: (-kv[1], kv[0])))[
        :ROSTER_SIZE
    ]
    slots = (
        tuple(float(x) for x in slot_multipliers)
        if slot_multipliers is not None
        else (
            tuple(float(x) for x in contract.slot_multipliers)
            if contract is not None and contract.slot_multipliers is not None
            else DEFAULT_SLOT_MULTIPLIERS
        )
    )
    if len(slots) != ROSTER_SIZE:
        raise ValueError("slot_multipliers_must_match_roster_size_5")
    # Assign highest projection to highest slot multiplier (greedy).
    ordered_ids = ranked
    score = score_ordered_lineup(
        ordered_ids,
        usable,
        card_boosts=card_boosts,
        contract=contract,
        slot_multipliers=slots,
        eligibility=eligibility,
        boost_multiplier=boost_multiplier,
    )
    return FivePlayerPick(
        player_ids=ordered_ids,
        projected_values={pid: usable[pid] for pid in ordered_ids},
        slot_multipliers=slots,
        lineup_score=score,
    )

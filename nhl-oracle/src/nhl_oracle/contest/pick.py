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
from nhl_oracle.contract.boost_gate import (
    BoostEligibility,
    TeamGamesPlayed,
    evaluate_boost_eligibility,
)
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


def select_no_boost_five_from_full_pool(
    projected_values: Mapping[int, float],
    *,
    expected_pool_size: int,
    card_boosts: Mapping[int, float] | None = None,
    contract: NhlContestContract | None = None,
    team_games_played: Mapping[str, int] | Sequence[TeamGamesPlayed] | None = None,
    slate_teams: Sequence[str] | None = None,
    team_card_counts: Mapping[str, int] | None = None,
) -> FivePlayerPick:
    """Pick the ordered five from the full slate pool with the zero-boost gate.

    A five-player stub is not a roster. ``expected_pool_size`` must be larger
    than the contest five and must equal the number of projected players.
    When ``slate_teams`` is set, every team on the slate must have at least
    one card and those cards must sum to the pool. Card boosts are multiplied
    by the gate: 0 until every club has a game, including when coverage is
    missing. There is no caller boost-multiplier override.
    """

    if expected_pool_size <= ROSTER_SIZE:
        raise ValueError("full_roster_pool_required")
    if len(projected_values) != expected_pool_size:
        raise ValueError(f"pool_incomplete_{len(projected_values)}_of_{expected_pool_size}")
    if slate_teams is not None:
        if team_card_counts is None:
            raise ValueError("team_card_counts_required")
        teams = tuple(slate_teams)
        missing = [team for team in teams if int(team_card_counts.get(team, 0)) < 1]
        if missing:
            raise ValueError("slate_team_missing_from_pool")
        off_slate = [team for team in team_card_counts if team not in teams]
        if off_slate:
            raise ValueError("pool_has_teams_off_slate")
        if sum(int(team_card_counts[team]) for team in teams) != expected_pool_size:
            raise ValueError("team_cards_do_not_cover_pool")
    eligibility = evaluate_boost_eligibility(team_games_played)
    return select_five_player_pick(
        projected_values,
        card_boosts=card_boosts,
        contract=contract,
        eligibility=eligibility,
    )

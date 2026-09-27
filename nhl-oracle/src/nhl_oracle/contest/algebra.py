"""NHL five-card contest algebra (observation / research only).

Verified Week 2 contract (#299 / #325): ordered five-card lineup, slot
multipliers ``(2.0, 1.8, 1.6, 1.4, 1.2)``, score label ``value``, goalie
eligible. Card contribution:

    item_score = value * (slot_multiplier + effective_card_boost)

``effective_card_boost`` is forced to 0.0 while the all-teams-played zero-boost
gate is active (#501 / #517). No contest entry.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from nhl_oracle.contract.boost_gate import BOOST_MULTIPLIER_GATED, BoostEligibility
from nhl_oracle.contract.schema import NhlContestContract

DEFAULT_SLOT_MULTIPLIERS: tuple[float, ...] = (2.0, 1.8, 1.6, 1.4, 1.2)
ROSTER_SIZE = 5


@dataclass(frozen=True)
class CardContribution:
    """One ordered slot's contribution under NHL contest algebra."""

    slot: int
    player_id: int
    value: float
    slot_multiplier: float
    card_boost: float
    effective_card_boost: float
    item_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot": self.slot,
            "player_id": self.player_id,
            "value": self.value,
            "slot_multiplier": self.slot_multiplier,
            "card_boost": self.card_boost,
            "effective_card_boost": self.effective_card_boost,
            "item_score": self.item_score,
        }


@dataclass(frozen=True)
class LineupScore:
    """Committed five-card lineup score under the verified contest law."""

    contributions: tuple[CardContribution, ...]
    total_score: float
    boost_gated: bool
    roster_size: int = ROSTER_SIZE

    def to_dict(self) -> dict[str, Any]:
        return {
            "contributions": [c.to_dict() for c in self.contributions],
            "total_score": self.total_score,
            "boost_gated": self.boost_gated,
            "roster_size": self.roster_size,
            "contest_entry": False,
        }


def effective_card_boost(
    card_boost: float,
    *,
    eligibility: BoostEligibility | None = None,
    boost_multiplier: float | None = None,
) -> float:
    """Apply the hard zero-boost gate to a provider card boost."""

    if card_boost < 0:
        raise ValueError("card_boost_must_be_non_negative")
    if eligibility is not None:
        return float(card_boost) * float(eligibility.boost_multiplier)
    if boost_multiplier is not None:
        if boost_multiplier < 0:
            raise ValueError("boost_multiplier_must_be_non_negative")
        return float(card_boost) * float(boost_multiplier)
    # Fail closed: no eligibility evidence => gated.
    return float(card_boost) * BOOST_MULTIPLIER_GATED


def item_score(
    value: float,
    slot_multiplier: float,
    *,
    card_boost: float = 0.0,
    eligibility: BoostEligibility | None = None,
    boost_multiplier: float | None = None,
) -> float:
    """Single-card Real Sports item score under NHL algebra."""

    if slot_multiplier <= 0:
        raise ValueError("slot_multiplier_must_be_positive")
    eff = effective_card_boost(
        card_boost, eligibility=eligibility, boost_multiplier=boost_multiplier
    )
    return float(value) * (float(slot_multiplier) + eff)


def resolve_slot_multipliers(
    contract: NhlContestContract | None = None,
    slot_multipliers: Sequence[float] | None = None,
) -> tuple[float, ...]:
    if slot_multipliers is not None:
        slots = tuple(float(x) for x in slot_multipliers)
    elif contract is not None and contract.slot_multipliers is not None:
        slots = tuple(float(x) for x in contract.slot_multipliers)
    else:
        slots = DEFAULT_SLOT_MULTIPLIERS
    if len(slots) != ROSTER_SIZE:
        raise ValueError("slot_multipliers_must_match_roster_size_5")
    if any(m <= 0 for m in slots):
        raise ValueError("slot_multipliers_must_be_positive")
    return slots


def score_ordered_lineup(
    player_ids: Sequence[int],
    values: Mapping[int, float],
    *,
    card_boosts: Mapping[int, float] | None = None,
    contract: NhlContestContract | None = None,
    slot_multipliers: Sequence[float] | None = None,
    eligibility: BoostEligibility | None = None,
    boost_multiplier: float | None = None,
) -> LineupScore:
    """Score a committed ordered five-card lineup (never reorders by outcome)."""

    if len(player_ids) != ROSTER_SIZE:
        raise ValueError("lineup_must_have_exactly_5_players")
    if len(set(player_ids)) != ROSTER_SIZE:
        raise ValueError("lineup_players_must_be_distinct")
    slots = resolve_slot_multipliers(contract, slot_multipliers)
    boosts = card_boosts or {}
    contributions: list[CardContribution] = []
    total = 0.0
    if eligibility is not None:
        gated = not eligibility.boost_allowed
    elif boost_multiplier is None:
        gated = True
    else:
        gated = boost_multiplier == BOOST_MULTIPLIER_GATED
    for index, player_id in enumerate(player_ids):
        if player_id not in values:
            raise ValueError(f"missing_value_for_player:{player_id}")
        raw_boost = float(boosts.get(player_id, 0.0))
        eff = effective_card_boost(
            raw_boost, eligibility=eligibility, boost_multiplier=boost_multiplier
        )
        score = item_score(
            values[player_id],
            slots[index],
            card_boost=raw_boost,
            eligibility=eligibility,
            boost_multiplier=boost_multiplier,
        )
        contributions.append(
            CardContribution(
                slot=index + 1,
                player_id=int(player_id),
                value=float(values[player_id]),
                slot_multiplier=slots[index],
                card_boost=raw_boost,
                effective_card_boost=eff,
                item_score=score,
            )
        )
        total += score
    return LineupScore(
        contributions=tuple(contributions),
        total_score=total,
        boost_gated=gated,
    )


def hindsight_optimal_assignment(
    player_ids: Sequence[int],
    values: Mapping[int, float],
    *,
    card_boosts: Mapping[int, float] | None = None,
    contract: NhlContestContract | None = None,
    slot_multipliers: Sequence[float] | None = None,
    eligibility: BoostEligibility | None = None,
    boost_multiplier: float | None = None,
) -> LineupScore:
    """Assign five fixed players to slots by descending value (research only).

    Live freeze must never call this on a committed lineup; it is the
    backtest reference assignment for a chosen five-player set.
    """

    if len(player_ids) != ROSTER_SIZE:
        raise ValueError("lineup_must_have_exactly_5_players")
    ordered = tuple(sorted(player_ids, key=lambda pid: (-float(values[pid]), int(pid))))
    return score_ordered_lineup(
        ordered,
        values,
        card_boosts=card_boosts,
        contract=contract,
        slot_multipliers=slot_multipliers,
        eligibility=eligibility,
        boost_multiplier=boost_multiplier,
    )

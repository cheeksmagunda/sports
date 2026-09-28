"""T-40 freeze publication policy coherent with NHL contest algebra (#535).

T-40 means freeze prepare/publish may open at ``lock_at - 40 minutes`` under
the verified per-contest lock scope. The five-player ordered pick and slot
multipliers must match ``NhlContestContract`` before a freeze record is
marked prepared. Observation only; ``contest_entry`` stays False.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from nhl_oracle.contest.algebra import DEFAULT_SLOT_MULTIPLIERS, ROSTER_SIZE
from nhl_oracle.contest.pick import FivePlayerPick
from nhl_oracle.contract.boost_gate import BoostEligibility
from nhl_oracle.contract.schema import ContestFormat, LockScope, NhlContestContract

T40_OFFSET = timedelta(minutes=40)


@dataclass(frozen=True)
class T40Window:
    """Publication window relative to contest lock."""

    lock_at: datetime
    open_at: datetime
    offset_minutes: int = 40

    def contains(self, now: datetime) -> bool:
        return self.open_at <= now < self.lock_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "lock_at": self.lock_at.isoformat(),
            "open_at": self.open_at.isoformat(),
            "offset_minutes": self.offset_minutes,
            "lock_scope_expected": LockScope.PER_CONTEST.value,
        }


@dataclass(frozen=True)
class FreezeCoherence:
    """Whether a five-player pick is coherent with NHL contest algebra + T-40."""

    ok: bool
    reasons: tuple[str, ...]
    t40: T40Window | None
    in_t40_window: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reasons": list(self.reasons),
            "t40": None if self.t40 is None else self.t40.to_dict(),
            "in_t40_window": self.in_t40_window,
            "contest_entry": False,
        }


def t40_window(lock_at: datetime) -> T40Window:
    if lock_at.tzinfo is None:
        raise ValueError("lock_at_must_be_timezone_aware")
    return T40Window(lock_at=lock_at, open_at=lock_at - T40_OFFSET)


def assert_contract_five_card(contract: NhlContestContract) -> tuple[str, ...]:
    """Return blocking reasons when the contract is not five-card ordered."""

    reasons: list[str] = []
    if contract.format is not ContestFormat.FIVE_CARD_ORDERED:
        reasons.append(f"format_not_five_card_ordered:{contract.format.value}")
    if contract.roster_size != ROSTER_SIZE:
        reasons.append(f"roster_size_not_5:{contract.roster_size}")
    slots = contract.slot_multipliers
    if slots is None:
        reasons.append("slot_multipliers_missing")
    elif tuple(slots) != DEFAULT_SLOT_MULTIPLIERS:
        reasons.append(f"slot_multipliers_unexpected:{slots}")
    if contract.lock_scope not in {LockScope.PER_CONTEST, LockScope.UNKNOWN}:
        # Per-game lock would need a different T-40 definition; flag it.
        reasons.append(f"lock_scope_not_per_contest:{contract.lock_scope.value}")
    return tuple(reasons)


def evaluate_freeze_coherence(
    *,
    pick: FivePlayerPick,
    contract: NhlContestContract,
    now: datetime,
    lock_at: datetime | None,
    eligibility: BoostEligibility | None = None,
    pool_complete: bool | None = None,
) -> FreezeCoherence:
    """Check five-player pick + T-40 window against NHL contest algebra.

    With no eligibility evidence the zero-boost gate stays closed: a pick
    whose effective card boost is nonzero cannot freeze. Pass a cleared
    ``BoostEligibility`` only after every club has at least one GP.
    ``pool_complete=False`` refuses the freeze; ``None`` leaves pool checks
    to the caller (older call sites).
    """

    reasons = list(assert_contract_five_card(contract))
    if len(pick.player_ids) != ROSTER_SIZE:
        reasons.append("pick_roster_size_not_5")
    if len(set(pick.player_ids)) != ROSTER_SIZE:
        reasons.append("pick_players_not_distinct")
    if pick.slot_multipliers != DEFAULT_SLOT_MULTIPLIERS:
        reasons.append(f"pick_slot_multipliers_unexpected:{pick.slot_multipliers}")
    if pick.lineup_score.roster_size != ROSTER_SIZE:
        reasons.append("lineup_score_roster_size_not_5")

    window: T40Window | None = None
    in_window = False
    if lock_at is None:
        reasons.append("lock_at_unknown")
    else:
        window = t40_window(lock_at)
        in_window = window.contains(now)
        if now >= lock_at:
            reasons.append("past_lock")
        elif not in_window:
            reasons.append("before_t40_window")

    # No eligibility evidence is the same as the gate still being closed.
    boost_gated = eligibility is None or not eligibility.boost_allowed
    if boost_gated:
        if not pick.lineup_score.boost_gated:
            reasons.append("zero_boost_not_applied")
        if any(card.effective_card_boost != 0.0 for card in pick.lineup_score.contributions):
            reasons.append("effective_boost_nonzero_while_gated")
    if pool_complete is False:
        reasons.append("pool_incomplete")

    return FreezeCoherence(
        ok=not reasons,
        reasons=tuple(reasons),
        t40=window,
        in_t40_window=in_window,
    )

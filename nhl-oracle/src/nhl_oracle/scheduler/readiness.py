"""T-40 win-freeze readiness for a live NHL slate (observation only).

A five-card freeze is ready only when all of the following hold:

- the contest pool equals the slate denominator (not merely five players)
- every scheduled game on that slate was captured
- every pool player has a pregame projection
- effective card boost is 0 while any club is still at 0 GP, or coverage is
  missing (fail closed)
- the decision clock is inside ``lock_at - 40 minutes`` and before lock
- the contract is five-card ordered with the verified slot multipliers

No live provider call lives here. Callers inject a snapshot. With no snapshot,
``empty_snapshot_readiness`` stays not ready and does not invent a lineup.
``contest_entry`` stays false.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from nhl_oracle.contest.algebra import ROSTER_SIZE
from nhl_oracle.contest.pick import select_no_boost_five_from_full_pool
from nhl_oracle.contract.boost_gate import (
    BoostEligibility,
    TeamGamesPlayed,
    evaluate_boost_eligibility,
    force_none_while_gated,
)
from nhl_oracle.contract.gates import evaluate_nhl_audit
from nhl_oracle.contract.schema import NhlAuditFixture, NhlCandidate, NhlContestContract
from nhl_oracle.scheduler.t40 import evaluate_freeze_coherence


@dataclass(frozen=True)
class WinFreezeReadiness:
    """Observation report for one T-40 five-card freeze attempt."""

    freeze_ready: bool
    blocked_reasons: tuple[str, ...]
    pool_complete: bool
    pool_detail: str
    zero_boost_active: bool
    boost_multiplier: float
    boost_detail: str
    in_t40_window: bool
    pick_player_ids: tuple[int, ...] | None
    contest_entry: bool = False
    observation_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "freeze_ready": self.freeze_ready,
            "blocked_reasons": list(self.blocked_reasons),
            "pool_complete": self.pool_complete,
            "pool_detail": self.pool_detail,
            "zero_boost_active": self.zero_boost_active,
            "boost_multiplier": self.boost_multiplier,
            "boost_detail": self.boost_detail,
            "in_t40_window": self.in_t40_window,
            "pick_player_ids": None if self.pick_player_ids is None else list(self.pick_player_ids),
            "contest_entry": self.contest_entry,
            "observation_only": self.observation_only,
        }


def _team_rows(
    team_games_played: Mapping[str, int] | Sequence[TeamGamesPlayed] | None,
) -> tuple[TeamGamesPlayed, ...] | None:
    if team_games_played is None:
        return None
    if isinstance(team_games_played, Mapping):
        return tuple(
            TeamGamesPlayed(team_id=str(team_id), games_played=int(games_played))
            for team_id, games_played in team_games_played.items()
        )
    return tuple(team_games_played)


def _from_eligibility(
    eligibility: BoostEligibility,
    *,
    blocked_reasons: tuple[str, ...],
    pool_complete: bool = False,
    pool_detail: str = "pool_not_supplied",
    in_t40_window: bool = False,
    pick_player_ids: tuple[int, ...] | None = None,
    freeze_ready: bool = False,
) -> WinFreezeReadiness:
    return WinFreezeReadiness(
        freeze_ready=freeze_ready,
        blocked_reasons=blocked_reasons,
        pool_complete=pool_complete,
        pool_detail=pool_detail,
        zero_boost_active=not eligibility.boost_allowed,
        boost_multiplier=eligibility.boost_multiplier,
        boost_detail=eligibility.detail,
        in_t40_window=in_t40_window,
        pick_player_ids=pick_player_ids,
    )


def empty_snapshot_readiness() -> WinFreezeReadiness:
    """No live slate was supplied. Fail closed. Do not invent five players."""

    eligibility = evaluate_boost_eligibility(None)
    return _from_eligibility(eligibility, blocked_reasons=("no_live_slate_snapshot",))


def evaluate_win_freeze_readiness(
    *,
    candidates: Sequence[NhlCandidate],
    expected_pool_size: int,
    games_scheduled: int,
    games_captured: int,
    projected_values: Mapping[int, float],
    now: datetime,
    lock_at: datetime | None,
    contract: NhlContestContract | None = None,
    team_games_played: Mapping[str, int] | Sequence[TeamGamesPlayed] | None = None,
    card_boosts: Mapping[int, float] | None = None,
) -> WinFreezeReadiness:
    """Score one injected slate. Ready only inside T-40 with a complete pool.

    While the all-teams-played gate is closed, flat or positional contract
    labels are forced to ``none`` and card boosts contribute 0. A partial
    pool does not produce a five-player pick.
    """

    if now.tzinfo is None:
        raise ValueError("now_must_be_timezone_aware")

    rows = _team_rows(team_games_played)
    eligibility = evaluate_boost_eligibility(rows)
    if expected_pool_size <= ROSTER_SIZE:
        return _from_eligibility(
            eligibility,
            blocked_reasons=("full_roster_pool_required",),
            pool_complete=False,
            pool_detail="full_roster_pool_required",
        )
    base = contract if contract is not None else NhlContestContract()
    regime, eligibility = force_none_while_gated(base.boost_regime, eligibility)
    audited = replace(base, boost_regime=regime)
    pool = tuple(candidates)
    fixture = NhlAuditFixture(
        contract=audited,
        candidates=pool,
        expected_roster_size=ROSTER_SIZE,
        team_games_played=rows,
        expected_pool_size=expected_pool_size,
        games_scheduled=games_scheduled,
        games_captured=games_captured,
    )
    report = evaluate_nhl_audit(fixture, decision_at=now)
    pool_item = next(item for item in report.items if item.key == "pool_completeness")
    reasons = list(report.blocked_reasons)

    pick_ids: tuple[int, ...] | None = None
    in_window = False
    if pool_item.ok:
        pool_ids = {candidate.player_id for candidate in pool}
        missing = [player_id for player_id in pool_ids if player_id not in projected_values]
        if missing:
            reasons.append(f"missing_projection_for_{len(missing)}_players")
        else:
            values = {player_id: float(projected_values[player_id]) for player_id in pool_ids}
            scoped_boosts = None
            if card_boosts is not None:
                scoped_boosts = {
                    player_id: float(card_boosts[player_id])
                    for player_id in pool_ids
                    if player_id in card_boosts
                }
            pick = select_no_boost_five_from_full_pool(
                values,
                expected_pool_size=len(values),
                card_boosts=scoped_boosts,
                contract=audited,
                team_games_played=rows,
            )
            coherence = evaluate_freeze_coherence(
                pick=pick,
                contract=audited,
                now=now,
                lock_at=lock_at,
                eligibility=eligibility,
                pool_complete=True,
            )
            pick_ids = pick.player_ids
            in_window = coherence.in_t40_window
            if not coherence.ok:
                reasons.extend(reason for reason in coherence.reasons if reason not in reasons)

    unique_reasons = tuple(dict.fromkeys(reasons))
    return _from_eligibility(
        eligibility,
        blocked_reasons=unique_reasons,
        pool_complete=pool_item.ok,
        pool_detail=pool_item.detail,
        in_t40_window=in_window,
        pick_player_ids=pick_ids,
        freeze_ready=not unique_reasons and pick_ids is not None,
    )

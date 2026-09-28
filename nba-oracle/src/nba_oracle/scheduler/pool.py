"""Draftable-only player pool for the NBA freeze gate.

Completeness uses games whose tip is still ahead of the decision clock.
A game that has already tipped drops out of both the roster and the
matched set, so an earlier tip cannot leave every later window
permanently incomplete. An unobserved player on a still-draftable game
fails closed.

Five distinct observed players is the portfolio card size used by the
other sports' T-40 gates. Live NBA contest law is unverified; this
module does not claim a provider roster rule beyond fail-closed size.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

ROSTER_SIZE = 5


@dataclass(frozen=True)
class TipGame:
    """One NBA game tip used only for draftable-window math."""

    game_id: str
    tip_at: datetime


@dataclass(frozen=True)
class PoolPlayer:
    """One roster row. ``observed`` means eligibility was seen this collect."""

    player_id: str
    game_id: str
    observed: bool
    evidence_at: datetime | None = None


@dataclass(frozen=True)
class PoolAssessment:
    """Pool gate outcome. ``ok`` is false whenever ``reasons`` is non-empty."""

    ok: bool
    reasons: tuple[str, ...]
    draftable_game_ids: tuple[str, ...]
    roster_count: int
    observed_count: int
    unmatched_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "reasons": list(self.reasons),
            "draftable_game_ids": list(self.draftable_game_ids),
            "roster_count": self.roster_count,
            "observed_count": self.observed_count,
            "unmatched_ids": list(self.unmatched_ids),
        }


def _require_aware(label: str, value: datetime) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{label}_must_be_timezone_aware")


def evaluate_draftable_pool(
    *,
    games: tuple[TipGame, ...],
    players: tuple[PoolPlayer, ...],
    decision_at: datetime,
    evidence_epoch: datetime | None = None,
    max_age_seconds: int = 900,
    roster_size: int = ROSTER_SIZE,
) -> PoolAssessment:
    """Return whether the draftable pool is complete enough to freeze.

    ``evidence_epoch`` is the single collect-tick stamp. A player whose
    ``evidence_at`` equals that epoch is fresh even when ``decision_at``
    is later than ``max_age_seconds`` after the original observation.
    Callers that do not stamp an epoch still fail closed on aged rows.
    """

    _require_aware("decision_at", decision_at)
    if evidence_epoch is not None:
        _require_aware("evidence_epoch", evidence_epoch)
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds_must_be_positive")
    if roster_size <= 0:
        raise ValueError("roster_size_must_be_positive")

    game_ids = [game.game_id for game in games]
    if len(game_ids) != len(set(game_ids)):
        return _assessment(
            reasons=("duplicate_game",),
            draftable=(),
            roster_count=0,
            observed_count=0,
            unmatched=(),
        )
    for game in games:
        _require_aware("tip_at", game.tip_at)

    known = set(game_ids)
    orphans = tuple(sorted(player.player_id for player in players if player.game_id not in known))
    if orphans:
        return _assessment(
            reasons=("player_game_identity_mismatch",),
            draftable=tuple(sorted(game.game_id for game in games if game.tip_at > decision_at)),
            roster_count=0,
            observed_count=0,
            unmatched=orphans,
        )

    draftable = tuple(game for game in games if game.tip_at > decision_at)
    draftable_ids = {game.game_id for game in draftable}
    if not draftable:
        return _assessment(
            reasons=("no_draftable_games",),
            draftable=(),
            roster_count=0,
            observed_count=0,
            unmatched=(),
        )

    roster = tuple(player for player in players if player.game_id in draftable_ids)
    roster_ids = [player.player_id for player in roster]
    reasons: list[str] = []
    if len(roster_ids) != len(set(roster_ids)):
        reasons.append("duplicate_player")
    if not roster:
        reasons.append("empty_draftable_roster")

    unmatched = tuple(sorted(player.player_id for player in roster if not player.observed))
    if unmatched:
        reasons.append("incomplete_player_pool")

    missing_clock: list[str] = []
    future: list[str] = []
    stale: list[str] = []
    for player in roster:
        if not player.observed:
            continue
        evidence_at = player.evidence_at
        if evidence_at is None:
            missing_clock.append(player.player_id)
            continue
        _require_aware("evidence_at", evidence_at)
        if evidence_at > decision_at:
            future.append(player.player_id)
            continue
        same_tick = evidence_epoch is not None and evidence_at == evidence_epoch
        age = (decision_at - evidence_at).total_seconds()
        if age > max_age_seconds and not same_tick:
            stale.append(player.player_id)
    if missing_clock:
        reasons.append("missing_evidence_clock")
    if future:
        reasons.append("future_evidence")
    if stale:
        reasons.append("stale_player")

    observed = [player for player in roster if player.observed]
    if not reasons and len({player.player_id for player in observed}) < roster_size:
        if roster_size == ROSTER_SIZE:
            reasons.append("fewer_than_five_candidates")
        else:
            reasons.append(f"fewer_than_roster:{roster_size}")

    return _assessment(
        reasons=tuple(reasons),
        draftable=tuple(sorted(draftable_ids)),
        roster_count=len(roster),
        observed_count=len(observed),
        unmatched=unmatched,
    )


def _assessment(
    *,
    reasons: tuple[str, ...],
    draftable: tuple[str, ...],
    roster_count: int,
    observed_count: int,
    unmatched: tuple[str, ...],
) -> PoolAssessment:
    return PoolAssessment(
        ok=not reasons,
        reasons=reasons,
        draftable_game_ids=draftable,
        roster_count=roster_count,
        observed_count=observed_count,
        unmatched_ids=unmatched,
    )

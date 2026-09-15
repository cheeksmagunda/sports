"""Project live candidate values from Corpus G history.

This module is deliberately small and auditable. It turns the validated live
candidate pool plus Real-id history join into slot-ordered projected values
without provider writes. Slot selection is boost-aware: it holds under both
the zero-boost week-1 regime and the live card-boost table from week 2 on.
Appearance count is never a ranking bonus (#185); low-n history shrinks
toward the position prior instead of being discarded.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from statistics import mean, pstdev

from nfl_oracle.contests.schema import OBSERVED_SLOT_MULTIPLIERS
from nfl_oracle.valuelaw.candidates import CandidateRow


@dataclass(frozen=True)
class CandidateProjection:
    player_id: int
    name: str
    team: str
    position: str
    injury_status: str | None
    card_boost: float
    projected_value: float
    prior_games: int
    method: str
    uncertainty: float


@dataclass(frozen=True)
class SlotRecommendation:
    slot: int
    slot_multiplier: float
    projection: CandidateProjection
    expected_total_value: float


def position_priors(rows: Iterable[CandidateRow]) -> dict[str, float]:
    """Return position means from the joined player histories."""

    values: dict[str, list[float]] = {}
    for row in rows:
        if row.history is None:
            continue
        values.setdefault(row.candidate.position, []).extend(row.history.values)
    return {position: mean(samples) for position, samples in values.items() if samples}


def ewma(values: Sequence[float], *, decay: float = 0.9) -> float:
    """Return an exponentially weighted mean with newest games weighted most."""

    if not values:
        raise ValueError("ewma_requires_values")
    if not 0 < decay <= 1:
        raise ValueError("decay_out_of_range")
    weighted = list(enumerate(reversed(values)))
    denominator = sum(decay**age for age, _value in weighted)
    return sum(value * (decay**age) for age, value in weighted) / denominator


def project_candidate(
    row: CandidateRow,
    priors: Mapping[str, float],
    *,
    min_player_games: int = 3,
    decay: float = 0.9,
) -> CandidateProjection:
    """Project one candidate's finalized Real value from predecision priors."""

    status = (row.candidate.injury_status or "").lower()
    if status in {"out", "inactive", "suspended", "ir"}:
        return CandidateProjection(
            player_id=row.player_id,
            name=row.candidate.name,
            team=row.candidate.team,
            position=row.candidate.position,
            injury_status=row.candidate.injury_status,
            card_boost=row.candidate.card_boost,
            projected_value=0.0,
            prior_games=0 if row.history is None else row.history.games,
            method="injury_zero",
            uncertainty=0.0,
        )
    fallback = priors.get(row.candidate.position, 0.0)
    if row.history is not None and row.history.games >= 1:
        values = row.history.recent_values
        player_est = ewma(values, decay=decay)
        n = float(row.history.games)
        if row.history.games >= min_player_games:
            projected = player_est
            method = "player_ewma"
        else:
            # Issue #185: low-frequency high-EV sleepers must keep a value
            # signal. Pure position-mean fallback buries a 1-game outlier
            # under corpus chalk that dominates the position pool. Shrink
            # toward the position prior instead of discarding the observation.
            k = float(min_player_games)
            projected = (n * player_est + k * fallback) / (n + k)
            method = "player_ewma_shrunk"
        return CandidateProjection(
            player_id=row.player_id,
            name=row.candidate.name,
            team=row.candidate.team,
            position=row.candidate.position,
            injury_status=row.candidate.injury_status,
            card_boost=row.candidate.card_boost,
            projected_value=projected,
            prior_games=row.history.games,
            method=method,
            uncertainty=pstdev(values) if len(values) > 1 else 0.0,
        )
    return CandidateProjection(
        player_id=row.player_id,
        name=row.candidate.name,
        team=row.candidate.team,
        position=row.candidate.position,
        injury_status=row.candidate.injury_status,
        card_boost=row.candidate.card_boost,
        projected_value=fallback,
        prior_games=0 if row.history is None else row.history.games,
        method="position_mean",
        uncertainty=0.0,
    )


def project_candidates(
    rows: Sequence[CandidateRow],
    *,
    min_player_games: int = 3,
    decay: float = 0.9,
) -> tuple[CandidateProjection, ...]:
    priors = position_priors(rows)
    return tuple(
        project_candidate(row, priors, min_player_games=min_player_games, decay=decay)
        for row in rows
    )


def recommend_slots(
    projections: Sequence[CandidateProjection],
    *,
    slot_multipliers: Sequence[float] = OBSERVED_SLOT_MULTIPLIERS,
) -> tuple[SlotRecommendation, ...]:
    """Return the five slot-ordered recommendations that maximize total score.

    ``score = value * (slot + boost)`` splits into an order-invariant
    ``sum(value * boost)`` term and a rearrangement term ``sum(value * slot)``
    that, for any FIXED set of five players, is maximized by descending-value
    slot assignment regardless of boost (rearrangement inequality). So once
    the eligible pool is sorted by projected value descending, selecting the
    optimal SET reduces to a linear-time DP over that sorted pool: this
    mirrors ``nfl_oracle.replay.harness.hindsight_best_lineup`` exactly, the
    same fix for the same bug class, applied to projected rather than
    finalized values. Descending projected value alone (the prior behavior of
    this function) is only optimal when every candidate shares the same
    boost, e.g. the zero-boost regime; it is not assumed here.
    """

    k = len(slot_multipliers)
    if k != 5:
        raise ValueError("five_slots_required")
    eligible = [p for p in projections if p.projected_value > 0]
    if len(eligible) < k:
        raise ValueError("fewer_than_five_projected_candidates")
    ranked = sorted(eligible, key=lambda p: (-p.projected_value, p.player_id))
    slots = [float(m) for m in slot_multipliers]
    n = len(ranked)

    neg_inf = float("-inf")
    # best[j] = max achievable total using a prefix of the value-sorted pool,
    # having filled j of the k slots so far (slot j+1 is assigned next).
    best: list[float] = [0.0] + [neg_inf] * k
    choice: list[list[bool]] = [[False] * (k + 1) for _ in range(n)]
    for i, projection in enumerate(ranked):
        own_boost_total = projection.projected_value * projection.card_boost
        for j in range(min(i, k - 1), -1, -1):
            if best[j] == neg_inf:
                continue
            candidate = best[j] + own_boost_total + projection.projected_value * slots[j]
            if candidate > best[j + 1]:
                best[j + 1] = candidate
                choice[i][j + 1] = True

    if best[k] == neg_inf:
        raise ValueError("fewer_than_five_projected_candidates")
    chosen: list[int] = []
    j = k
    for i in range(n - 1, -1, -1):
        if j > 0 and choice[i][j]:
            chosen.append(i)
            j -= 1
    chosen.reverse()

    def expected_total_value(slot_index: int, projection: CandidateProjection) -> float:
        return projection.projected_value * (slots[slot_index] + projection.card_boost)

    return tuple(
        SlotRecommendation(
            slot=slot_index + 1,
            slot_multiplier=slots[slot_index],
            projection=ranked[i],
            expected_total_value=expected_total_value(slot_index, ranked[i]),
        )
        for slot_index, i in enumerate(chosen)
    )

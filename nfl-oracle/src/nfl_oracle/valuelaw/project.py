"""Project live candidate values from Corpus G history.

This module is deliberately small and auditable for the zero-boost week-1
decision path. It turns the validated live candidate pool plus Real-id history
join into slot-ordered projected values without provider writes.
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
    if row.history is not None and row.history.games >= min_player_games:
        values = row.history.recent_values
        return CandidateProjection(
            player_id=row.player_id,
            name=row.candidate.name,
            team=row.candidate.team,
            position=row.candidate.position,
            injury_status=row.candidate.injury_status,
            card_boost=row.candidate.card_boost,
            projected_value=ewma(values, decay=decay),
            prior_games=row.history.games,
            method="player_ewma",
            uncertainty=pstdev(values) if len(values) > 1 else 0.0,
        )
    fallback = priors.get(row.candidate.position, 0.0)
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
    """Return the five slot-ordered recommendations for a zero-boost slate."""

    if len(slot_multipliers) != 5:
        raise ValueError("five_slots_required")
    eligible = [p for p in projections if p.projected_value > 0]
    if len(eligible) < 5:
        raise ValueError("fewer_than_five_projected_candidates")
    if any(p.card_boost != 0 for p in eligible):
        raise ValueError("recommend_slots_requires_zero_boost_regime")
    chosen = sorted(eligible, key=lambda p: (-p.projected_value, p.player_id))[:5]
    return tuple(
        SlotRecommendation(
            slot=index + 1,
            slot_multiplier=float(slot_multipliers[index]),
            projection=projection,
            expected_total_value=projection.projected_value * float(slot_multipliers[index]),
        )
        for index, projection in enumerate(chosen)
    )

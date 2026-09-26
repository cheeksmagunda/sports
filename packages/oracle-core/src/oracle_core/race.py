"""Provider-neutral race fitness helpers for variant search (#332, #339).

A "race" compares candidate variants on one unit of historical evidence:
one slate, one game, one fold, or one replay window. Sport applications own
how candidates are generated and how their scores are computed. This module
only classifies finishes and aggregates WIN/CLOSE fitness share.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any


class FitResult(str, Enum):  # noqa: UP042
    """WIN/CLOSE/OUT classification for one candidate in one race."""

    WIN = "win"
    CLOSE = "close"
    OUT = "out"


@dataclass(frozen=True)
class FitConfig:
    """Provider-neutral knobs for WIN/CLOSE race fitness.

    ``close_score_gap`` is an absolute tolerance from the best score.
    ``close_score_pct`` is a relative tolerance from the best score's absolute
    magnitude. The effective CLOSE band is the larger of the two.
    ``min_races`` lets callers reject under-sampled candidates when ranking the
    aggregated summaries.
    """

    close_score_gap: float = 0.0
    close_score_pct: float = 0.0
    higher_is_better: bool = True
    min_races: int = 1

    def __post_init__(self) -> None:
        if self.close_score_gap < 0:
            raise ValueError("close_score_gap must be non-negative")
        if not 0.0 <= self.close_score_pct <= 1.0:
            raise ValueError("close_score_pct must be between 0.0 and 1.0")
        if self.min_races < 1:
            raise ValueError("min_races must be at least 1")

    def close_tolerance(self, best_score: float) -> float:
        """Return the effective CLOSE tolerance around the best score."""

        return max(self.close_score_gap, abs(best_score) * self.close_score_pct)

    def gap_from_best(self, *, score: float, best_score: float) -> float:
        """Return a non-negative gap for non-winning scores."""

        if self.higher_is_better:
            return best_score - score
        return score - best_score


@dataclass(frozen=True)
class FitOutcome:
    """One candidate's finish in one race."""

    candidate_id: str
    score: float
    result: FitResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "score": self.score,
            "result": self.result.value,
        }


@dataclass(frozen=True)
class FitnessSummary:
    """Aggregated WIN/CLOSE fitness for one candidate across races."""

    candidate_id: str
    races: int
    wins: int
    closes: int
    losses: int
    win_share: float
    close_share: float
    win_or_close_share: float
    fitness: float
    eligible: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "races": self.races,
            "wins": self.wins,
            "closes": self.closes,
            "losses": self.losses,
            "win_share": self.win_share,
            "close_share": self.close_share,
            "win_or_close_share": self.win_or_close_share,
            "fitness": self.fitness,
            "eligible": self.eligible,
        }


def rank_race(
    scores: Mapping[str, float],
    *,
    config: FitConfig = FitConfig(),
) -> tuple[FitOutcome, ...]:
    """Classify every candidate in one race as WIN, CLOSE, or OUT."""

    if not scores:
        return ()

    validated: dict[str, float] = {}
    for candidate_id, score in scores.items():
        if not math.isfinite(score):
            raise ValueError(f"score for {candidate_id!r} must be finite")
        validated[candidate_id] = float(score)

    best_score = (
        max(validated.values()) if config.higher_is_better else min(validated.values())
    )
    tolerance = config.close_tolerance(best_score)

    outcomes: list[FitOutcome] = []
    for candidate_id in sorted(validated):
        score = validated[candidate_id]
        gap = config.gap_from_best(score=score, best_score=best_score)
        if gap <= 0:
            result = FitResult.WIN
        elif gap <= tolerance:
            result = FitResult.CLOSE
        else:
            result = FitResult.OUT
        outcomes.append(FitOutcome(candidate_id=candidate_id, score=score, result=result))
    return tuple(outcomes)


def summarize_fitness(
    races: Iterable[Mapping[str, float]],
    *,
    config: FitConfig = FitConfig(),
) -> dict[str, FitnessSummary]:
    """Aggregate WIN/CLOSE share across many races.

    Candidates absent from a race are not penalized for that race; they simply
    have one fewer observed result.
    """

    counts: dict[str, dict[FitResult, int]] = defaultdict(
        lambda: {
            FitResult.WIN: 0,
            FitResult.CLOSE: 0,
            FitResult.OUT: 0,
        }
    )
    for race in races:
        for outcome in rank_race(race, config=config):
            counts[outcome.candidate_id][outcome.result] += 1

    summaries: dict[str, FitnessSummary] = {}
    for candidate_id in sorted(counts):
        wins = counts[candidate_id][FitResult.WIN]
        closes = counts[candidate_id][FitResult.CLOSE]
        losses = counts[candidate_id][FitResult.OUT]
        races_count = wins + closes + losses
        win_share = wins / races_count if races_count else 0.0
        close_share = closes / races_count if races_count else 0.0
        win_or_close_share = win_share + close_share
        eligible = races_count >= config.min_races
        summaries[candidate_id] = FitnessSummary(
            candidate_id=candidate_id,
            races=races_count,
            wins=wins,
            closes=closes,
            losses=losses,
            win_share=win_share,
            close_share=close_share,
            win_or_close_share=win_or_close_share,
            fitness=win_or_close_share if eligible else 0.0,
            eligible=eligible,
        )
    return summaries

"""WNBA evaluate hook for the portfolio race engine (#356).

Maps per-slate realized scores onto WIN/CLOSE observations compatible with
``oracle_core.race``. Symmetric to ``nfl_oracle.replay.racer``: offline tests
and Actions skeletons pass precomputed rows via ``EvalContext.extras`` so the
hook never opens Postgres or a live model artifact.

Fitness uses ``oracle_core.fitness``:

* **WIN** -- ``score >= winner``
* **CLOSE** -- ``score >= (1 - b) * winner``
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Protocol

from oracle_core.fitness import win_close
from oracle_core.race import (
    EvalContext,
    RankObservation,
    SlateResult,
    Variant,
)

_RACE_SOURCE = "oracle_core.race"

DEFAULT_CLOSE_BAND = 0.10
EXTRAS_SLATES = "slate_scores"
EXTRAS_CLOSE_BAND = "close_band"


class EvaluationFn(Protocol):
    def __call__(self, variant: Variant, context: EvalContext) -> SlateResult: ...


@dataclass(frozen=True)
class SlateScore:
    """One precomputed WNBA slate outcome for offline race evaluation."""

    slate_id: str
    score: float
    winner_score: float
    rank20_score: float | None = None
    field_size: int | None = None
    rank: int | None = None


def _resolve_close_band(extras: Mapping[str, Any]) -> float:
    raw = extras.get(EXTRAS_CLOSE_BAND)
    if raw is None:
        return DEFAULT_CLOSE_BAND
    band = float(raw)
    if not 0.0 <= band <= 1.0:
        raise ValueError("close_band_out_of_range")
    return band


def _coerce_slate(raw: SlateScore | Mapping[str, Any]) -> SlateScore | None:
    if isinstance(raw, SlateScore):
        return raw
    if not isinstance(raw, Mapping):
        return None
    slate_id = raw.get("slate_id")
    score = raw.get("score")
    winner = raw.get("winner_score")
    if slate_id is None or score is None or winner is None:
        return None
    rank20 = raw.get("rank20_score")
    return SlateScore(
        slate_id=str(slate_id),
        score=float(score),
        winner_score=float(winner),
        rank20_score=None if rank20 is None else float(rank20),
        field_size=None if raw.get("field_size") is None else int(raw["field_size"]),
        rank=None if raw.get("rank") is None else int(raw["rank"]),
    )


def observation_from_slate(slate: SlateScore, *, b: float) -> RankObservation:
    won, close = win_close(slate.score, slate.winner_score, b)
    return RankObservation(
        slate_id=slate.slate_id,
        won=won,
        close=close,
        score=slate.score,
        rank=slate.rank,
        field_size=slate.field_size,
    )


def evaluate(variant: Variant, context: EvalContext) -> SlateResult:
    """Offline evaluate hook: slate scores from ``context.extras``.

    Expected extras:

    * ``slate_scores`` -- sequence of :class:`SlateScore` or mappings
    * ``close_band`` -- ``b`` for CLOSE (default :data:`DEFAULT_CLOSE_BAND`)

    Missing or empty extras return zero observations so workflow skeletons
    stay no-op until a corpus is wired (#337).
    """

    extras = dict(context.extras or {})
    band = _resolve_close_band(extras)
    observations: list[RankObservation] = []
    for raw in extras.get(EXTRAS_SLATES) or ():
        slate = _coerce_slate(raw)
        if slate is None:
            continue
        observations.append(observation_from_slate(slate, b=band))
    return SlateResult(variant_id=variant.id, observations=tuple(observations))


def make_evaluate_fn(
    slates: Sequence[SlateScore | Mapping[str, Any]],
    *,
    b: float | None = None,
) -> EvaluationFn:
    band = DEFAULT_CLOSE_BAND if b is None else float(b)
    if not 0.0 <= band <= 1.0:
        raise ValueError("close_band_out_of_range")

    def _evaluate(variant: Variant, context: EvalContext) -> SlateResult:
        extras = dict(context.extras or {})
        extras.setdefault(EXTRAS_CLOSE_BAND, band)
        extras.setdefault(EXTRAS_SLATES, slates)
        return evaluate(variant, replace(context, extras=extras))

    return _evaluate


def race_contract_source() -> str:
    return _RACE_SOURCE


__all__ = [
    "DEFAULT_CLOSE_BAND",
    "EXTRAS_CLOSE_BAND",
    "EXTRAS_SLATES",
    "EvalContext",
    "EvaluationFn",
    "RankObservation",
    "SlateResult",
    "SlateScore",
    "Variant",
    "evaluate",
    "make_evaluate_fn",
    "observation_from_slate",
    "race_contract_source",
]

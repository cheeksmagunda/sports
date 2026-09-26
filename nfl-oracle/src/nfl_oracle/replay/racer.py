"""NFL evaluate hook for the portfolio race engine (#339).

Maps :class:`~nfl_oracle.replay.contest_pool_replay.ContestPoolResult`
``production_score`` / ``winner_score`` (and optional visible rank-20 floor)
onto per-slate WIN/CLOSE observations compatible with ``oracle_core.race``.

Fitness (portfolio contract, Refs #332 / #339):

* **WIN** -- ``production_score >= winner_score``
* **CLOSE** -- ``production_score >= (1 - b) * winner_score``, where
  ``b = 1 - median(rank20_score / winner_score)`` over graded contests
  (so the CLOSE floor sits near the visible twentieth). WIN implies CLOSE.

Honesty boundary inherited from the contest-pool replay: only the top twenty
entries are visible. Observations never invent a field percentile.

``oracle_core.race`` may not be on ``main`` yet. Until it lands, this module
ships local dataclasses matching the designed ``RankObservation`` /
``SlateResult`` / ``EvalContext`` / ``Variant`` contract and marks the import
site with a TODO. Heavy walk-forward replay stays injectable: offline tests
and Actions skeletons pass precomputed :class:`ContestPoolResult` rows via
:class:`EvalContext` extras (or the offline :func:`make_evaluate_fn` helper)
instead of pulling Corpus G / fitting ridge in-process.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Protocol

from nfl_oracle.recommendations.picker_knobs import PickerKnobs
from nfl_oracle.replay.contest_pool_replay import ContestPoolResult

# ---------------------------------------------------------------------------
# oracle_core.race contract (import when present; else local stubs)
# ---------------------------------------------------------------------------

try:
    # TODO(#339): prefer oracle_core.race once Phase 2 lands on main.
    from oracle_core.race import (  # type: ignore[import-not-found]
        EvalContext,
        RankObservation,
        SlateResult,
        Variant,
    )

    _RACE_SOURCE = "oracle_core.race"
except ImportError:  # pragma: no cover - exercised when race is absent

    @dataclass(frozen=True)
    class Variant:  # type: ignore[no-redef]
        """Local stub matching ``oracle_core.race.Variant``."""

        params: Mapping[str, Any]

        @property
        def id(self) -> str:
            # Content-addressed id lands with oracle_core.race; stubs use a
            # stable, order-independent repr so offline tests stay deterministic.
            items = sorted((str(k), repr(v)) for k, v in dict(self.params).items())
            return "stub:" + ",".join(f"{k}={v}" for k, v in items)

    @dataclass(frozen=True)
    class RankObservation:  # type: ignore[no-redef]
        """Local stub matching ``oracle_core.race.RankObservation``."""

        slate_id: str
        won: bool
        close: bool
        score: float = 0.0
        rank: int | None = None
        field_size: int | None = None

    @dataclass(frozen=True)
    class SlateResult:  # type: ignore[no-redef]
        """Local stub matching ``oracle_core.race.SlateResult``."""

        variant_id: str
        observations: tuple[RankObservation, ...]

    @dataclass(frozen=True)
    class EvalContext:  # type: ignore[no-redef]
        """Local stub matching ``oracle_core.race.EvalContext``."""

        fidelity: Any = None
        seed: int = 0
        generation: int = 0
        now: datetime | None = None
        cache_dir: Path | None = None
        extras: Mapping[str, Any] = field(default_factory=dict)

    _RACE_SOURCE = "nfl_oracle.replay.racer.stub"


#: Fallback CLOSE band when no (rank20, winner) pairs are available.
#: Roughly a 10 percent gap under the winner -- within the observed
#: Corpus C range (~0.07-0.12) from the #332 NFL race design.
DEFAULT_CLOSE_BAND = 0.10

#: EvalContext.extras keys the offline evaluate path understands.
EXTRAS_RESULTS = "contest_pool_results"
EXTRAS_RESULTS_BY_PROFILE = "contest_pool_results_by_profile"
EXTRAS_CLOSE_BAND = "close_band"
EXTRAS_PROFILE_KEY = "profile_param"


class EvaluationFn(Protocol):
    """Application-supplied point-in-time backtest (``oracle_core.race`` shape)."""

    def __call__(self, variant: Variant, context: EvalContext) -> SlateResult: ...


# ---------------------------------------------------------------------------
# WIN / CLOSE classification
# ---------------------------------------------------------------------------


def gap_fraction(rank20_score: float, winner_score: float) -> float | None:
    """Return ``b = 1 - rank20/winner`` so CLOSE ≈ visible twentieth.

    Returns ``None`` when the pair is unusable (non-positive winner, ratio
    outside ``(0, 1]``).
    """
    if winner_score <= 0.0:
        return None
    ratio = rank20_score / winner_score
    if not 0.0 < ratio <= 1.0:
        return None
    return 1.0 - ratio


def close_band_from_ratios(
    pairs: Sequence[tuple[float, float]],
    *,
    default: float = DEFAULT_CLOSE_BAND,
) -> float:
    """Median CLOSE band ``b`` from ``(rank20_score, winner_score)`` pairs."""
    gaps = [gap for rank20, winner in pairs if (gap := gap_fraction(rank20, winner)) is not None]
    return float(median(gaps)) if gaps else default


def classify_scores(
    score: float,
    winner_score: float,
    *,
    b: float,
) -> tuple[bool, bool]:
    """Return ``(won, close)``. WIN implies CLOSE.

    Differs slightly from :attr:`ContestPoolResult.beats_winner` (strict ``>``):
    race fitness uses ``>=`` so tying the visible winner counts as a WIN.
    """
    if b < 0.0 or b > 1.0:
        raise ValueError("close_band_out_of_range")
    won = score >= winner_score
    close = won or score >= (1.0 - b) * winner_score
    return won, close


def observation_from_scores(
    *,
    slate_id: str,
    score: float,
    winner_score: float,
    b: float,
    field_size: int | None = None,
    rank: int | None = None,
) -> RankObservation:
    """Build one RankObservation from raw scores and a CLOSE band."""
    won, close = classify_scores(score, winner_score, b=b)
    return RankObservation(
        slate_id=slate_id,
        won=won,
        close=close,
        score=score,
        rank=rank,
        field_size=field_size,
    )


def observation_from_contest_pool_result(
    result: ContestPoolResult,
    *,
    b: float,
) -> RankObservation | None:
    """Map one ContestPoolResult onto a RankObservation.

    Returns ``None`` when ``winner_score`` is missing (contest not gradeable
    for WIN/CLOSE). Does not invent a field rank: the archive only exposes the
    visible top twenty.
    """
    if result.winner_score is None:
        return None
    return observation_from_scores(
        slate_id=str(result.contest_id),
        score=result.production_score,
        winner_score=result.winner_score,
        b=b,
        field_size=result.entrants,
    )


def observations_from_contest_pool_results(
    results: Sequence[ContestPoolResult],
    *,
    b: float,
) -> tuple[RankObservation, ...]:
    """Convert a walk-forward ContestPoolResult sequence into observations."""
    out: list[RankObservation] = []
    for result in results:
        obs = observation_from_contest_pool_result(result, b=b)
        if obs is not None:
            out.append(obs)
    return tuple(out)


# ---------------------------------------------------------------------------
# Variant -> picker knobs (wiring for a future live evaluate path)
# ---------------------------------------------------------------------------


def picker_knobs_from_variant(variant: Variant) -> PickerKnobs:
    """Translate race variant params into :class:`PickerKnobs`.

    Recognized keys: ``boost_rank_blend``, ``position_calibration``,
    ``profile``. Missing numerics default to identity (0.0). The live
    ``replay_contest_pools`` path is not invoked here; callers that need a
    full walk-forward must inject precomputed results or call the replay
    module themselves.
    """
    params = dict(variant.params)
    blend = float(params.get("boost_rank_blend", 0.0))
    position = float(params.get("position_calibration", 0.0))
    profile = str(params.get("profile") or "variant").strip() or "variant"
    return PickerKnobs(
        boost_rank_blend=blend,
        position_calibration=position,
        profile=profile,
    )


def _resolve_close_band(extras: Mapping[str, Any]) -> float:
    raw = extras.get(EXTRAS_CLOSE_BAND)
    if raw is None:
        return DEFAULT_CLOSE_BAND
    band = float(raw)
    if not 0.0 <= band <= 1.0:
        raise ValueError("close_band_out_of_range")
    return band


def _results_for_variant(
    variant: Variant, extras: Mapping[str, Any]
) -> Sequence[ContestPoolResult]:
    by_profile = extras.get(EXTRAS_RESULTS_BY_PROFILE)
    if isinstance(by_profile, Mapping):
        profile_key = str(extras.get(EXTRAS_PROFILE_KEY) or "profile")
        profile = str(variant.params.get(profile_key) or picker_knobs_from_variant(variant).profile)
        found = by_profile.get(profile)
        if found is None:
            found = by_profile.get(picker_knobs_from_variant(variant).profile)
        if found is not None:
            return list(found)
    results = extras.get(EXTRAS_RESULTS)
    if results is None:
        return ()
    return list(results)


def _slate_from_extras(variant: Variant, extras: Mapping[str, Any]) -> SlateResult:
    b = _resolve_close_band(extras)
    results = _results_for_variant(variant, extras)
    observations = observations_from_contest_pool_results(results, b=b)
    return SlateResult(variant_id=variant.id, observations=observations)


def evaluate(variant: Variant, context: EvalContext) -> SlateResult:
    """Offline evaluate hook: ContestPoolResult rows from ``context.extras``.

    Expected extras (any combination):

    * ``contest_pool_results`` -- sequence of :class:`ContestPoolResult`
    * ``contest_pool_results_by_profile`` -- map profile -> results
    * ``close_band`` -- ``b`` for CLOSE (default :data:`DEFAULT_CLOSE_BAND`)
    * ``profile_param`` -- variant param name holding the profile key

    When no gradeable rows are present, returns an empty observation tuple so
    workflow skeletons stay no-op until a corpus is wired.
    """
    return _slate_from_extras(variant, dict(context.extras or {}))


def make_evaluate_fn(
    results: Sequence[ContestPoolResult] | Mapping[str, Sequence[ContestPoolResult]],
    *,
    b: float | None = None,
    profile_param: str = "profile",
) -> EvaluationFn:
    """Build an :class:`EvaluationFn` over precomputed ContestPoolResult rows.

    Pass a sequence to grade every variant against the same walk-forward
    outcomes, or a profile-keyed mapping when the knob sweep already produced
    per-profile :func:`~nfl_oracle.replay.contest_pool_replay.replay_contest_pools_knob_sweep`
    output.
    """
    band = DEFAULT_CLOSE_BAND if b is None else float(b)
    if not 0.0 <= band <= 1.0:
        raise ValueError("close_band_out_of_range")

    def _evaluate(variant: Variant, context: EvalContext) -> SlateResult:
        extras = dict(context.extras or {})
        extras.setdefault(EXTRAS_CLOSE_BAND, band)
        extras.setdefault(EXTRAS_PROFILE_KEY, profile_param)
        if isinstance(results, Mapping):
            extras.setdefault(EXTRAS_RESULTS_BY_PROFILE, results)
        else:
            extras.setdefault(EXTRAS_RESULTS, results)
        return _slate_from_extras(variant, extras)

    return _evaluate


def race_contract_source() -> str:
    """Where RankObservation / SlateResult were loaded from (for diagnostics)."""
    return _RACE_SOURCE


__all__ = [
    "DEFAULT_CLOSE_BAND",
    "EXTRAS_CLOSE_BAND",
    "EXTRAS_PROFILE_KEY",
    "EXTRAS_RESULTS",
    "EXTRAS_RESULTS_BY_PROFILE",
    "EvalContext",
    "EvaluationFn",
    "RankObservation",
    "SlateResult",
    "Variant",
    "classify_scores",
    "close_band_from_ratios",
    "evaluate",
    "gap_fraction",
    "make_evaluate_fn",
    "observation_from_contest_pool_result",
    "observation_from_scores",
    "observations_from_contest_pool_results",
    "picker_knobs_from_variant",
    "race_contract_source",
]

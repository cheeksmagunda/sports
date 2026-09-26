"""Domain-free evolutionary/successive-halving search over backtests.

The insight this module encodes (issues #332 / #339 / #356): machine learning for a
sport application happens in the *backtest*, not inside a single fitted model.
Spawn a large population of configuration variants over every tunable variable,
race them through point-in-time historical evaluation, keep the group that WINS
or gets CLOSE (one elite band), and breed the next generation from that band.

This package is deliberately domain-free. It knows nothing about slates,
players, contests, odds, or any sport. It owns only the provider-neutral
machinery:

* representing a search space and sampling variants from it,
* deterministic variant identity (content-addressed sha256),
* genetics (mutate / crossover / breed),
* fitness aggregation (WIN-or-CLOSE share) and elite-band selection,
* score-based WIN/CLOSE classification helpers (:class:`FitConfig`),
* chronological lockbox split (held-out promotion fold),
* sharding a population for parallel evaluation and merging the records,
* process-pool-friendly shard map helpers,
* atomic, hash-verified persistence of per-generation records,
* an orchestrating :class:`Racer` with a pluggable :class:`StopPolicy`.

The sport application supplies an :data:`EvaluationFn`: given a :class:`Variant`
and an :class:`EvalContext` (which carries the current :class:`Fidelity`, a
deterministic seed, and optional cache handles), it runs its own point-in-time
backtest and returns a :class:`SlateResult` of per-slate :class:`RankObservation`
rows. All sport logic, provider payload parsing, and scoring stay in the app.

Predict-cache hook points
-------------------------
Backtests are dominated by the cost of regenerating model predictions for every
historical slate. An application can avoid recomputing them by caching
predictions (for example one parquet file per slate keyed by the model-input
hash) and having its :data:`EvaluationFn` read from that cache. This module does
not require, read, or write any such cache; it only threads the handles an app
needs to find one. Every hook point below is marked ``predict-cache hook`` in a
comment:

* :class:`EvalContext.cache_dir` -- a directory an app may treat as its
  prediction cache root.
* :class:`EvalContext.extras` -- an arbitrary app-owned mapping (open DB
  handles, a loaded corpus, a warm cache object) passed straight through.
* :class:`Fidelity.slate_budget` -- lets an app read only the first *N* cached
  slates at a cheap rung and the full history at an expensive one.

Keeping the cache entirely app-side preserves the portfolio boundary: no sport
predict parquet schema leaks into ``oracle-core``.
"""

from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, TypeVar, runtime_checkable

from oracle_core.artifacts import ArtifactInfo, atomic_write_json, sha256_bytes

__all__ = [
    "DimKind",
    "Dimension",
    "SearchSpace",
    "Variant",
    "variant_id",
    "Fidelity",
    "EvalContext",
    "EvaluationFn",
    "RankObservation",
    "SlateResult",
    "VariantRecord",
    "Sampler",
    "RandomSampler",
    "SobolSampler",
    "FitResult",
    "FitConfig",
    "FitOutcome",
    "FitnessSummary",
    "rank_race",
    "summarize_fitness",
    "win_or_close_share",
    "top_quantile_band",
    "select_elite",
    "split_lockbox",
    "seed_generation_zero",
    "mutate",
    "crossover",
    "breed_generation",
    "partition_variants",
    "run_shard",
    "merge_shard_records",
    "write_records",
    "process_pool_map",
    "StopPolicy",
    "StopDecision",
    "Racer",
    "RaceResult",
]

_T = TypeVar("_T")
_R = TypeVar("_R")


# ---------------------------------------------------------------------------
# Search space
# ---------------------------------------------------------------------------


class DimKind(StrEnum):
    """The kind of value a search :class:`Dimension` produces."""

    FLOAT = "float"
    LOG_FLOAT = "log_float"
    INT = "int"
    BOOL = "bool"
    CATEGORICAL = "categorical"


@dataclass(frozen=True)
class Dimension:
    """One tunable variable in a :class:`SearchSpace`.

    ``FLOAT``/``LOG_FLOAT``/``INT`` dimensions use ``low``/``high`` (inclusive).
    ``CATEGORICAL`` uses ``choices``. ``BOOL`` needs neither. ``LOG_FLOAT``
    samples uniformly in log-space and requires strictly positive bounds.
    """

    name: str
    kind: DimKind
    low: float | None = None
    high: float | None = None
    choices: tuple[Any, ...] | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Dimension.name must be non-empty")
        if self.kind in (DimKind.FLOAT, DimKind.LOG_FLOAT, DimKind.INT):
            if self.low is None or self.high is None:
                raise ValueError(f"{self.name}: numeric dimension requires low and high")
            if self.low > self.high:
                raise ValueError(f"{self.name}: low must be <= high")
            if self.kind is DimKind.LOG_FLOAT and self.low <= 0:
                raise ValueError(f"{self.name}: log_float requires low > 0")
            if self.kind is DimKind.INT and (
                self.low != int(self.low) or self.high != int(self.high)
            ):
                raise ValueError(f"{self.name}: int bounds must be whole numbers")
        elif self.kind is DimKind.CATEGORICAL:
            if not self.choices:
                raise ValueError(f"{self.name}: categorical dimension requires choices")


@dataclass(frozen=True)
class SearchSpace:
    """An ordered collection of named :class:`Dimension` variables."""

    dimensions: tuple[Dimension, ...]

    def __post_init__(self) -> None:
        names = [dim.name for dim in self.dimensions]
        if len(names) != len(set(names)):
            raise ValueError("SearchSpace dimension names must be unique")

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(dim.name for dim in self.dimensions)

    def by_name(self, name: str) -> Dimension:
        for dim in self.dimensions:
            if dim.name == name:
                return dim
        raise KeyError(name)


# ---------------------------------------------------------------------------
# Variant identity
# ---------------------------------------------------------------------------


def _canonical_bytes(value: Any) -> bytes:
    """Canonical JSON bytes: sorted keys, compact separators, trailing newline.

    Matches :func:`oracle_core.artifacts.atomic_write_json` so a variant id and
    a written records file share one serialization contract.
    """

    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"{payload}\n".encode()


def variant_id(variant: Variant | Mapping[str, Any]) -> str:
    """Return the deterministic content-addressed id for a variant's params.

    Identity is a function of the parameter mapping only, canonicalized so that
    key order and equal values always yield the same digest. Two variants with
    the same parameters are the same individual and share evaluation records.
    """

    params = variant.params if isinstance(variant, Variant) else variant
    return sha256_bytes(_canonical_bytes(dict(params)))


@dataclass(frozen=True)
class Variant:
    """A concrete assignment of values to every :class:`SearchSpace` dimension."""

    params: Mapping[str, Any]

    @property
    def id(self) -> str:
        return variant_id(self.params)


# ---------------------------------------------------------------------------
# Fidelity, evaluation, observations
# ---------------------------------------------------------------------------


@dataclass(frozen=True, order=True)
class Fidelity:
    """One rung of evaluation cost in a successive-halving schedule.

    Higher ``level`` means a more expensive, more trustworthy evaluation.
    ``slate_budget`` is a provider-neutral hint an app may use to bound how many
    historical slates to backtest at this rung (predict-cache hook: read only
    the first ``slate_budget`` cached slates cheaply, the full set at the top).
    """

    level: int
    slate_budget: int = field(default=0, compare=False)
    label: str = field(default="", compare=False)


@dataclass(frozen=True)
class EvalContext:
    """Everything an :data:`EvaluationFn` needs beyond the variant itself."""

    fidelity: Fidelity
    seed: int = 0
    generation: int = 0
    now: datetime | None = None
    # predict-cache hook: an app may treat this as its prediction-cache root.
    cache_dir: Path | None = None
    # predict-cache hook: opaque, app-owned handles (open DB session, loaded
    # corpus, warm cache object) threaded straight through untouched.
    extras: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RankObservation:
    """One point-in-time result: how a variant placed on a single slate.

    ``won`` and ``close`` are decided by the application (it owns what "cash
    line" or "one prize off" means for its contest). ``score`` is the raw
    objective value the app optimizes (points, ROI, ...), used only for
    reporting a mean and as a tie-break, never to redefine win/close.
    """

    slate_id: str
    won: bool
    close: bool
    score: float = 0.0
    rank: int | None = None
    field_size: int | None = None


@dataclass(frozen=True)
class SlateResult:
    """The full set of per-slate observations for one variant evaluation."""

    variant_id: str
    observations: tuple[RankObservation, ...]


#: An application-supplied point-in-time backtest for a single variant.
EvaluationFn = Callable[[Variant, EvalContext], SlateResult]


# ---------------------------------------------------------------------------
# Fitness and elite selection
# ---------------------------------------------------------------------------


def win_or_close_share(result: SlateResult) -> float:
    """Fraction of a variant's slates where it WON or came CLOSE.

    This is the portfolio's fitness function: a variant that never wins outright
    but is repeatedly one prize away is valuable and breeds forward. Returns
    ``0.0`` for an empty observation set (nothing raced, nothing earned).
    """

    if not result.observations:
        return 0.0
    hits = sum(1 for obs in result.observations if obs.won or obs.close)
    return hits / len(result.observations)


def _mean_score(result: SlateResult) -> float:
    if not result.observations:
        return 0.0
    return sum(obs.score for obs in result.observations) / len(result.observations)


def top_quantile_band(values: Sequence[float], *, quantile: float) -> float:
    """Return the fitness threshold that keeps the top ``quantile`` fraction.

    ``quantile`` is the share to KEEP (``0.2`` keeps the best 20 percent). The
    band is the fitness of the k-th best individual where
    ``k = ceil(quantile * n)`` (at least one). Callers keep every variant whose
    fitness is ``>= band``, which is an MCS-style band: ties at the boundary are
    all retained rather than arbitrarily cut.
    """

    if not values:
        raise ValueError("top_quantile_band requires at least one value")
    if not 0.0 < quantile <= 1.0:
        raise ValueError("quantile must be in (0, 1]")
    ordered = sorted(values, reverse=True)
    k = max(1, math.ceil(quantile * len(ordered)))
    return ordered[k - 1]


def select_elite(records: Sequence[VariantRecord], *, quantile: float) -> list[VariantRecord]:
    """Keep the elite band: records at or above the top-``quantile`` fitness.

    Ties at the band are retained (see :func:`top_quantile_band`). The result is
    sorted best-first, breaking ties by variant id for determinism.
    """

    if not records:
        return []
    band = top_quantile_band([r.win_or_close_share for r in records], quantile=quantile)
    elite = [r for r in records if r.win_or_close_share >= band]
    elite.sort(key=lambda r: (-r.win_or_close_share, -r.mean_score, r.variant_id))
    return elite


# ---------------------------------------------------------------------------
# Score-based WIN/CLOSE classification (FitConfig)
# ---------------------------------------------------------------------------


class FitResult(StrEnum):
    """WIN/CLOSE/OUT classification for one candidate in one race."""

    WIN = "win"
    CLOSE = "close"
    OUT = "out"


@dataclass(frozen=True)
class FitConfig:
    """Provider-neutral knobs for score-based WIN/CLOSE race fitness.

    Use this when an evaluation yields raw scores and the application has not
    already decided ``won`` / ``close`` flags on :class:`RankObservation`.
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
    """One candidate's finish in one score-based race."""

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
    config: FitConfig | None = None,
) -> tuple[FitOutcome, ...]:
    """Classify every candidate in one race as WIN, CLOSE, or OUT."""

    cfg = config if config is not None else FitConfig()
    if not scores:
        return ()

    validated: dict[str, float] = {}
    for candidate_id, score in scores.items():
        if not math.isfinite(score):
            raise ValueError(f"score for {candidate_id!r} must be finite")
        validated[candidate_id] = float(score)

    best_score = max(validated.values()) if cfg.higher_is_better else min(validated.values())
    tolerance = cfg.close_tolerance(best_score)

    outcomes: list[FitOutcome] = []
    for candidate_id in sorted(validated):
        score = validated[candidate_id]
        gap = cfg.gap_from_best(score=score, best_score=best_score)
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
    config: FitConfig | None = None,
) -> dict[str, FitnessSummary]:
    """Aggregate WIN/CLOSE share across many score-based races.

    Candidates absent from a race are not penalized for that race; they simply
    have one fewer observed result.
    """

    cfg = config if config is not None else FitConfig()
    counts: dict[str, dict[FitResult, int]] = defaultdict(
        lambda: {
            FitResult.WIN: 0,
            FitResult.CLOSE: 0,
            FitResult.OUT: 0,
        }
    )
    for race in races:
        for outcome in rank_race(race, config=cfg):
            counts[outcome.candidate_id][outcome.result] += 1

    summaries: dict[str, FitnessSummary] = {}
    for candidate_id in sorted(counts):
        wins = counts[candidate_id][FitResult.WIN]
        closes = counts[candidate_id][FitResult.CLOSE]
        losses = counts[candidate_id][FitResult.OUT]
        races_count = wins + closes + losses
        win_share = wins / races_count if races_count else 0.0
        close_share = closes / races_count if races_count else 0.0
        share = win_share + close_share
        eligible = races_count >= cfg.min_races
        summaries[candidate_id] = FitnessSummary(
            candidate_id=candidate_id,
            races=races_count,
            wins=wins,
            closes=closes,
            losses=losses,
            win_share=win_share,
            close_share=close_share,
            win_or_close_share=share,
            fitness=share if eligible else 0.0,
            eligible=eligible,
        )
    return summaries


# ---------------------------------------------------------------------------
# Lockbox split
# ---------------------------------------------------------------------------


def split_lockbox(
    unit_ids: Sequence[str],
    *,
    fraction: float = 0.20,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split chronologically ordered units into search fold and lockbox.

    ``unit_ids`` must already be in chronological order. The last ``fraction``
    of units become the lockbox (promotion gate only). The remainder is the
    search fold used for racing, elite selection, and breeding. Never breed,
    rank, or early-stop on the lockbox.
    """

    if not 0.0 < fraction < 1.0:
        raise ValueError("fraction must be in (0, 1)")
    units = tuple(unit_ids)
    if not units:
        return (), ()
    lockbox_count = max(1, math.ceil(len(units) * fraction)) if len(units) > 1 else 0
    if lockbox_count >= len(units):
        lockbox_count = len(units) - 1
    split_at = len(units) - lockbox_count
    return units[:split_at], units[split_at:]


# ---------------------------------------------------------------------------
# Records and persistence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VariantRecord:
    """A persisted evaluation outcome for one variant in one generation."""

    variant_id: str
    params: Mapping[str, Any]
    generation: int
    fidelity_level: int
    win_or_close_share: float
    mean_score: float
    slates: int

    @property
    def variant(self) -> Variant:
        return Variant(dict(self.params))

    def as_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "params": dict(self.params),
            "generation": self.generation,
            "fidelity_level": self.fidelity_level,
            "win_or_close_share": self.win_or_close_share,
            "mean_score": self.mean_score,
            "slates": self.slates,
        }


def _record_from_result(
    result: SlateResult, *, params: Mapping[str, Any], generation: int, fidelity_level: int
) -> VariantRecord:
    return VariantRecord(
        variant_id=result.variant_id,
        params=dict(params),
        generation=generation,
        fidelity_level=fidelity_level,
        win_or_close_share=win_or_close_share(result),
        mean_score=_mean_score(result),
        slates=len(result.observations),
    )


def merge_shard_records(
    shards: Iterable[Sequence[VariantRecord]],
) -> list[VariantRecord]:
    """Flatten per-shard record lists into one deterministically ordered list.

    Ordering is best-first by fitness, then mean score, then variant id, so the
    merged output does not depend on the order shards completed (which, under a
    process pool, is nondeterministic).
    """

    merged: list[VariantRecord] = []
    for shard in shards:
        merged.extend(shard)
    merged.sort(key=lambda r: (-r.win_or_close_share, -r.mean_score, r.variant_id))
    return merged


def write_records(
    path: str | Path, records: Sequence[VariantRecord], *, mode: int = 0o644
) -> ArtifactInfo:
    """Atomically persist records as canonical JSON and return their metadata.

    Reuses :func:`oracle_core.artifacts.atomic_write_json` for the durable write
    and :func:`oracle_core.artifacts.sha256_bytes` for the integrity digest, so
    the returned :class:`ArtifactInfo` matches exactly what landed on disk.
    """

    payload = [record.as_dict() for record in records]
    destination = atomic_write_json(path, payload, mode=mode)
    data = _canonical_bytes(payload)
    return ArtifactInfo(path=destination, sha256=sha256_bytes(data), size=len(data))


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------


def _sample_value(dim: Dimension, rng: random.Random) -> Any:
    if dim.kind is DimKind.FLOAT:
        assert dim.low is not None and dim.high is not None
        return rng.uniform(dim.low, dim.high)
    if dim.kind is DimKind.LOG_FLOAT:
        assert dim.low is not None and dim.high is not None
        return math.exp(rng.uniform(math.log(dim.low), math.log(dim.high)))
    if dim.kind is DimKind.INT:
        assert dim.low is not None and dim.high is not None
        return rng.randint(int(dim.low), int(dim.high))
    if dim.kind is DimKind.BOOL:
        return rng.random() < 0.5
    # CATEGORICAL
    assert dim.choices is not None
    return dim.choices[rng.randrange(len(dim.choices))]


def _value_from_unit(dim: Dimension, unit: float) -> Any:
    """Map a value in ``[0, 1)`` onto a dimension (for quasi-random samplers)."""

    unit = min(max(unit, 0.0), 1.0 - 1e-12)
    if dim.kind is DimKind.FLOAT:
        assert dim.low is not None and dim.high is not None
        return dim.low + unit * (dim.high - dim.low)
    if dim.kind is DimKind.LOG_FLOAT:
        assert dim.low is not None and dim.high is not None
        return math.exp(math.log(dim.low) + unit * (math.log(dim.high) - math.log(dim.low)))
    if dim.kind is DimKind.INT:
        assert dim.low is not None and dim.high is not None
        span = int(dim.high) - int(dim.low) + 1
        return int(dim.low) + min(int(unit * span), span - 1)
    if dim.kind is DimKind.BOOL:
        return unit < 0.5
    assert dim.choices is not None
    return dim.choices[min(int(unit * len(dim.choices)), len(dim.choices) - 1)]


@runtime_checkable
class Sampler(Protocol):
    """Draws a fresh :class:`Variant` from a :class:`SearchSpace`."""

    def sample(self, space: SearchSpace, rng: random.Random) -> Variant: ...


@dataclass(frozen=True)
class RandomSampler:
    """Independent uniform sampling per dimension (the portfolio default)."""

    def sample(self, space: SearchSpace, rng: random.Random) -> Variant:
        return Variant({dim.name: _sample_value(dim, rng) for dim in space.dimensions})


@dataclass
class SobolSampler:
    """Low-discrepancy (Sobol) sampling for more even space coverage.

    Optional: importing ``scipy`` is deferred to first use so the base package
    never depends on it. If ``scipy`` is unavailable, constructing a variant
    raises :class:`ImportError` with actionable guidance. Prefer this only for
    generation-zero seeding; genetics drive later generations.
    """

    scramble: bool = True
    _engine: Any = field(default=None, init=False, repr=False, compare=False)
    _ndim: int = field(default=0, init=False, repr=False, compare=False)

    def sample(self, space: SearchSpace, rng: random.Random) -> Variant:
        ndim = len(space.dimensions)
        if self._engine is None or self._ndim != ndim:
            try:
                from scipy.stats import qmc
            except ImportError as exc:  # pragma: no cover - env dependent
                raise ImportError(
                    "SobolSampler requires scipy; install the optional dependency "
                    "or use RandomSampler."
                ) from exc
            # Seed the Sobol engine from the shared rng so runs stay reproducible.
            self._engine = qmc.Sobol(d=ndim, scramble=self.scramble, seed=rng.randrange(2**32))
            self._ndim = ndim
        point = self._engine.random(1)[0]
        return Variant(
            {
                dim.name: _value_from_unit(dim, float(u))
                for dim, u in zip(space.dimensions, point, strict=True)
            }
        )


# ---------------------------------------------------------------------------
# Genetics
# ---------------------------------------------------------------------------


def seed_generation_zero(
    space: SearchSpace, sampler: Sampler, *, count: int, rng: random.Random
) -> list[Variant]:
    """Sample the initial population of ``count`` variants."""

    if count <= 0:
        raise ValueError("count must be positive")
    return [sampler.sample(space, rng) for _ in range(count)]


def mutate(
    variant: Variant, space: SearchSpace, rng: random.Random, *, rate: float = 0.1
) -> Variant:
    """Resample each dimension independently with probability ``rate``.

    Resampling (rather than perturbing) keeps the operator domain-free: it works
    identically for numeric, boolean, and categorical dimensions without any
    per-kind step-size tuning.
    """

    if not 0.0 <= rate <= 1.0:
        raise ValueError("rate must be in [0, 1]")
    params = dict(variant.params)
    for dim in space.dimensions:
        if rng.random() < rate:
            params[dim.name] = _sample_value(dim, rng)
    return Variant(params)


def crossover(a: Variant, b: Variant, space: SearchSpace, rng: random.Random) -> Variant:
    """Uniform crossover: inherit each dimension from parent ``a`` or ``b``."""

    params: dict[str, Any] = {}
    for dim in space.dimensions:
        source = a if rng.random() < 0.5 else b
        params[dim.name] = source.params[dim.name]
    return Variant(params)


def breed_generation(
    elites: Sequence[Variant],
    space: SearchSpace,
    sampler: Sampler,
    rng: random.Random,
    *,
    size: int,
    mutation_rate: float = 0.1,
    elite_carryover: int = 0,
) -> list[Variant]:
    """Build the next generation of ``size`` variants from the elite band.

    The first ``elite_carryover`` elites survive unchanged (elitism). The rest
    are bred by crossing two random elites and mutating the child. With fewer
    than two elites, offspring are mutations of the sole elite; with none, the
    generation is freshly sampled (a cold restart).
    """

    if size <= 0:
        raise ValueError("size must be positive")
    if elite_carryover < 0:
        raise ValueError("elite_carryover must be >= 0")

    if not elites:
        return seed_generation_zero(space, sampler, count=size, rng=rng)

    generation: list[Variant] = list(elites[: min(elite_carryover, size)])
    while len(generation) < size:
        if len(elites) >= 2:
            parent_a = elites[rng.randrange(len(elites))]
            parent_b = elites[rng.randrange(len(elites))]
            child = crossover(parent_a, parent_b, space, rng)
        else:
            child = elites[0]
        generation.append(mutate(child, space, rng, rate=mutation_rate))
    return generation


# ---------------------------------------------------------------------------
# Sharding and shard evaluation
# ---------------------------------------------------------------------------


def partition_variants(variants: Sequence[Variant], num_shards: int) -> list[list[Variant]]:
    """Split variants into ``num_shards`` balanced, deterministic shards.

    Round-robin assignment keeps shard sizes within one of each other regardless
    of population size, so a process pool sees evenly weighted work. Empty
    shards are dropped from the tail when there are fewer variants than shards.
    """

    if num_shards <= 0:
        raise ValueError("num_shards must be positive")
    shards: list[list[Variant]] = [[] for _ in range(num_shards)]
    for index, variant in enumerate(variants):
        shards[index % num_shards].append(variant)
    return [shard for shard in shards if shard]


def run_shard(
    variants: Sequence[Variant],
    evaluate: EvaluationFn,
    context: EvalContext,
) -> list[VariantRecord]:
    """Evaluate every variant in one shard and return their records.

    Pure and side-effect free given a deterministic ``evaluate``: it takes only
    its inputs and returns records, which makes it safe to hand to a process
    pool worker (each worker calls ``run_shard`` on its shard, the parent merges
    with :func:`merge_shard_records`).
    """

    records: list[VariantRecord] = []
    for variant in variants:
        result = evaluate(variant, context)
        records.append(
            _record_from_result(
                result,
                params=variant.params,
                generation=context.generation,
                fidelity_level=context.fidelity.level,
            )
        )
    return records


def process_pool_map(
    func: Callable[[_T], _R],
    items: Iterable[_T],
    *,
    max_workers: int | None = None,
) -> list[_R]:
    """Map ``func`` over ``items`` in a :class:`ProcessPoolExecutor`.

    Drop-in for :attr:`Racer.map_fn` when shard evaluation is CPU-bound. ``func``
    and every item must be picklable (module-level callables; no lambdas). For
    a race, prefer a module-level worker that unpacks ``(variants, evaluate,
    context)`` and calls :func:`run_shard`, then pass that worker here.
    """

    materialised = list(items)
    if not materialised:
        return []
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(func, materialised))


# ---------------------------------------------------------------------------
# Stop policy and orchestration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StopDecision:
    """Whether the race should stop, and why."""

    stop: bool
    reason: str


@dataclass(frozen=True)
class StopPolicy:
    """Bounds a race by generation count, wall-clock deadline, or target fitness."""

    max_generations: int
    deadline: datetime | None = None
    target_share: float | None = None

    def __post_init__(self) -> None:
        if self.max_generations <= 0:
            raise ValueError("max_generations must be positive")
        if self.target_share is not None and not 0.0 <= self.target_share <= 1.0:
            raise ValueError("target_share must be in [0, 1]")

    def decide(self, *, generation: int, best_share: float | None, now: datetime) -> StopDecision:
        """Decide after completing ``generation`` (zero-based) whether to stop."""

        if self.target_share is not None and best_share is not None:
            if best_share >= self.target_share:
                return StopDecision(True, "target_share_reached")
        if self.deadline is not None and now >= self.deadline:
            return StopDecision(True, "deadline_reached")
        if generation + 1 >= self.max_generations:
            return StopDecision(True, "max_generations_reached")
        return StopDecision(False, "continue")


@dataclass(frozen=True)
class RaceResult:
    """The outcome of a completed :class:`Racer` run."""

    generations: int
    stop_reason: str
    best: VariantRecord | None
    final_records: tuple[VariantRecord, ...]
    history: tuple[tuple[VariantRecord, ...], ...]


@dataclass
class Racer:
    """Orchestrates the evolutionary race across generations.

    The caller supplies the search space, the application's :data:`EvaluationFn`,
    and a :class:`StopPolicy`. Each generation:

    1. partitions the population into shards (:func:`partition_variants`),
    2. evaluates each shard (:func:`run_shard`) via ``map_fn`` -- swap in a
       process pool's ``map`` here for parallelism; the default is sequential,
    3. merges the shard records (:func:`merge_shard_records`),
    4. optionally persists them (:func:`write_records`),
    5. selects the elite band (:func:`select_elite`) and breeds the next
       generation (:func:`breed_generation`).

    Determinism: given the same ``seed``, a deterministic ``evaluate``, and a
    fixed ``clock``, a run reproduces exactly (identical records and ids).
    """

    space: SearchSpace
    evaluate: EvaluationFn
    clock: Callable[[], datetime]
    sampler: Sampler = field(default_factory=RandomSampler)
    population_size: int = 32
    elite_quantile: float = 0.25
    mutation_rate: float = 0.1
    elite_carryover: int = 1
    num_shards: int = 1
    fidelity_schedule: Sequence[Fidelity] = field(default_factory=lambda: (Fidelity(level=0),))
    # map_fn mirrors ``builtins.map`` / ``Pool.map``: swap in a process pool to
    # fan shard evaluation out across cores. Kept injectable so the engine has
    # no hard dependency on ``multiprocessing``.
    map_fn: Callable[..., Iterable[Any]] = map
    records_dir: Path | None = None

    def _fidelity_for(self, generation: int) -> Fidelity:
        if not self.fidelity_schedule:
            return Fidelity(level=0)
        index = min(generation, len(self.fidelity_schedule) - 1)
        return self.fidelity_schedule[index]

    def run(self, *, seed: int, stop: StopPolicy) -> RaceResult:
        rng = random.Random(seed)
        population = seed_generation_zero(
            self.space, self.sampler, count=self.population_size, rng=rng
        )

        history: list[tuple[VariantRecord, ...]] = []
        best: VariantRecord | None = None
        stop_reason = "continue"
        generation = 0

        while True:
            fidelity = self._fidelity_for(generation)
            # Deterministic per-generation evaluation seed independent of the
            # breeding rng, so an app's own randomness is reproducible per rung.
            eval_seed = (seed * 1_000_003 + generation) & 0x7FFF_FFFF
            context = EvalContext(
                fidelity=fidelity,
                seed=eval_seed,
                generation=generation,
                now=self.clock(),
                cache_dir=self.records_dir,  # predict-cache hook: reuse as root
            )

            shards = partition_variants(population, self.num_shards)
            evaluate = self.evaluate
            shard_records = list(
                self.map_fn(
                    lambda shard, _evaluate=evaluate, _context=context: run_shard(
                        shard, _evaluate, _context
                    ),
                    shards,
                )
            )
            records = merge_shard_records(shard_records)
            history.append(tuple(records))

            if records and (
                best is None or records[0].win_or_close_share > best.win_or_close_share
            ):
                best = records[0]

            if self.records_dir is not None:
                write_records(Path(self.records_dir) / f"generation-{generation:04d}.json", records)

            best_share = best.win_or_close_share if best is not None else None
            decision = stop.decide(generation=generation, best_share=best_share, now=self.clock())
            if decision.stop:
                stop_reason = decision.reason
                break

            elites = [
                record.variant for record in select_elite(records, quantile=self.elite_quantile)
            ]
            population = breed_generation(
                elites,
                self.space,
                self.sampler,
                rng,
                size=self.population_size,
                mutation_rate=self.mutation_rate,
                elite_carryover=self.elite_carryover,
            )
            generation += 1

        return RaceResult(
            generations=generation + 1,
            stop_reason=stop_reason,
            best=best,
            final_records=history[-1] if history else (),
            history=tuple(history),
        )


def _replace_fidelity(context: EvalContext, fidelity: Fidelity) -> EvalContext:
    """Return a copy of *context* at a different fidelity (helper for apps)."""

    return replace(context, fidelity=fidelity)

"""Walk-forward backtest of the actual production prediction pipeline (#280).

This replays what ``nfl_oracle.recommendations.cli._model_bundle`` and
``RecommendationPipeline.prepare`` do in production, slate by slate, against
finalized Corpus G outcomes:

1. ``fit_model`` over ``attach_enrichment(rows, enrich_historical_rows(...))``
   after ``drop_ambiguous_identity_rows``, exactly as ``_model_bundle`` does,
   but trained only on rows whose label was final strictly before the fold's
   cutoff.
2. ``predict`` with per-candidate ``ContextAdjustment`` built from the target
   row's own walk-forward context features (the historical analogue of
   ``build_context``).
3. The production ``optimize`` (exact MILP when scipy is present) with the
   production ``ScoringPolicy`` and ``OptimizerConfig`` diversity rules.

The committed lineup's realized score is compared with the hindsight-best
lineup over the same candidate pool, under the same slot structure and the
zero-boost scoring law, giving a capture ratio comparable to
``nfl_oracle.replay.backtest`` (naive EWMA baseline) and to the Corpus C field
numbers in ``nfl_oracle.replay.harness``.

Clock handling, load-bearing. Every Corpus G row carries a ``captured_at``
from the retrospective backfill, and the nflverse context snapshot carries
today's capture clock. The production clock contracts (``fit_model``'s
``future_training_label``/``future_context_evidence``, ``predict``'s history
filter, ``Slate.assert_prelock``) therefore cannot be satisfied by pretending
the decision happened in 2024. The harness instead walks forward in DATA:
``trained_at``/``decision_at`` are the real wall clock, and every row the
model or the prior bank sees is filtered to ``available_at < cutoff`` for the
backtested slate. :func:`assert_no_leakage` re-checks that filter and raises
:class:`LeakageError` if it is ever violated. Slate objects carry a synthetic
future kickoff only so the live prelock contract passes; they are never used
as a data cutoff. Context features are ``retrospective_reconstructed``
(nflverse releases can revise past weekly stats), not prospective evidence.

Read-only research: no provider calls, no contest entry, no store writes.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from statistics import mean, median
from typing import Literal
from zoneinfo import ZoneInfo

from nfl_oracle.recommendations.model import (
    ContextAdjustment,
    FitConfig,
    HistoricalPerformance,
    Projection,
    RatingModel,
    drop_ambiguous_identity_rows,
    fit_model,
    predict,
)
from nfl_oracle.recommendations.optimizer import (
    OptimizerConfig,
    ScoringPolicy,
    optimize,
)
from nfl_oracle.recommendations.schema import (
    Candidate,
    Contest,
    EvidenceClock,
    Game,
    Slate,
    utc,
)
from nfl_oracle.valuelaw.project import ewma

SLOT_MULTIPLIERS: tuple[float, float, float, float, float] = (2.0, 1.8, 1.6, 1.4, 1.2)
EASTERN = ZoneInfo("America/New_York")
SlateGrouping = Literal["game", "day"]
# Fits and predicts through the real production functions. Tests may swap the
# fitter to exercise failure paths; the CLI never does.
Fitter = Callable[[Sequence[HistoricalPerformance], datetime, FitConfig], RatingModel]


class LeakageError(ValueError):
    """A training or prior-bank row was not final strictly before the slate cutoff."""


@dataclass(frozen=True)
class SlateBacktestResult:
    slate_key: str
    game_ids: tuple[int, ...]
    cutoff: datetime
    fold: str
    training_rows: int
    selected_estimator: str
    candidate_count: int
    predicted_player_ids: tuple[int, ...]
    hindsight_player_ids: tuple[int, ...]
    committed_score: float
    hindsight_score: float
    capture_ratio: float
    projected_total_value: float
    diversity_relaxed: bool
    # Paired naive EWMA baseline (same slate, same pool, same slots) so the
    # production number is compared on identical games, not a different sample.
    naive_capture_ratio: float | None = None


@dataclass(frozen=True)
class ProductionBacktestSummary:
    n_slates: int
    mean_capture_ratio: float | None
    median_capture_ratio: float | None
    min_capture_ratio: float | None
    max_capture_ratio: float | None
    mean_committed_score: float | None
    mean_hindsight_score: float | None
    mean_naive_capture_ratio: float | None = None
    median_naive_capture_ratio: float | None = None
    slates_production_beats_naive: int | None = None
    excluded: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class _SlateSpec:
    key: str
    rows: tuple[HistoricalPerformance, ...]

    @property
    def cutoff(self) -> datetime:
        return min(row.kickoff_at for row in self.rows)

    @property
    def game_ids(self) -> tuple[int, ...]:
        return tuple(sorted({row.game_id for row in self.rows}))


def assert_no_leakage(
    rows: Iterable[HistoricalPerformance],
    *,
    cutoff: datetime,
    slate_game_ids: Iterable[int],
) -> None:
    """Refuse any row whose label or kickoff is not strictly before ``cutoff``."""
    boundary = utc(cutoff)
    games = set(slate_game_ids)
    for row in rows:
        if row.game_id in games:
            raise LeakageError("slate_game_in_training")
        if row.available_at >= boundary or row.kickoff_at >= boundary:
            raise LeakageError("future_label_in_training")


def rows_before(
    rows: Iterable[HistoricalPerformance],
    *,
    cutoff: datetime,
    exclude_game_ids: Iterable[int] = (),
) -> tuple[HistoricalPerformance, ...]:
    """Rows whose label was final strictly before ``cutoff`` (walk-forward filter)."""
    boundary = utc(cutoff)
    games = set(exclude_game_ids)
    return tuple(
        row
        for row in rows
        if row.available_at < boundary and row.kickoff_at < boundary and row.game_id not in games
    )


def hindsight_best(
    values: Mapping[int, float], slots: Sequence[float]
) -> tuple[tuple[int, ...], float]:
    """Best zero-boost lineup: top-five realized values in descending slot order.

    With every boost zero, ``sum(value * slot)`` over any five players is
    maximized by the five largest values assigned in descending order
    (rearrangement inequality), which is what
    :func:`nfl_oracle.replay.harness.hindsight_best_lineup` reduces to here.
    """
    ranked = sorted(values.items(), key=lambda item: (-item[1], item[0]))[: len(slots)]
    ids = tuple(player_id for player_id, _ in ranked)
    score = sum(value * slot for (_, value), slot in zip(ranked, slots, strict=True))
    return ids, score


def _slate_key(row: HistoricalPerformance, grouping: SlateGrouping) -> str:
    if grouping == "game":
        return f"game:{row.game_id}"
    return f"day:{row.kickoff_at.astimezone(EASTERN).date().isoformat()}"


def group_slates(
    rows: Iterable[HistoricalPerformance], grouping: SlateGrouping
) -> list[_SlateSpec]:
    grouped: dict[str, list[HistoricalPerformance]] = defaultdict(list)
    for row in rows:
        grouped[_slate_key(row, grouping)].append(row)
    specs = [_SlateSpec(key=key, rows=tuple(value)) for key, value in grouped.items()]
    return sorted(specs, key=lambda spec: (spec.cutoff, spec.key))


def build_slate(
    rows: Sequence[HistoricalPerformance],
    *,
    now: datetime,
    team_keys: Mapping[int, str] | None = None,
    card_boosts: Mapping[int, float] | None = None,
    slot_multipliers: tuple[float, float, float, float, float] = SLOT_MULTIPLIERS,
) -> Slate:
    """A live-contract ``Slate`` for a historical set of games.

    Candidates are the players who actually took the field (``did_not_play``
    rows are excluded: the live pool is built after inactives are known and a
    DNP scores zero). Every clock is ``now`` and every kickoff is one hour in
    the future purely so ``assert_prelock`` passes; see the module docstring.
    ``card_boosts`` carries a replayed contest's own per-player boosts (the
    Corpus C contest-pool replay); absent players, and the default, are zero.
    """
    now = utc(now)
    clock = EvidenceClock(source_available_at=now, captured_at=now)
    keys = team_keys or {}
    teams_by_game: dict[int, set[int]] = defaultdict(set)
    for row in rows:
        if row.team_id is None or row.opponent_team_id is None:
            raise ValueError("historical_row_missing_team")
        teams_by_game[row.game_id].update({row.team_id, row.opponent_team_id})
    games = []
    for game_id, teams in sorted(teams_by_game.items()):
        if len(teams) != 2:
            raise ValueError("historical_game_team_count")
        home, away = sorted(teams)
        games.append(
            Game(
                game_id=game_id,
                season=0,
                kickoff_at=now + timedelta(hours=1),
                home_team_id=home,
                away_team_id=away,
                home_team=keys.get(home, str(home)),
                away_team=keys.get(away, str(away)),
                status="scheduled",
            )
        )
    candidates = tuple(
        Candidate(
            player_id=row.player_id,
            game_id=row.game_id,
            team_id=row.team_id or 0,
            name=str(row.player_id),
            position=row.position,
            team=keys.get(row.team_id or 0, str(row.team_id)),
            opponent=keys.get(row.opponent_team_id or 0, str(row.opponent_team_id)),
            injury_status=None,
            card_boost=(card_boosts or {}).get(row.player_id, 0.0),
            clock=clock,
        )
        for row in sorted(rows, key=lambda r: (r.game_id, r.player_id))
        if not row.did_not_play
    )
    nonzero_boosts = [c.card_boost for c in candidates if c.card_boost > 0]
    return Slate(
        contest=Contest(
            contest_id=1,
            day=now.date(),
            end_day=now.date(),
            slot_multipliers=slot_multipliers,
            is_locked=False,
            is_finalized=False,
            clock=clock,
            evidence_sha256="retrospective_production_backtest",
        ),
        games=tuple(games),
        candidates=candidates,
        captured_at=now,
        source_hashes=(),
        pool_roster_count=len(candidates),
        pool_search_matched_count=len(candidates),
        pool_complete=True,
        boost_regime="zero_boost" if not nonzero_boosts else "provider_boosts_present",
        boost_nonzero_count=len(nonzero_boosts),
        boost_max=max(nonzero_boosts, default=0.0),
    )


def compact_projections(projections: Sequence[Projection]) -> tuple[Projection, ...]:
    """Replace each residual sample vector with its own mean.

    ``optimize`` selects the lineup from ``mean(score(v) for v in samples)``,
    which is linear in ``v``, so a one-element sample equal to the sample mean
    gives the identical objective and the identical lineup. The Monte Carlo
    p90/field-win diagnostics (which never reassign the lineup) become
    degenerate, which is why this is used only for speed and is tested for
    selection equivalence.
    """
    return tuple(
        projection.model_copy(update={"samples": (mean(projection.samples),)})
        for projection in projections
    )


def naive_ewma_projections(
    playing: Sequence[HistoricalPerformance],
    history: Sequence[HistoricalPerformance],
    *,
    min_player_games: int = 3,
    decay: float = 0.9,
) -> dict[int, float]:
    """The ``nfl_oracle.replay.backtest`` EWMA-plus-position-prior projection.

    Uses only ``history`` (already filtered to final-before-cutoff rows), so it
    is leakage-safe by the same guard as the production replay. Players with
    neither enough own history nor a position prior are left out.
    """
    by_player: dict[int, list[HistoricalPerformance]] = defaultdict(list)
    by_position: dict[str, list[float]] = defaultdict(list)
    for row in sorted(history, key=lambda r: r.kickoff_at):
        if row.did_not_play:
            continue
        by_player[row.player_id].append(row)
        by_position[row.position].append(row.value)
    projected: dict[int, float] = {}
    for row in playing:
        prior = by_player.get(row.player_id, [])
        if len(prior) >= min_player_games:
            projected[row.player_id] = ewma(tuple(r.value for r in prior), decay=decay)
        else:
            samples = by_position.get(row.position)
            if samples:
                projected[row.player_id] = mean(samples)
    return projected


def naive_ewma_capture(
    playing: Sequence[HistoricalPerformance],
    history: Sequence[HistoricalPerformance],
    *,
    min_player_games: int = 3,
    decay: float = 0.9,
) -> float | None:
    """Zero-boost capture of the :func:`naive_ewma_projections` top five on this pool."""
    projected = naive_ewma_projections(
        playing, history, min_player_games=min_player_games, decay=decay
    )
    if len(projected) < len(SLOT_MULTIPLIERS):
        return None
    chosen = sorted(projected.items(), key=lambda item: (-item[1], item[0]))[
        : len(SLOT_MULTIPLIERS)
    ]
    actual = {row.player_id: row.value for row in playing}
    committed = sum(
        actual[player_id] * slot
        for (player_id, _projection), slot in zip(chosen, SLOT_MULTIPLIERS, strict=True)
    )
    _ids, best = hindsight_best(actual, SLOT_MULTIPLIERS)
    return committed / best if best > 0 else None


def _production_fit(
    rows: Sequence[HistoricalPerformance], trained_at: datetime, fit_config: FitConfig
) -> RatingModel:
    return fit_model(rows, trained_at=trained_at, fit_config=fit_config)


def _default_fold(spec: _SlateSpec) -> str:
    return spec.key


def backtest_production_pipeline(
    rows: Sequence[HistoricalPerformance],
    *,
    grouping: SlateGrouping = "game",
    fold_of: Callable[[_SlateSpec], Hashable] | None = None,
    now: datetime | None = None,
    team_keys: Mapping[int, str] | None = None,
    optimizer_config: OptimizerConfig | None = None,
    fit_config: FitConfig | None = None,
    compact_samples: bool = True,
    fitter: Fitter = _production_fit,
    progress: Callable[[str], None] | None = None,
) -> tuple[tuple[SlateBacktestResult, ...], dict[str, int]]:
    """Walk-forward replay of fit/predict/optimize over enriched history rows.

    ``rows`` must already be the enriched production training set
    (``attach_enrichment`` output). ``fold_of`` groups slates that share one
    retrain; the fold's model is trained on rows final before the fold's
    earliest slate cutoff, while each slate's prior bank uses every row final
    before that slate's own cutoff. The default is one retrain per slate.
    """
    clock_now = utc(now or datetime.now(UTC))
    cfg = optimizer_config or OptimizerConfig(simulations=100)
    model_fit_config = fit_config or FitConfig()
    fold_key = fold_of or _default_fold
    specs = group_slates(rows, grouping)
    folds: dict[Hashable, list[_SlateSpec]] = defaultdict(list)
    for spec in specs:
        folds[fold_key(spec)].append(spec)
    excluded: dict[str, int] = defaultdict(int)
    results: list[SlateBacktestResult] = []
    for key, fold_specs in sorted(folds.items(), key=lambda item: min(s.cutoff for s in item[1])):
        fold_cutoff = min(spec.cutoff for spec in fold_specs)
        fold_games = {game for spec in fold_specs for game in spec.game_ids}
        train = rows_before(rows, cutoff=fold_cutoff, exclude_game_ids=fold_games)
        train, _audit = drop_ambiguous_identity_rows(train)
        assert_no_leakage(train, cutoff=fold_cutoff, slate_game_ids=fold_games)
        try:
            model = fitter(train, clock_now, model_fit_config)
        except ValueError as error:
            if isinstance(error, LeakageError):
                raise
            excluded[f"fit:{error}"] += len(fold_specs)
            continue
        for spec in fold_specs:
            result = _run_slate(
                spec,
                rows=rows,
                model=model,
                fold=str(key),
                training_rows=len(train),
                now=clock_now,
                team_keys=team_keys,
                config=cfg,
                compact_samples=compact_samples,
                excluded=excluded,
            )
            if result is not None:
                results.append(result)
                if progress is not None:
                    progress(f"{spec.key} capture={result.capture_ratio:.3f}")
    return tuple(results), dict(excluded)


def _run_slate(
    spec: _SlateSpec,
    *,
    rows: Sequence[HistoricalPerformance],
    model: RatingModel,
    fold: str,
    training_rows: int,
    now: datetime,
    team_keys: Mapping[int, str] | None,
    config: OptimizerConfig,
    compact_samples: bool,
    excluded: dict[str, int],
) -> SlateBacktestResult | None:
    history = rows_before(rows, cutoff=spec.cutoff, exclude_game_ids=spec.game_ids)
    history, _audit = drop_ambiguous_identity_rows(history)
    assert_no_leakage(history, cutoff=spec.cutoff, slate_game_ids=spec.game_ids)
    playing = [row for row in spec.rows if not row.did_not_play]
    if len(playing) < 5:
        excluded["fewer_than_five_players"] += 1
        return None
    try:
        slate = build_slate(spec.rows, now=now, team_keys=team_keys)
    except ValueError as error:
        excluded[f"slate:{error}"] += 1
        return None
    clock = EvidenceClock(source_available_at=now, captured_at=now)
    adjustments = {
        row.player_id: ContextAdjustment(
            clock=clock,
            external_id=row.external_id,
            features=dict(row.context_features),
            provenance=(row.context_evidence_mode,),
        )
        for row in playing
    }
    try:
        projections = predict(slate, model, history, decision_at=now, context=adjustments)
    except ValueError as error:
        excluded[f"predict:{error}"] += 1
        return None
    if compact_samples:
        projections = compact_projections(projections)
    try:
        lineup = optimize(
            slate,
            projections,
            decision_at=now,
            scoring_policy=ScoringPolicy(),
            config=config,
        )
    except ValueError as error:
        excluded[f"optimize:{error}"] += 1
        return None
    actual = {row.player_id: row.value for row in playing}
    policy = ScoringPolicy()
    committed = sum(
        policy.score(actual[pick.player_id], pick.slot_multiplier, pick.card_boost)
        for pick in lineup.picks
    )
    hindsight_ids, hindsight_score = hindsight_best(actual, SLOT_MULTIPLIERS)
    if hindsight_score <= 0 or not math.isfinite(hindsight_score):
        excluded["nonpositive_hindsight"] += 1
        return None
    return SlateBacktestResult(
        slate_key=spec.key,
        game_ids=spec.game_ids,
        cutoff=spec.cutoff,
        fold=fold,
        training_rows=training_rows,
        selected_estimator=model.selected_estimator,
        candidate_count=len(slate.candidates),
        predicted_player_ids=tuple(pick.player_id for pick in lineup.picks),
        hindsight_player_ids=hindsight_ids,
        committed_score=committed,
        hindsight_score=hindsight_score,
        capture_ratio=committed / hindsight_score,
        projected_total_value=lineup.total_value,
        diversity_relaxed=lineup.diversity_relaxed,
        naive_capture_ratio=naive_ewma_capture(playing, history),
    )


def summarize(
    results: Sequence[SlateBacktestResult], excluded: Mapping[str, int] | None = None
) -> ProductionBacktestSummary:
    captures = [result.capture_ratio for result in results]
    if not captures:
        return ProductionBacktestSummary(
            n_slates=0,
            mean_capture_ratio=None,
            median_capture_ratio=None,
            min_capture_ratio=None,
            max_capture_ratio=None,
            mean_committed_score=None,
            mean_hindsight_score=None,
            excluded=dict(excluded or {}),
        )
    naive = [r.naive_capture_ratio for r in results if r.naive_capture_ratio is not None]
    paired = [r for r in results if r.naive_capture_ratio is not None]
    return ProductionBacktestSummary(
        n_slates=len(captures),
        mean_naive_capture_ratio=mean(naive) if naive else None,
        median_naive_capture_ratio=median(naive) if naive else None,
        slates_production_beats_naive=sum(
            r.capture_ratio > (r.naive_capture_ratio or 0.0) for r in paired
        ),
        mean_capture_ratio=mean(captures),
        median_capture_ratio=median(captures),
        min_capture_ratio=min(captures),
        max_capture_ratio=max(captures),
        mean_committed_score=mean(result.committed_score for result in results),
        mean_hindsight_score=mean(result.hindsight_score for result in results),
        excluded=dict(excluded or {}),
    )

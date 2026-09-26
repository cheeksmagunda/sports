"""Replay the production pipeline on the pool each Corpus C contest showed (#280).

``nfl_oracle.replay.production_backtest`` scores production against the full
Corpus G game pool with zero boosts. The field numbers in
``nfl_oracle.replay.harness`` use a different denominator: the contest's own
visible pool, under that contest's own card boosts. This module closes that
gap so production and the visible winner are measured on identical terms:

1. The candidate pool is the contest's visible draft-stats players, joined to
   Corpus G by Real Sports ``player_id`` on the contest's America/New_York
   day, each carrying the contest's own ``card_boost``.
2. Production ``fit_model``/``predict``/``optimize`` run exactly as in
   :mod:`nfl_oracle.replay.production_backtest`, walk-forward, trained and
   primed only on rows final strictly before the day's first kickoff
   (:func:`~nfl_oracle.replay.production_backtest.assert_no_leakage`).
3. Every lineup is scored with the contest's own finalized values (the
   leaderboard's scoring input), against the same boost-aware ceiling
   (:func:`~nfl_oracle.replay.harness.hindsight_best_lineup`) the winner's
   capture uses.

It also splits production's shortfall into selection and ordering:
``ordered_capture`` re-slots production's own five cards by their realized
values, so ``1 - ordered_capture`` is lost to choosing the wrong players and
``ordered_capture - capture`` is lost to slot order alone.

Honesty boundary, inherited from the harness: only the top twenty entries are
visible. ``beats_visible_entries`` counts visible entries production's score
exceeds; it is never a percentile of the full field. Pool players with no
Corpus G row that day (all scored zero in the local archive) are dropped from
 the candidate pool and counted, which is slightly generous to production.

Read-only research: no provider calls, no contest entry, no store writes.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from statistics import mean, median
from zoneinfo import ZoneInfo

from nfl_oracle.contests.boosts import slot_multiplier_for
from nfl_oracle.contests.parse import ParsedContest
from nfl_oracle.recommendations.model import (
    ContextAdjustment,
    FitConfig,
    HistoricalPerformance,
    RatingModel,
    drop_ambiguous_identity_rows,
    predict,
)
from nfl_oracle.recommendations.optimizer import (
    OptimizerConfig,
    ScoringPolicy,
    optimize,
)
from nfl_oracle.recommendations.picker_knobs import (
    PickerKnobs,
    apply_picker_knobs,
)
from nfl_oracle.recommendations.schema import EvidenceClock, utc
from nfl_oracle.replay.harness import (
    best_lineup,
    eligible_pool_values,
    replay_contest,
)
from nfl_oracle.replay.production_backtest import (
    Fitter,
    LeakageError,
    _production_fit,
    assert_no_leakage,
    build_slate,
    compact_projections,
    naive_ewma_projections,
    rows_before,
)

EASTERN = ZoneInfo("America/New_York")
# Corpus C and Corpus G can disagree by float noise on a shared player; count
# only disagreements a leaderboard would notice.
VALUE_MISMATCH_TOLERANCE = 0.05


@dataclass(frozen=True)
class ContestPool:
    """One contest's visible pool joined to that day's Corpus G rows."""

    contest: ParsedContest
    rows: tuple[HistoricalPerformance, ...]
    day_game_ids: tuple[int, ...]
    cutoff: datetime
    missing_player_ids: tuple[int, ...]

    @property
    def contest_id(self) -> int:
        return self.contest.contest.contest_id

    @property
    def game_ids(self) -> tuple[int, ...]:
        return tuple(sorted({row.game_id for row in self.rows}))


@dataclass(frozen=True)
class ContestPoolResult:
    contest_id: int
    day: date
    is_zero_boost: bool
    law_verified: bool
    entrants: int
    fold: str
    game_ids: tuple[int, ...]
    visible_pool_size: int
    candidate_count: int
    pool_missing_from_history: int
    value_mismatches: int
    ceiling_score: float
    hindsight_player_ids: tuple[int, ...]
    production_player_ids: tuple[int, ...]
    production_score: float
    capture_ratio: float
    ordered_capture_ratio: float
    hindsight_overlap: int
    winner_score: float | None
    winner_capture_ratio: float | None
    winner_player_ids: tuple[int, ...]
    winner_overlap: int | None
    beats_winner: bool | None
    beats_visible_entries: int
    visible_entries: int
    diversity_relaxed: bool
    naive_capture_ratio: float | None = None
    picker_profile: str = "identity"


@dataclass(frozen=True)
class RegimeSummary:
    n_contests: int
    mean_capture_ratio: float | None
    median_capture_ratio: float | None
    mean_ordered_capture_ratio: float | None
    mean_winner_capture_ratio: float | None
    mean_naive_capture_ratio: float | None
    mean_hindsight_overlap: float | None
    contests_beating_winner: int
    mean_visible_entries_beaten: float | None


@dataclass(frozen=True)
class ContestPoolSummary:
    all: RegimeSummary
    zero_boost: RegimeSummary
    boosted: RegimeSummary
    excluded: dict[str, int] = field(default_factory=dict)


def rows_by_eastern_day(
    rows: Iterable[HistoricalPerformance],
) -> dict[date, tuple[HistoricalPerformance, ...]]:
    grouped: dict[date, list[HistoricalPerformance]] = defaultdict(list)
    for row in rows:
        grouped[row.kickoff_at.astimezone(EASTERN).date()].append(row)
    return {day: tuple(value) for day, value in grouped.items()}


def join_contest_pool(
    contest: ParsedContest,
    day_rows: Sequence[HistoricalPerformance],
) -> ContestPool | None:
    """Restrict one ET day's Corpus G rows to this contest's visible pool.

    The cutoff is the day's first kickoff across every Corpus G game that day,
    and every one of those games is excluded from training, which is
    conservative when a contest covers only part of the day.
    """
    if not day_rows:
        return None
    pool_ids = {row.player_id for row in contest.draft_stats}
    joined = tuple(row for row in day_rows if row.player_id in pool_ids)
    if not joined:
        return None
    present = {row.player_id for row in joined}
    return ContestPool(
        contest=contest,
        rows=joined,
        day_game_ids=tuple(sorted({row.game_id for row in day_rows})),
        cutoff=min(row.kickoff_at for row in day_rows),
        missing_player_ids=tuple(sorted(pool_ids - present)),
    )


def _slots(contest: ParsedContest) -> tuple[float, float, float, float, float] | None:
    """The contest's five slot multipliers, or None for any other lineup size.

    The production ``Contest`` schema is five cards; a contest of another size
    is excluded visibly rather than squeezed into that shape.
    """
    record = contest.contest
    if record.lineup_size != 5:
        return None
    one, two, three, four, five = (
        slot_multiplier_for(slot, record.slot_multipliers) for slot in range(1, 6)
    )
    return (one, two, three, four, five)


def _default_fold(pool: ContestPool) -> Hashable:
    return pool.contest_id


def replay_contest_pools(
    rows: Sequence[HistoricalPerformance],
    contests: Iterable[ParsedContest],
    *,
    fold_of: Callable[[ContestPool], Hashable] | None = None,
    now: datetime | None = None,
    team_keys: Mapping[int, str] | None = None,
    optimizer_config: OptimizerConfig | None = None,
    fit_config: FitConfig | None = None,
    compact_samples: bool = True,
    fitter: Fitter = _production_fit,
    picker: PickerKnobs | None = None,
    progress: Callable[[str], None] | None = None,
) -> tuple[tuple[ContestPoolResult, ...], dict[str, int]]:
    """Walk-forward production replay restricted to each contest's visible pool.

    ``rows`` is the enriched production training set (``attach_enrichment``
    output) over all of Corpus G, not only pool players. ``fold_of`` groups
    contests that share one retrain, trained on rows final before the fold's
    earliest cutoff; each contest's prior bank uses rows final before its own.
    """
    clock_now = utc(now or datetime.now(UTC))
    cfg = optimizer_config or OptimizerConfig(simulations=100)
    model_fit_config = fit_config or FitConfig()
    knobs = picker or PickerKnobs()
    fold_key = fold_of or _default_fold
    by_day = rows_by_eastern_day(rows)
    excluded: dict[str, int] = defaultdict(int)
    pools: list[ContestPool] = []
    for contest in contests:
        if not contest.draft_stats:
            excluded["no_draft_stats"] += 1
            continue
        pool = join_contest_pool(contest, by_day.get(contest.contest.day, ()))
        if pool is None:
            excluded["no_corpus_g_rows_for_day"] += 1
            continue
        pools.append(pool)
    folds: dict[Hashable, list[ContestPool]] = defaultdict(list)
    for pool in pools:
        folds[fold_key(pool)].append(pool)
    results: list[ContestPoolResult] = []
    for key, fold_pools in sorted(folds.items(), key=lambda item: min(p.cutoff for p in item[1])):
        fold_cutoff = min(pool.cutoff for pool in fold_pools)
        fold_games = {game for pool in fold_pools for game in pool.day_game_ids}
        train = rows_before(rows, cutoff=fold_cutoff, exclude_game_ids=fold_games)
        train, _audit = drop_ambiguous_identity_rows(train)
        assert_no_leakage(train, cutoff=fold_cutoff, slate_game_ids=fold_games)
        try:
            model = fitter(train, clock_now, model_fit_config)
        except ValueError as error:
            if isinstance(error, LeakageError):
                raise
            excluded[f"fit:{error}"] += len(fold_pools)
            continue
        for pool in sorted(fold_pools, key=lambda p: (p.cutoff, p.contest_id)):
            result = _run_contest(
                pool,
                rows=rows,
                model=model,
                fold=str(key),
                now=clock_now,
                team_keys=team_keys,
                config=cfg,
                compact_samples=compact_samples,
                picker=knobs,
                excluded=excluded,
            )
            if result is not None:
                results.append(result)
                if progress is not None:
                    progress(f"contest:{pool.contest_id} capture={result.capture_ratio:.3f}")
    return tuple(results), dict(excluded)


def _run_contest(
    pool: ContestPool,
    *,
    rows: Sequence[HistoricalPerformance],
    model: RatingModel,
    fold: str,
    now: datetime,
    team_keys: Mapping[int, str] | None,
    config: OptimizerConfig,
    compact_samples: bool,
    picker: PickerKnobs,
    excluded: dict[str, int],
) -> ContestPoolResult | None:
    contest = pool.contest
    history = rows_before(rows, cutoff=pool.cutoff, exclude_game_ids=pool.day_game_ids)
    history, _audit = drop_ambiguous_identity_rows(history)
    assert_no_leakage(history, cutoff=pool.cutoff, slate_game_ids=pool.day_game_ids)
    slots = _slots(contest)
    if slots is None:
        excluded["unsupported_lineup_size"] += 1
        return None
    playing = [row for row in pool.rows if not row.did_not_play]
    if len(playing) < len(slots):
        excluded["fewer_than_lineup_size_players"] += 1
        return None
    boosts = contest.boost_table()
    try:
        slate = build_slate(
            pool.rows,
            now=now,
            team_keys=team_keys,
            card_boosts=boosts,
            slot_multipliers=slots,
        )
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
    projections = apply_picker_knobs(
        projections,
        slate,
        knobs=picker,
        position_bias=model.position_residual_bias,
    )
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

    # Score with the contest's own finalized values; Corpus G fills only a
    # value the contest did not reveal.
    contest_values = eligible_pool_values(contest)
    actual = {row.player_id: contest_values.get(row.player_id, row.value) for row in playing}
    mismatches = sum(
        1
        for row in playing
        if row.player_id in contest_values
        and abs(contest_values[row.player_id] - row.value) > VALUE_MISMATCH_TOLERANCE
    )
    replay = replay_contest(contest)
    if replay.hindsight_best is None or replay.hindsight_best.total_score <= 0:
        excluded["nonpositive_ceiling"] += 1
        return None
    ceiling = replay.hindsight_best.total_score
    policy = ScoringPolicy()
    committed = sum(
        policy.score(actual[pick.player_id], pick.slot_multiplier, pick.card_boost)
        for pick in lineup.picks
    )
    chosen = tuple(pick.player_id for pick in lineup.picks)
    ordered = best_lineup({pid: actual[pid] for pid in chosen}, boosts, slots)
    ordered_score = ordered.total_score if ordered is not None else committed

    naive_projection = naive_ewma_projections(playing, history)
    naive_capture: float | None = None
    naive_pick = best_lineup(naive_projection, boosts, slots)
    if naive_pick is not None:
        # best_lineup returns picks in slot order (descending projected value).
        naive_score = sum(
            policy.score(actual[pid], slot, boosts.get(pid, 0.0))
            for pid, slot in zip(naive_pick.player_ids, slots, strict=True)
        )
        naive_capture = naive_score / ceiling

    winner = next((entry for entry in contest.entries if entry.rank == 1), None)
    winner_ids = tuple(pick.player_id for pick in winner.picks) if winner else ()
    visible = [entry.total_from_picks() for entry in contest.entries]
    visible_scores = [score for score in visible if score is not None]
    hindsight_ids = replay.hindsight_best.player_ids
    return ContestPoolResult(
        contest_id=pool.contest_id,
        day=contest.contest.day,
        is_zero_boost=replay.is_zero_boost,
        law_verified=contest.law_verified,
        entrants=contest.contest.entrants,
        fold=fold,
        game_ids=pool.game_ids,
        visible_pool_size=len({row.player_id for row in contest.draft_stats}),
        candidate_count=len(slate.candidates),
        pool_missing_from_history=len(pool.missing_player_ids),
        value_mismatches=mismatches,
        ceiling_score=ceiling,
        hindsight_player_ids=hindsight_ids,
        production_player_ids=chosen,
        production_score=committed,
        capture_ratio=committed / ceiling,
        ordered_capture_ratio=ordered_score / ceiling,
        hindsight_overlap=len(set(chosen) & set(hindsight_ids)),
        winner_score=replay.winner_score,
        winner_capture_ratio=replay.winner_capture_ratio,
        winner_player_ids=winner_ids,
        winner_overlap=len(set(chosen) & set(winner_ids)) if winner else None,
        beats_winner=(committed > replay.winner_score) if replay.winner_score is not None else None,
        beats_visible_entries=sum(committed > score for score in visible_scores),
        visible_entries=len(visible_scores),
        diversity_relaxed=lineup.diversity_relaxed,
        naive_capture_ratio=naive_capture,
        picker_profile=picker.profile,
    )


def _mean(values: Sequence[float]) -> float | None:
    return mean(values) if values else None


def summarize_regime(results: Sequence[ContestPoolResult]) -> RegimeSummary:
    captures = [r.capture_ratio for r in results]
    winners = [r.winner_capture_ratio for r in results if r.winner_capture_ratio is not None]
    naive = [r.naive_capture_ratio for r in results if r.naive_capture_ratio is not None]
    beaten = [r.beats_visible_entries / r.visible_entries for r in results if r.visible_entries]
    return RegimeSummary(
        n_contests=len(results),
        mean_capture_ratio=_mean(captures),
        median_capture_ratio=median(captures) if captures else None,
        mean_ordered_capture_ratio=_mean([r.ordered_capture_ratio for r in results]),
        mean_winner_capture_ratio=_mean(winners),
        mean_naive_capture_ratio=_mean(naive),
        mean_hindsight_overlap=_mean([float(r.hindsight_overlap) for r in results]),
        contests_beating_winner=sum(bool(r.beats_winner) for r in results),
        mean_visible_entries_beaten=_mean(beaten),
    )


def summarize(
    results: Sequence[ContestPoolResult], excluded: Mapping[str, int] | None = None
) -> ContestPoolSummary:
    return ContestPoolSummary(
        all=summarize_regime(results),
        zero_boost=summarize_regime([r for r in results if r.is_zero_boost]),
        boosted=summarize_regime([r for r in results if not r.is_zero_boost]),
        excluded=dict(excluded or {}),
    )


def _merge_excluded_counts(
    shared: Mapping[str, int], per_profile: Mapping[str, int]
) -> dict[str, int]:
    merged: dict[str, int] = dict(shared)
    for reason, count in per_profile.items():
        merged[reason] = merged.get(reason, 0) + count
    return {reason: count for reason, count in merged.items() if count}


def capture_with_picker(
    pool: ContestPool,
    *,
    rows: Sequence[HistoricalPerformance],
    model: RatingModel,
    fold: str,
    now: datetime,
    team_keys: Mapping[int, str] | None,
    config: OptimizerConfig,
    compact_samples: bool,
    picker: PickerKnobs,
) -> ContestPoolResult | None:
    """Replay one contest under an explicit picker setting (shared-fit helper)."""
    excluded: dict[str, int] = defaultdict(int)
    return _run_contest(
        pool,
        rows=rows,
        model=model,
        fold=fold,
        now=now,
        team_keys=team_keys,
        config=config,
        compact_samples=compact_samples,
        picker=picker,
        excluded=excluded,
    )


def replay_contest_pools_knob_sweep(
    rows: Sequence[HistoricalPerformance],
    contests: Iterable[ParsedContest],
    knobs_list: Sequence[PickerKnobs],
    *,
    fold_of: Callable[[ContestPool], Hashable] | None = None,
    now: datetime | None = None,
    team_keys: Mapping[int, str] | None = None,
    optimizer_config: OptimizerConfig | None = None,
    fit_config: FitConfig | None = None,
    compact_samples: bool = True,
    fitter: Fitter = _production_fit,
    progress: Callable[[str], None] | None = None,
) -> dict[str, tuple[tuple[ContestPoolResult, ...], dict[str, int]]]:
    """One walk-forward fit, many picker settings. Keys are ``PickerKnobs.profile``."""
    if not knobs_list:
        raise ValueError("knobs_list_empty")
    profiles = [k.profile for k in knobs_list]
    if len(set(profiles)) != len(profiles):
        raise ValueError("picker_profile_not_unique")
    clock_now = utc(now or datetime.now(UTC))
    cfg = optimizer_config or OptimizerConfig(simulations=100)
    model_fit_config = fit_config or FitConfig()
    fold_key = fold_of or _default_fold
    by_day = rows_by_eastern_day(rows)
    shared_excluded: dict[str, int] = defaultdict(int)
    pools: list[ContestPool] = []
    for contest in contests:
        if not contest.draft_stats:
            shared_excluded["no_draft_stats"] += 1
            continue
        pool = join_contest_pool(contest, by_day.get(contest.contest.day, ()))
        if pool is None:
            shared_excluded["no_corpus_g_rows_for_day"] += 1
            continue
        pools.append(pool)
    folds: dict[Hashable, list[ContestPool]] = defaultdict(list)
    for pool in pools:
        folds[fold_key(pool)].append(pool)
    results_by_profile: dict[str, list[ContestPoolResult]] = {k.profile: [] for k in knobs_list}
    excluded_by_profile: dict[str, dict[str, int]] = {
        k.profile: defaultdict(int) for k in knobs_list
    }
    for key, fold_pools in sorted(folds.items(), key=lambda item: min(p.cutoff for p in item[1])):
        fold_cutoff = min(pool.cutoff for pool in fold_pools)
        fold_games = {game for pool in fold_pools for game in pool.day_game_ids}
        train = rows_before(rows, cutoff=fold_cutoff, exclude_game_ids=fold_games)
        train, _audit = drop_ambiguous_identity_rows(train)
        assert_no_leakage(train, cutoff=fold_cutoff, slate_game_ids=fold_games)
        try:
            model = fitter(train, clock_now, model_fit_config)
        except ValueError as error:
            if isinstance(error, LeakageError):
                raise
            shared_excluded[f"fit:{error}"] += len(fold_pools)
            continue
        for pool in sorted(fold_pools, key=lambda p: (p.cutoff, p.contest_id)):
            for knobs in knobs_list:
                per_excluded: dict[str, int] = defaultdict(int)
                result = _run_contest(
                    pool,
                    rows=rows,
                    model=model,
                    fold=str(key),
                    now=clock_now,
                    team_keys=team_keys,
                    config=cfg,
                    compact_samples=compact_samples,
                    picker=knobs,
                    excluded=per_excluded,
                )
                for reason, count in per_excluded.items():
                    excluded_by_profile[knobs.profile][reason] += count
                if result is not None:
                    results_by_profile[knobs.profile].append(result)
                    if progress is not None:
                        progress(
                            f"contest:{pool.contest_id} profile={knobs.profile} "
                            f"capture={result.capture_ratio:.3f}"
                        )
    return {
        profile: (
            tuple(results),
            _merge_excluded_counts(shared_excluded, excluded_by_profile[profile]),
        )
        for profile, results in results_by_profile.items()
    }

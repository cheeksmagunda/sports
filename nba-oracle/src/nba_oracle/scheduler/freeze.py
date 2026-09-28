"""NBA freeze cycle.

Step order is fixed: collect, then read the decision clock, then stamp
one evidence epoch for that tick, then check the draftable pool and the
T-40 window, then prepare, then publish. Reading the clock before
collect is the NFL failure mode where every later freshness check saw
future evidence. Stamping the epoch after collect is the failure mode
where a long pool sweep aged the first player past ``max_age`` and
raised ``stale_player`` for evidence gathered in the same tick.

Optional feature rows whose ``available_at`` is after the decision are
skipped and named on the record. A required future row fails closed.
Nothing in this module submits a contest entry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime

from oracle_core.jobs import JobContext, JobResult, JobSpec

from nba_oracle.scheduler.pool import (
    PoolPlayer,
    TipGame,
    evaluate_draftable_pool,
)
from nba_oracle.scheduler.t40 import T40_OFFSET, publication_window

DEFAULT_LEASE_KEY = "nba:freeze_cycle"
DEFAULT_LEASE_TTL_SECONDS = 300
T40_PUBLICATION_OFFSET_MINUTES = int(T40_OFFSET.total_seconds() // 60)


@dataclass(frozen=True)
class FeatureRow:
    """One optional or required feature clock checked at freeze time."""

    name: str
    available_at: datetime
    required: bool = False


@dataclass(frozen=True)
class FreezeSnapshot:
    """What ``collect`` returns. Clocks on players may predate the decision."""

    games: tuple[TipGame, ...]
    players: tuple[PoolPlayer, ...]
    features: tuple[FeatureRow, ...] = ()
    lock_at: datetime | None = None


@dataclass(frozen=True)
class FreezeCycleRecord:
    """One freeze attempt. ``contest_entry`` is always false."""

    decision_at: datetime
    collected: bool
    prepared: bool
    published: bool
    contest_entry: bool
    reasons: tuple[str, ...]
    skipped_features: tuple[str, ...]
    pool_roster_count: int
    pool_observed_count: int
    draftable_game_ids: tuple[str, ...]
    in_t40_window: bool


def stamp_collect_epoch(
    players: tuple[PoolPlayer, ...],
    epoch: datetime,
) -> tuple[PoolPlayer, ...]:
    """Move same-tick observations onto ``epoch``.

    Future evidence is left untouched so a clock skew cannot be rewritten
    into a fresh observation. Unobserved rows are left untouched.
    """

    if epoch.tzinfo is None:
        raise ValueError("epoch_must_be_timezone_aware")
    stamped: list[PoolPlayer] = []
    for player in players:
        evidence_at = player.evidence_at
        if player.observed and evidence_at is not None and evidence_at <= epoch:
            stamped.append(replace(player, evidence_at=epoch))
        else:
            stamped.append(player)
    return tuple(stamped)


def _dedupe(reasons: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    seen: list[str] = []
    for reason in reasons:
        if reason not in seen:
            seen.append(reason)
    return tuple(seen)


def partition_features(
    features: tuple[FeatureRow, ...],
    decision_at: datetime,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split future rows into skipped names and blocking reasons."""

    if decision_at.tzinfo is None:
        raise ValueError("decision_at_must_be_timezone_aware")
    skipped: list[str] = []
    blocking: list[str] = []
    for row in features:
        if row.available_at.tzinfo is None:
            raise ValueError("available_at_must_be_timezone_aware")
        if row.available_at <= decision_at:
            continue
        if row.required:
            blocking.append(f"future_feature:{row.name}")
        else:
            skipped.append(row.name)
    return tuple(skipped), tuple(blocking)


def run_freeze_cycle(
    context: JobContext,
    *,
    collect: Callable[[], FreezeSnapshot],
    prepare: Callable[[], bool] | None = None,
    publish: Callable[[], bool] | None = None,
    max_age_seconds: int = 900,
) -> tuple[JobResult, FreezeCycleRecord]:
    """Run one observation-only freeze cycle. Never sets contest entry."""

    snapshot = collect()
    decision_at = context.now()
    players = stamp_collect_epoch(snapshot.players, decision_at)
    pool = evaluate_draftable_pool(
        games=snapshot.games,
        players=players,
        decision_at=decision_at,
        evidence_epoch=decision_at,
        max_age_seconds=max_age_seconds,
    )
    window, timing_reasons = publication_window(
        games=snapshot.games,
        decision_at=decision_at,
        lock_at=snapshot.lock_at,
    )
    skipped, feature_reasons = partition_features(snapshot.features, decision_at)
    reasons = _dedupe((*pool.reasons, *timing_reasons, *feature_reasons))
    in_window = window is not None and window.contains(decision_at)

    def _record(*, prepared: bool, published: bool) -> FreezeCycleRecord:
        return FreezeCycleRecord(
            decision_at=decision_at,
            collected=True,
            prepared=prepared,
            published=published,
            contest_entry=False,
            reasons=reasons,
            skipped_features=skipped,
            pool_roster_count=pool.roster_count,
            pool_observed_count=pool.observed_count,
            draftable_game_ids=pool.draftable_game_ids,
            in_t40_window=in_window,
        )

    details = {
        "decision_at": decision_at.isoformat(),
        "reasons": list(reasons),
        "skipped_features": list(skipped),
        "contest_entry": False,
        "in_t40_window": in_window,
        "pool_roster_count": pool.roster_count,
        "pool_observed_count": pool.observed_count,
        "draftable_game_ids": list(pool.draftable_game_ids),
    }

    if reasons:
        record = _record(prepared=False, published=False)
        return JobResult.retryable_failure(reasons[0], **details), record

    prepared = True if prepare is None else prepare()
    if not prepared:
        record = _record(prepared=False, published=False)
        return JobResult.retryable_failure("prepare_failed", **details), record

    published = True if publish is None else publish()
    record = _record(prepared=True, published=published)
    if published:
        result = JobResult.success("freeze_cycle_complete", **details)
    else:
        result = JobResult.retryable_failure("publish_failed", **details)
    return result, record


def build_freeze_job(
    *,
    collect: Callable[[], FreezeSnapshot],
    prepare: Callable[[], bool] | None = None,
    publish: Callable[[], bool] | None = None,
    max_age_seconds: int = 900,
    lease_key: str = DEFAULT_LEASE_KEY,
    lease_ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
) -> JobSpec:
    """Register the freeze cycle for the worker role only."""

    def handler(context: JobContext) -> JobResult:
        result, _record = run_freeze_cycle(
            context,
            collect=collect,
            prepare=prepare,
            publish=publish,
            max_age_seconds=max_age_seconds,
        )
        return result

    return JobSpec(
        name="nba_freeze_cycle",
        handler=handler,
        roles=frozenset({"worker"}),
        lease_key=lease_key,
        lease_ttl_seconds=lease_ttl_seconds,
    )

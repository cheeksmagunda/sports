"""NBA T-40 freeze gate: draftable pool, clock order, same-tick epoch."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from oracle_core.jobs import JobContext, JobRegistry, JobRunner, JobStatus, RoleMismatchError
from oracle_core.logging import get_logger
from oracle_core.testing import FakeLeaseStore, FixedClock

from nba_oracle.api.app import create_app
from nba_oracle.scheduler.freeze import (
    FeatureRow,
    FreezeSnapshot,
    build_freeze_job,
    run_freeze_cycle,
    stamp_collect_epoch,
)
from nba_oracle.scheduler.pool import PoolPlayer, TipGame, evaluate_draftable_pool
from nba_oracle.scheduler.t40 import publication_window

TIP = datetime(2026, 10, 20, 23, 0, tzinfo=UTC)
LATER_TIP = datetime(2026, 10, 21, 1, 30, tzinfo=UTC)


def _players(game_id: str, count: int, evidence_at: datetime) -> tuple[PoolPlayer, ...]:
    return tuple(
        PoolPlayer(
            player_id=f"{game_id}-{index}",
            game_id=game_id,
            observed=True,
            evidence_at=evidence_at,
        )
        for index in range(count)
    )


def _context(clock: FixedClock) -> JobContext:
    return JobContext(
        job_name="nba_freeze_cycle",
        role="worker",
        run_id="test-run",
        started_at=clock(),
        clock=clock,
        logger=get_logger("nba_oracle.test"),
    )


def _snapshot(
    *,
    evidence_at: datetime,
    games: tuple[TipGame, ...] | None = None,
    extra_players: tuple[PoolPlayer, ...] = (),
    features: tuple[FeatureRow, ...] = (),
    lock_at: datetime | None = None,
) -> FreezeSnapshot:
    slate_games = games or (TipGame("early", TIP),)
    return FreezeSnapshot(
        games=slate_games,
        players=_players("early", 5, evidence_at) + extra_players,
        features=features,
        lock_at=lock_at,
    )


def test_tipped_game_does_not_incomplete_the_later_pool() -> None:
    decision = TIP + timedelta(minutes=20)
    epoch = decision
    games = (TipGame("early", TIP), TipGame("late", LATER_TIP))
    tipped_unobserved = tuple(
        PoolPlayer(player_id=f"gone-{index}", game_id="early", observed=False) for index in range(8)
    )
    later = _players("late", 5, epoch)
    assessment = evaluate_draftable_pool(
        games=games,
        players=tipped_unobserved + later,
        decision_at=decision,
        evidence_epoch=epoch,
    )
    assert assessment.ok is True
    assert assessment.draftable_game_ids == ("late",)
    assert assessment.roster_count == 5
    assert "incomplete_player_pool" not in assessment.reasons


def test_unobserved_draftable_player_fails_closed() -> None:
    decision = TIP - timedelta(minutes=30)
    players = _players("early", 5, decision) + (
        PoolPlayer(player_id="missing", game_id="early", observed=False),
    )
    assessment = evaluate_draftable_pool(
        games=(TipGame("early", TIP),),
        players=players,
        decision_at=decision,
        evidence_epoch=decision,
    )
    assert assessment.ok is False
    assert "incomplete_player_pool" in assessment.reasons
    assert assessment.unmatched_ids == ("missing",)


def test_same_tick_epoch_is_fresh_when_wall_clock_moved() -> None:
    epoch = TIP - timedelta(minutes=30)
    decision = epoch + timedelta(minutes=20)
    aged = evaluate_draftable_pool(
        games=(TipGame("early", TIP),),
        players=_players("early", 5, epoch),
        decision_at=decision,
        max_age_seconds=60,
    )
    assert "stale_player" in aged.reasons

    fresh = evaluate_draftable_pool(
        games=(TipGame("early", TIP),),
        players=_players("early", 5, epoch),
        decision_at=decision,
        evidence_epoch=epoch,
        max_age_seconds=60,
    )
    assert fresh.ok is True
    assert "stale_player" not in fresh.reasons


def test_future_player_evidence_fails_closed() -> None:
    decision = TIP - timedelta(minutes=20)
    future = decision + timedelta(seconds=5)
    assessment = evaluate_draftable_pool(
        games=(TipGame("early", TIP),),
        players=_players("early", 5, future),
        decision_at=decision,
        evidence_epoch=decision,
    )
    assert assessment.ok is False
    assert "future_evidence" in assessment.reasons


def test_later_window_uses_the_next_tip_not_the_first() -> None:
    decision = TIP + timedelta(minutes=15)
    window, reasons = publication_window(
        games=(TipGame("early", TIP), TipGame("late", LATER_TIP)),
        decision_at=decision,
    )
    assert window is not None
    assert window.cutoff_at == LATER_TIP
    assert window.open_at == LATER_TIP - timedelta(minutes=40)
    assert reasons == ("before_t40_window",)
    assert window.contains(decision) is False


def test_inside_t40_window_has_no_timing_reason() -> None:
    decision = TIP - timedelta(minutes=20)
    window, reasons = publication_window(
        games=(TipGame("early", TIP),),
        decision_at=decision,
    )
    assert reasons == ()
    assert window is not None
    assert window.contains(decision) is True


def test_decision_at_is_read_after_collect_and_epoch_clears_stale() -> None:
    start = TIP - timedelta(minutes=50)
    clock = FixedClock(start)
    context = _context(clock)
    captured = start

    def collect() -> FreezeSnapshot:
        nonlocal captured
        captured = clock()
        clock.advance(timedelta(minutes=20))
        return _snapshot(evidence_at=captured)

    result, record = run_freeze_cycle(context, collect=collect, max_age_seconds=60)

    decision = start + timedelta(minutes=20)
    assert record.decision_at == decision
    assert record.decision_at != captured
    assert record.contest_entry is False
    assert record.prepared is True
    assert record.published is True
    assert record.in_t40_window is True
    assert record.reasons == ()
    assert result.status == JobStatus.SUCCESS
    assert result.details["contest_entry"] is False
    assert result.message == "freeze_cycle_complete"


def test_before_t40_refuses_with_reason_and_skips_prepare() -> None:
    start = TIP - timedelta(hours=3)
    clock = FixedClock(start)
    prepare_calls: list[bool] = []

    def prepare() -> bool:
        prepare_calls.append(True)
        return True

    result, record = run_freeze_cycle(
        _context(clock),
        collect=lambda: _snapshot(evidence_at=start),
        prepare=prepare,
    )
    assert result.status == JobStatus.RETRYABLE_FAILURE
    assert result.message == "before_t40_window"
    assert "before_t40_window" in result.details["reasons"]
    assert record.prepared is False
    assert record.published is False
    assert record.contest_entry is False
    assert prepare_calls == []


def test_optional_future_feature_is_skipped_and_required_blocks() -> None:
    decision = TIP - timedelta(minutes=15)
    clock = FixedClock(decision)
    optional = FeatureRow(
        name="forecast_note",
        available_at=decision + timedelta(minutes=5),
        required=False,
    )
    result, record = run_freeze_cycle(
        _context(clock),
        collect=lambda: _snapshot(evidence_at=decision, features=(optional,)),
    )
    assert result.status == JobStatus.SUCCESS
    assert record.skipped_features == ("forecast_note",)
    assert record.reasons == ()

    required = FeatureRow(
        name="identity_feed",
        available_at=decision + timedelta(minutes=5),
        required=True,
    )
    prepare_calls: list[bool] = []

    def prepare() -> bool:
        prepare_calls.append(True)
        return True

    blocked, blocked_record = run_freeze_cycle(
        _context(clock),
        collect=lambda: _snapshot(evidence_at=decision, features=(required,)),
        prepare=prepare,
    )
    assert blocked.status == JobStatus.RETRYABLE_FAILURE
    assert blocked.message == "future_feature:identity_feed"
    assert blocked_record.prepared is False
    assert prepare_calls == []


def test_stamp_does_not_rewrite_future_evidence() -> None:
    decision = TIP - timedelta(minutes=15)
    future = decision + timedelta(minutes=1)
    stamped = stamp_collect_epoch(
        (PoolPlayer("p", "early", True, future),),
        decision,
    )
    assert stamped[0].evidence_at == future


def test_short_card_fails_closed() -> None:
    decision = TIP - timedelta(minutes=15)
    assessment = evaluate_draftable_pool(
        games=(TipGame("early", TIP),),
        players=_players("early", 4, decision),
        decision_at=decision,
        evidence_epoch=decision,
    )
    assert assessment.reasons == ("fewer_than_five_candidates",)


def test_freeze_job_is_worker_only_and_lease_skips() -> None:
    start = TIP - timedelta(minutes=15)
    clock = FixedClock(start)
    lease_store = FakeLeaseStore(clock=lambda: clock().timestamp())
    job = build_freeze_job(
        collect=lambda: _snapshot(evidence_at=start),
        lease_key="nba:freeze_cycle",
    )
    runner = JobRunner(JobRegistry([job]), lease_store=lease_store, clock=clock)

    with pytest.raises(RoleMismatchError):
        runner.run("nba_freeze_cycle", role="serve")

    held = lease_store.acquire("nba:freeze_cycle", ttl_seconds=300)
    assert held is not None
    skipped = runner.run("nba_freeze_cycle", role="worker")
    assert skipped.status == JobStatus.SKIPPED

    lease_store.release(held)
    ran = runner.run("nba_freeze_cycle", role="worker")
    assert ran.status == JobStatus.SUCCESS
    assert ran.details["contest_entry"] is False


def test_health_app_does_not_grow_a_freeze_route() -> None:
    paths = {getattr(route, "path", None) for route in create_app().routes}
    assert "/health" in paths
    assert "/" in paths
    assert "/freeze" not in paths
    assert "/slate" not in paths

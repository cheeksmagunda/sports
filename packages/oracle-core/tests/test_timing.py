from __future__ import annotations

from datetime import UTC, datetime, timedelta

from oracle_core.timing import window_decision


def test_window_decision_not_yet_due() -> None:
    now = datetime(2026, 9, 20, 19, 0, tzinfo=UTC)
    target = datetime(2026, 9, 20, 20, 5, tzinfo=UTC)

    decision = window_decision(now=now, target_at=target, lead=timedelta(minutes=40))

    assert decision.due is False
    assert decision.due_at == datetime(2026, 9, 20, 19, 25, tzinfo=UTC)
    assert decision.seconds_remaining == 25 * 60
    details = decision.as_details()
    assert details["next_due"] == decision.due_at.isoformat()
    assert details["target_at"] == target.isoformat()


def test_window_decision_due_exactly_at_boundary() -> None:
    now = datetime(2026, 9, 20, 19, 25, tzinfo=UTC)
    target = datetime(2026, 9, 20, 20, 5, tzinfo=UTC)

    decision = window_decision(now=now, target_at=target, lead=timedelta(minutes=40))

    assert decision.due is True
    assert decision.seconds_remaining == 0


def test_window_decision_past_target() -> None:
    now = datetime(2026, 9, 20, 20, 30, tzinfo=UTC)
    target = datetime(2026, 9, 20, 20, 5, tzinfo=UTC)

    decision = window_decision(now=now, target_at=target, lead=timedelta(minutes=40))

    assert decision.due is True
    assert decision.seconds_remaining < 0

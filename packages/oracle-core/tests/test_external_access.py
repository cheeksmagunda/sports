from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from oracle_core.external_access import AccessPolicy, evaluate_access


def test_access_policy_allows_first_window() -> None:
    now = datetime(2026, 8, 26, 16, tzinfo=UTC)
    policy = AccessPolicy(timedelta(hours=3), max_windows_per_day=4)

    decision = evaluate_access(
        policy=policy,
        now=now,
        last_started_at=None,
        windows_today=0,
    )

    assert decision.granted is True
    assert decision.reason == "granted"


def test_access_policy_enforces_account_wide_cooldown() -> None:
    last = datetime(2026, 8, 26, 14, tzinfo=UTC)
    policy = AccessPolicy(timedelta(hours=3), max_windows_per_day=4)

    decision = evaluate_access(
        policy=policy,
        now=last + timedelta(hours=2),
        last_started_at=last,
        windows_today=1,
    )

    assert decision.granted is False
    assert decision.reason == "cooldown"
    assert decision.next_eligible_at == last + timedelta(hours=3)


def test_access_policy_enforces_daily_ceiling() -> None:
    policy = AccessPolicy(timedelta(hours=1), max_windows_per_day=4)

    decision = evaluate_access(
        policy=policy,
        now=datetime(2026, 8, 26, 22, tzinfo=UTC),
        last_started_at=datetime(2026, 8, 26, 18, tzinfo=UTC),
        windows_today=4,
    )

    assert decision.granted is False
    assert decision.reason == "daily_limit"


def test_access_policy_rejects_naive_clock() -> None:
    policy = AccessPolicy(timedelta(hours=1), max_windows_per_day=4)

    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate_access(
            policy=policy,
            now=datetime(2026, 8, 26, 12),
            last_started_at=None,
            windows_today=0,
        )


def test_access_policy_validates_limits_and_timezone() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        AccessPolicy(timedelta(hours=1), max_windows_per_day=0)
    with pytest.raises(ValueError, match="unknown timezone"):
        AccessPolicy(timedelta(hours=1), max_windows_per_day=1, timezone="Mars/Olympus")

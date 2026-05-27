"""Watchdog trigger logic — pure function tests against a mocked engine."""

from __future__ import annotations

import datetime as dt
import json
from unittest.mock import MagicMock, patch

from wnba_oracle.scheduler import watchdog


def _engine_with_pool_count(n: int) -> MagicMock:
    eng = MagicMock()
    result = MagicMock()
    result.first.return_value = (n,)
    conn = MagicMock()
    conn.execute.return_value = result
    eng.connect.return_value.__enter__.return_value = conn
    return eng


def _engine_with_freeze_row(row: tuple | None) -> MagicMock:
    eng = MagicMock()
    result = MagicMock()
    result.first.return_value = row
    conn = MagicMock()
    conn.execute.return_value = result
    eng.connect.return_value.__enter__.return_value = conn
    return eng


def test_no_job1_pool_triggers_critical() -> None:
    with patch.object(watchdog, "get_engine", return_value=_engine_with_pool_count(0)):
        events = watchdog._check_pool("2026-05-27")
    assert len(events) == 1
    assert events[0].trigger == "no_job1_pool"
    assert events[0].severity == "critical"


def test_small_pool_triggers_warn() -> None:
    with patch.object(watchdog, "get_engine", return_value=_engine_with_pool_count(7)):
        events = watchdog._check_pool("2026-05-27")
    assert len(events) == 1
    assert events[0].trigger == "pool_too_small"
    assert events[0].severity == "warn"
    assert events[0].payload["pool_size"] == 7


def test_healthy_pool_no_events() -> None:
    with patch.object(watchdog, "get_engine", return_value=_engine_with_pool_count(60)):
        assert watchdog._check_pool("2026-05-27") == []


def test_no_frozen_lineup_after_22utc_triggers_critical() -> None:
    with patch.object(watchdog, "get_engine", return_value=_engine_with_freeze_row(None)):
        events = watchdog._check_freeze(
            "2026-05-27",
            now_utc=dt.datetime(2026, 5, 27, 22, 30, tzinfo=dt.UTC),
        )
    assert len(events) == 1
    assert events[0].trigger == "no_frozen_lineup"
    assert events[0].severity == "critical"


def test_no_frozen_lineup_before_22utc_no_event() -> None:
    """Quiet before the cron-job2 window has had enough attempts."""
    with patch.object(watchdog, "get_engine", return_value=_engine_with_freeze_row(None)):
        events = watchdog._check_freeze(
            "2026-05-27",
            now_utc=dt.datetime(2026, 5, 27, 21, 5, tzinfo=dt.UTC),
        )
    assert events == []


def test_no_frozen_lineup_quiet_for_past_slate() -> None:
    """Backfill / historical query — don't false-positive when the slate
    is yesterday and the check happens to fire today."""
    with patch.object(watchdog, "get_engine", return_value=_engine_with_freeze_row(None)):
        events = watchdog._check_freeze(
            "2026-05-26",
            now_utc=dt.datetime(2026, 5, 27, 23, 0, tzinfo=dt.UTC),
        )
    assert events == []


def test_missing_per_player_block_triggers_error() -> None:
    lineup = {"player_ids": [1, 2, 3, 4, 5], "slot_multipliers": [1.5]}  # no per_player
    row = (json.dumps(lineup), 1.2, dt.datetime.now(dt.UTC))
    with patch.object(watchdog, "get_engine", return_value=_engine_with_freeze_row(row)):
        events = watchdog._check_freeze(
            "2026-05-27",
            now_utc=dt.datetime(2026, 5, 27, 22, 30, tzinfo=dt.UTC),
        )
    triggers = {e.trigger for e in events}
    assert "missing_per_player" in triggers


def test_zero_expected_payout_triggers_warn() -> None:
    lineup = {"per_player": [{"player_id": i} for i in (1, 2, 3, 4, 5)]}
    row = (json.dumps(lineup), 0.0, dt.datetime.now(dt.UTC))
    with patch.object(watchdog, "get_engine", return_value=_engine_with_freeze_row(row)):
        events = watchdog._check_freeze("2026-05-27")
    triggers = {e.trigger for e in events}
    assert "zero_expected_payout" in triggers


def test_healthy_freeze_no_events() -> None:
    lineup = {"per_player": [{"player_id": i} for i in (1, 2, 3, 4, 5)]}
    row = (json.dumps(lineup), 1.4, dt.datetime.now(dt.UTC))
    with patch.object(watchdog, "get_engine", return_value=_engine_with_freeze_row(row)):
        events = watchdog._check_freeze("2026-05-27")
    assert events == []


def test_run_watchdog_aggregates_and_persists() -> None:
    """run_watchdog composes _check_pool + _check_freeze + persist. Patch
    each leaf so this test stays focused on the aggregation logic and
    doesn't have to thread two different SQL result shapes through one
    mock engine."""
    pool_ev = watchdog.WatchdogEvent(
        slate_date="2026-05-27",
        trigger="no_job1_pool",
        severity=watchdog.SEVERITY_CRITICAL,
        payload={"pool_size": 0},
    )
    freeze_ev = watchdog.WatchdogEvent(
        slate_date="2026-05-27",
        trigger="no_frozen_lineup",
        severity=watchdog.SEVERITY_CRITICAL,
        payload={"note": "no row"},
    )
    with patch.object(watchdog, "_check_pool", return_value=[pool_ev]), patch.object(
        watchdog, "_check_freeze", return_value=[freeze_ev]
    ), patch.object(watchdog, "persist_events", return_value=2) as persist:
        events = watchdog.run_watchdog(
            "2026-05-27",
            now_utc=dt.datetime(2026, 5, 27, 23, 0, tzinfo=dt.UTC),
        )
    triggers = {e.trigger for e in events}
    assert triggers == {"no_job1_pool", "no_frozen_lineup"}
    persist.assert_called_once_with([pool_ev, freeze_ev])


def test_summarize_status_picks_highest_severity() -> None:
    from wnba_oracle.api.watchdog import _summarize  # local import keeps test deps minimal

    assert _summarize([]) == "ok"
    assert _summarize([{"severity": "warn"}]) == "warn"
    assert _summarize([{"severity": "warn"}, {"severity": "error"}]) == "error"
    assert (
        _summarize(
            [{"severity": "warn"}, {"severity": "error"}, {"severity": "critical"}]
        )
        == "critical"
    )

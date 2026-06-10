"""Watchdog trigger logic — pure function tests against a mocked engine."""

from __future__ import annotations

import datetime as dt
import json
from unittest.mock import MagicMock, patch

from wnba_oracle.scheduler import watchdog


def _engine_with_pool_count(
    n: int,
    n_teams: int | None = None,
    last_captured: dt.datetime | None = None,
) -> MagicMock:
    eng = MagicMock()
    result = MagicMock()
    # POOL_SIZE_Q returns (count, distinct teams, max captured_at).
    teams = n_teams if n_teams is not None else min(n, 12)
    result.first.return_value = (n, teams, last_captured)
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


def test_small_pool_triggers_error() -> None:
    """D84: escalated from warn — a sub-10 pool is an ingest failure."""
    with patch.object(watchdog, "get_engine", return_value=_engine_with_pool_count(7)):
        events = watchdog._check_pool("2026-05-27")
    assert len(events) == 1
    assert events[0].trigger == "pool_too_small"
    assert events[0].severity == "error"
    assert events[0].payload["pool_size"] == 7


def test_single_team_pool_triggers_critical() -> None:
    """D84: the 2026-06-08 morning shape — rows exist, one team."""
    eng = _engine_with_pool_count(12, n_teams=1)
    with patch.object(watchdog, "get_engine", return_value=eng):
        events = watchdog._check_pool("2026-05-27")
    triggers = {e.trigger: e.severity for e in events}
    assert triggers.get("pool_degenerate_teams") == "critical"


def test_enrichment_stale_after_20utc() -> None:
    stale = dt.datetime(2026, 5, 27, 9, 0, tzinfo=dt.UTC)
    eng = _engine_with_pool_count(60, last_captured=stale)
    with patch.object(watchdog, "get_engine", return_value=eng):
        events = watchdog._check_enrichment_freshness(
            "2026-05-27", now_utc=dt.datetime(2026, 5, 27, 20, 30, tzinfo=dt.UTC)
        )
    assert len(events) == 1
    assert events[0].trigger == "enrichment_stale"
    assert events[0].severity == "warn"


def test_enrichment_fresh_no_event() -> None:
    fresh = dt.datetime(2026, 5, 27, 13, 40, tzinfo=dt.UTC)
    eng = _engine_with_pool_count(60, last_captured=fresh)
    with patch.object(watchdog, "get_engine", return_value=eng):
        events = watchdog._check_enrichment_freshness(
            "2026-05-27", now_utc=dt.datetime(2026, 5, 27, 20, 30, tzinfo=dt.UTC)
        )
    assert events == []


def test_enrichment_freshness_quiet_before_20utc() -> None:
    """The 13:00 UTC job1-path watchdog run must not flag the capture it
    just made (or its absence minutes before)."""
    eng = _engine_with_pool_count(60, last_captured=None)
    with patch.object(watchdog, "get_engine", return_value=eng):
        events = watchdog._check_enrichment_freshness(
            "2026-05-27", now_utc=dt.datetime(2026, 5, 27, 13, 10, tzinfo=dt.UTC)
        )
    assert events == []


def _engine_with_coverage(
    n_pool: int, n_missing: int, sample: list[tuple] | None = None
) -> MagicMock:
    eng = MagicMock()
    cov_result = MagicMock()
    cov_result.first.return_value = (n_pool, n_missing)
    sample_result = iter(sample or [])
    conn = MagicMock()
    conn.execute.side_effect = [cov_result, sample_result]
    eng.connect.return_value.__enter__.return_value = conn
    return eng


def test_label_coverage_gap_warn_on_small_gap() -> None:
    eng = _engine_with_coverage(80, 2, [(726, "J. Loyd"), (627, "A. Boston")])
    with patch.object(watchdog, "get_engine", return_value=eng):
        events = watchdog._check_label_coverage("2026-06-08")
    assert len(events) == 1
    assert events[0].trigger == "label_coverage_gap"
    assert events[0].severity == "warn"
    assert events[0].payload["n_missing"] == 2
    assert {s["player_id"] for s in events[0].payload["sample"]} == {726, 627}


def test_label_coverage_gap_error_above_20pct() -> None:
    eng = _engine_with_coverage(80, 40, [(1, "P1")])
    with patch.object(watchdog, "get_engine", return_value=eng):
        events = watchdog._check_label_coverage("2026-06-08")
    assert events[0].severity == "error"


def test_label_coverage_clean_no_event() -> None:
    eng = _engine_with_coverage(80, 0)
    with patch.object(watchdog, "get_engine", return_value=eng):
        assert watchdog._check_label_coverage("2026-06-08") == []


def test_label_coverage_quiet_on_empty_pool() -> None:
    """no_job1_pool owns the empty-pool signal; coverage stays silent."""
    eng = _engine_with_coverage(0, 0)
    with patch.object(watchdog, "get_engine", return_value=eng):
        assert watchdog._check_label_coverage("2026-06-08") == []


def _ev(severity: str) -> watchdog.WatchdogEvent:
    return watchdog.WatchdogEvent(
        slate_date="2026-05-27", trigger="t", severity=severity, payload={}
    )


def test_ping_fires_on_critical_when_url_set() -> None:
    from types import SimpleNamespace

    settings = SimpleNamespace(watchdog_ping_url="https://hc.example/abc")
    with patch(
        "wnba_oracle.common.settings.get_settings", return_value=settings
    ), patch("httpx.get") as get:
        watchdog._ping_on_critical([_ev("critical")])
    get.assert_called_once_with("https://hc.example/abc/fail", timeout=5.0)


def test_ping_skipped_without_critical() -> None:
    from types import SimpleNamespace

    settings = SimpleNamespace(watchdog_ping_url="https://hc.example/abc")
    with patch(
        "wnba_oracle.common.settings.get_settings", return_value=settings
    ), patch("httpx.get") as get:
        watchdog._ping_on_critical([_ev("warn"), _ev("error")])
    get.assert_not_called()


def test_ping_noop_without_url() -> None:
    from types import SimpleNamespace

    settings = SimpleNamespace(watchdog_ping_url="")
    with patch(
        "wnba_oracle.common.settings.get_settings", return_value=settings
    ), patch("httpx.get") as get:
        watchdog._ping_on_critical([_ev("critical")])
    get.assert_not_called()


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
        watchdog, "_check_enrichment_freshness", return_value=[]
    ), patch.object(
        watchdog, "_check_freeze", return_value=[freeze_ev]
    ), patch.object(watchdog, "persist_events", return_value=2) as persist, patch.object(
        watchdog, "_ping_on_critical"
    ) as ping:
        events = watchdog.run_watchdog(
            "2026-05-27",
            now_utc=dt.datetime(2026, 5, 27, 23, 0, tzinfo=dt.UTC),
        )
    triggers = {e.trigger for e in events}
    assert triggers == {"no_job1_pool", "no_frozen_lineup"}
    persist.assert_called_once_with([pool_ev, freeze_ev])
    ping.assert_called_once_with([pool_ev, freeze_ev])


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


def test_route_order_today_before_slate_param() -> None:
    """FastAPI matches routes in declaration order. If /{slate_date} is
    declared before /today, requests to /watchdog/today silently bind
    slate_date='today' and return empty events. Pin the order."""
    from wnba_oracle.api.watchdog import router

    watchdog_paths = [r.path for r in router.routes if hasattr(r, "path")]
    today_idx = watchdog_paths.index("/watchdog/today")
    param_idx = watchdog_paths.index("/watchdog/{slate_date}")
    assert today_idx < param_idx, (
        "/watchdog/today must be declared before /watchdog/{slate_date} or it "
        "will be shadowed at runtime."
    )

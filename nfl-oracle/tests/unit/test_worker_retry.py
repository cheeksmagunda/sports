import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

import nfl_oracle.ingest.realsports as realsports
from nfl_oracle.calendar.schedule import ScheduledGame
from nfl_oracle.recommendations import cli
from nfl_oracle.recommendations.provider import NoSlate


@pytest.mark.parametrize("poll_error", [RuntimeError("poll failed"), NoSlate("no games")])
def test_worker_recovers_when_failure_audit_database_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    poll_error: Exception,
    tmp_path,
) -> None:
    monkeypatch.setenv("NFL_RECOMMENDATIONS_ENABLED", "1")
    # _run_worker's retention-prune sweep runs against whatever _project_root()
    # resolves to. Left unmocked, that's the real repository checkout, not
    # this test's sandbox -- on a long-lived local checkout it silently
    # deletes real, aged (but not disposable-right-now) local data as a side
    # effect of running this test. See #278.
    monkeypatch.setattr(cli, "_project_root", lambda: tmp_path)
    store = Mock()
    store.record_run.side_effect = RuntimeError("password=must-not-appear")
    monkeypatch.setattr(cli, "_engine", Mock())
    monkeypatch.setattr(cli, "RecommendationStore", Mock(return_value=store))
    monkeypatch.setattr(cli, "RecommendationPipeline", Mock())
    poll = AsyncMock(side_effect=[poll_error, {"slate_date": "2026-09-09"}])
    monkeypatch.setattr(cli, "_worker_once", poll)
    sleep = AsyncMock(side_effect=[None, asyncio.CancelledError()])
    monkeypatch.setattr(cli.asyncio, "sleep", sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(cli._run_worker(False, 30, date(2026, 9, 9)))

    output = capsys.readouterr().out
    records = [json.loads(line) for line in output.splitlines()]
    assert poll.await_count == 2
    assert sleep.await_count == 2
    assert records[0]["detail_code"] == "worker_run_record_failed"
    assert records[-1] == {"status": "ready", "slate_date": "2026-09-09", "picks": 5}
    assert "password" not in output
    assert "must-not-appear" not in output


def test_worker_once_still_fails_when_poll_and_failure_audit_fail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("NFL_RECOMMENDATIONS_ENABLED", "1")
    monkeypatch.setattr(cli, "_project_root", lambda: tmp_path)  # see #278
    store = Mock()
    store.record_run.side_effect = RuntimeError("database unavailable")
    monkeypatch.setattr(cli, "_engine", Mock())
    monkeypatch.setattr(cli, "RecommendationStore", Mock(return_value=store))
    monkeypatch.setattr(cli, "RecommendationPipeline", Mock())
    monkeypatch.setattr(cli, "_worker_once", AsyncMock(side_effect=RuntimeError("poll failed")))
    sleep = AsyncMock()
    monkeypatch.setattr(cli.asyncio, "sleep", sleep)

    assert asyncio.run(cli._run_worker(True, 30, date(2026, 9, 9))) == 1
    sleep.assert_not_awaited()


def test_run_worker_passes_explicit_refreeze_override_to_poll(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NFL_RECOMMENDATIONS_ENABLED", "1")
    monkeypatch.setattr(cli, "_engine", Mock())
    monkeypatch.setattr(cli, "RecommendationStore", Mock(return_value=Mock()))
    monkeypatch.setattr(cli, "RecommendationPipeline", Mock())
    poll = AsyncMock(return_value=None)
    monkeypatch.setattr(cli, "_worker_once", poll)

    assert asyncio.run(cli._run_worker(True, 30, date(2026, 9, 9), allow_refreeze=True)) == 0

    assert poll.await_args.kwargs["allow_refreeze"] is True


def test_prune_data_retention_removes_only_expired_files(tmp_path) -> None:
    obs = tmp_path / "data" / "raw" / "observations" / "ab"
    obs.mkdir(parents=True)
    fresh = obs / "fresh.json"
    stale = obs / "stale.json"
    fresh.write_text("{}")
    stale.write_text("{}")
    import os
    import time

    old = time.time() - 10 * 24 * 60 * 60
    os.utime(stale, (old, old))

    cli._prune_data_retention(tmp_path)

    assert fresh.exists()
    assert not stale.exists()


def test_prune_data_retention_survives_missing_directories(tmp_path) -> None:
    # Neither data/raw/observations nor data/artifacts/context exists yet.
    cli._prune_data_retention(tmp_path)


def test_disk_usage_metadata_reports_percent_used(tmp_path) -> None:
    (tmp_path / "data").mkdir()
    metadata = cli._disk_usage_metadata(tmp_path)
    assert "disk" in metadata
    assert "percent_used" in metadata["disk"]


# --- Offline T-40 pregate (#267) -------------------------------------------

_KICKOFF = datetime(2026, 9, 25, 0, 15, tzinfo=UTC)  # Thu 2026-09-24 20:15 ET
_DAY = date(2026, 9, 24)


def _game(kickoff: datetime | None, game_id: str = "2026_03_ATL_GB") -> ScheduledGame:
    return ScheduledGame(
        season=2026,
        week=3,
        game_id=game_id,
        gameday=_DAY,
        home_team="GB",
        away_team="ATL",
        kickoff_at=kickoff,
    )


def _fresh_state(now: datetime) -> cli._PregateState:
    return cli._PregateState(live_checked_at=now - timedelta(minutes=1))


class _FrozenClock(datetime):
    fixed: datetime = _KICKOFF

    @classmethod
    def now(cls, tz: Any = None) -> Any:  # type: ignore[override]
        return cls.fixed if tz is None else cls.fixed.astimezone(tz)


def _run_poll(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    now: datetime,
    games: tuple[ScheduledGame, ...],
    state: cli._PregateState | None,
    requested_day: date | None = _DAY,
    store: Mock | None = None,
) -> tuple[Mock, AsyncMock]:
    """Run one _worker_once poll; the live capture fails loudly if reached."""
    _FrozenClock.fixed = now
    monkeypatch.setattr(cli, "datetime", _FrozenClock)
    capture = AsyncMock(side_effect=RuntimeError("live_capture_called"))
    monkeypatch.setattr(realsports, "headers_or_capture", capture)
    monkeypatch.setattr(cli, "NFLReader", Mock(side_effect=AssertionError("live_reader_built")))
    monkeypatch.setattr(cli, "_disk_usage_metadata", lambda _project: {})
    if store is None:
        store = Mock()
        store.latest.return_value = None
    try:
        asyncio.run(
            cli._worker_once(
                tmp_path,
                store,
                Mock(),
                requested_day,
                schedule_games=games,
                pregate_state=state,
            )
        )
    except RuntimeError as error:
        assert str(error) == "live_capture_called"
    return store, capture


def test_pregate_skips_live_calls_far_from_kickoff(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    now = _KICKOFF - timedelta(hours=3)
    store, capture = _run_poll(
        monkeypatch, tmp_path, now=now, games=(_game(_KICKOFF),), state=_fresh_state(now)
    )
    capture.assert_not_awaited()
    assert store.record_run.call_args.args == (_DAY,)
    kwargs = store.record_run.call_args.kwargs
    assert kwargs["status"] == "waiting"
    assert kwargs["detail_code"] == "waiting_offline_pregate"
    assert kwargs["details"]["cutoff_at"] == _KICKOFF.isoformat()
    assert kwargs["details"]["gate_source"] == "offline_schedule"


def test_pregate_resolves_eastern_day_without_requested_day(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # 17:00 UTC is 13:00 ET Thursday; the slate day is the ET date.
    now = _KICKOFF - timedelta(hours=7, minutes=15)
    store, capture = _run_poll(
        monkeypatch,
        tmp_path,
        now=now,
        games=(_game(_KICKOFF),),
        state=_fresh_state(now),
        requested_day=None,
    )
    capture.assert_not_awaited()
    assert store.record_run.call_args.args == (_DAY,)


@pytest.mark.parametrize("minutes_before", [60, 59, 41, 40, 10, -5])
def test_pregate_goes_live_inside_sixty_minute_window(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, minutes_before: int
) -> None:
    now = _KICKOFF - timedelta(minutes=minutes_before)
    _, capture = _run_poll(
        monkeypatch, tmp_path, now=now, games=(_game(_KICKOFF),), state=_fresh_state(now)
    )
    capture.assert_awaited_once()


def test_pregate_goes_live_when_any_kickoff_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    now = _KICKOFF - timedelta(hours=3)
    games = (_game(_KICKOFF), _game(None, game_id="2026_03_XXX_YYY"))
    _, capture = _run_poll(monkeypatch, tmp_path, now=now, games=games, state=_fresh_state(now))
    capture.assert_awaited_once()


def test_pregate_goes_live_with_no_offline_games(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    now = _KICKOFF - timedelta(hours=3)
    _, capture = _run_poll(monkeypatch, tmp_path, now=now, games=(), state=_fresh_state(now))
    capture.assert_awaited_once()


@pytest.mark.parametrize("stale", [None, "never", "thirty_minutes"])
def test_pregate_goes_live_without_a_recent_live_poll(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stale: str | None
) -> None:
    now = _KICKOFF - timedelta(hours=3)
    state: cli._PregateState | None = None
    if stale == "never":
        state = cli._PregateState()
    elif stale == "thirty_minutes":
        state = cli._PregateState(live_checked_at=now - timedelta(minutes=30))
    _, capture = _run_poll(monkeypatch, tmp_path, now=now, games=(_game(_KICKOFF),), state=state)
    capture.assert_awaited_once()


def test_pregate_respects_an_earlier_live_cutoff(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    now = _KICKOFF - timedelta(hours=3)
    state = cli._PregateState(
        live_checked_at=now - timedelta(minutes=1),
        live_day=_DAY,
        live_cutoff=now + timedelta(minutes=45),
    )
    _, capture = _run_poll(monkeypatch, tmp_path, now=now, games=(_game(_KICKOFF),), state=state)
    capture.assert_awaited_once()


def test_pregate_goes_live_when_already_frozen(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    now = _KICKOFF - timedelta(hours=3)
    monkeypatch.setattr(cli, "_already_frozen", lambda _store, _day: True)
    _, capture = _run_poll(
        monkeypatch, tmp_path, now=now, games=(_game(_KICKOFF),), state=_fresh_state(now)
    )
    capture.assert_awaited_once()


def test_pregate_falls_through_when_recording_the_skip_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    now = _KICKOFF - timedelta(hours=3)
    store = Mock()
    store.latest.return_value = None
    store.record_run.side_effect = RuntimeError("database unavailable")
    _, capture = _run_poll(
        monkeypatch,
        tmp_path,
        now=now,
        games=(_game(_KICKOFF),),
        state=_fresh_state(now),
        store=store,
    )
    capture.assert_awaited_once()


def test_pregate_never_raises_and_falls_through_on_error() -> None:
    class _Broken:
        def __iter__(self) -> Any:
            raise RuntimeError("schedule exploded")

    now = _KICKOFF - timedelta(hours=3)
    assert cli._offline_pregate(_Broken(), _DAY, now, _fresh_state(now)) is None  # type: ignore[arg-type]


def test_pregate_uses_eastern_date_not_utc_date_after_evening_rollover() -> None:
    # Sunday 20:00 ET is Monday 00:00 UTC. Sunday's SNF is still the slate;
    # picking Monday's MNF by UTC date would wrongly skip the live poll.
    sunday = date(2026, 9, 27)
    snf = ScheduledGame(
        2026, 3, "snf", sunday, "A", "B", kickoff_at=datetime(2026, 9, 28, 0, 20, tzinfo=UTC)
    )
    mnf = ScheduledGame(
        2026,
        3,
        "mnf",
        date(2026, 9, 28),
        "E",
        "F",
        kickoff_at=datetime(2026, 9, 29, 0, 15, tzinfo=UTC),
    )
    now = datetime(2026, 9, 28, 0, 0, tzinfo=UTC)
    assert cli._offline_pregate((snf, mnf), None, now, _fresh_state(now)) is None

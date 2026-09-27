"""Offline T-40 pre-check skips the live fetch when it can confidently vouch
for "not due yet" (#267), and always falls through to the live path
otherwise -- missing offline kickoff data, an explicit requested day, or the
offline gate itself saying due.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from nfl_oracle.recommendations import cli


class _StubStore:
    def __init__(self) -> None:
        self.runs: list[dict[str, object]] = []

    def latest(self, day):  # noqa: ANN001 - test stub
        return None

    def record_run(self, day, *, status, detail_code, details=None) -> None:  # noqa: ANN001
        self.runs.append(
            {"day": day, "status": status, "detail_code": detail_code, "details": details}
        )


def _write_schedule(project: Path, rows: str) -> None:
    schedule_dir = project / "data" / "schedule"
    schedule_dir.mkdir(parents=True, exist_ok=True)
    (schedule_dir / "schedules.csv").write_text(rows, encoding="utf-8")


NOT_DUE_ROWS = """season,week,game_id,gameday,gametime,home_team,away_team,game_type
2026,3,2026_03_AAA_BBB,2026-09-20,20:20,AAA,BBB,REG
"""

INCOMPLETE_ROWS = """season,week,game_id,gameday,gametime,home_team,away_team,game_type
2026,3,2026_03_AAA_BBB,2026-09-20,20:20,AAA,BBB,REG
2026,3,2026_03_CCC_DDD,2026-09-20,,CCC,DDD,REG
"""

NOW_WELL_BEFORE_KICKOFF = datetime(2026, 9, 20, 18, 0, tzinfo=UTC)  # kickoff is 00:20 UTC next day


def _patch_clock(monkeypatch: pytest.MonkeyPatch, now: datetime) -> None:
    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001
            return now if tz is None else now.astimezone(tz)

    monkeypatch.setattr(cli, "datetime", _FrozenDatetime)


def test_worker_once_skips_live_fetch_when_offline_gate_says_not_due(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_schedule(tmp_path, NOT_DUE_ROWS)
    _patch_clock(monkeypatch, NOW_WELL_BEFORE_KICKOFF)
    headers_mock = AsyncMock(side_effect=AssertionError("must not fetch live when not due"))
    monkeypatch.setattr("nfl_oracle.ingest.realsports.headers_or_capture", headers_mock)
    store = _StubStore()

    result = asyncio.run(cli._worker_once(tmp_path, store, Mock(), None))

    assert result is None
    headers_mock.assert_not_awaited()
    assert len(store.runs) == 1
    assert store.runs[0]["status"] == "waiting"
    assert store.runs[0]["detail_code"] == "waiting_for_t40_offline"
    assert store.runs[0]["day"].isoformat() == "2026-09-20"


def test_worker_once_goes_live_when_offline_schedule_missing_a_kickoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_schedule(tmp_path, INCOMPLETE_ROWS)
    _patch_clock(monkeypatch, NOW_WELL_BEFORE_KICKOFF)
    sentinel = RuntimeError("reached the live path")
    headers_mock = AsyncMock(side_effect=sentinel)
    monkeypatch.setattr("nfl_oracle.ingest.realsports.headers_or_capture", headers_mock)
    store = _StubStore()

    with pytest.raises(RuntimeError, match="reached the live path"):
        asyncio.run(cli._worker_once(tmp_path, store, Mock(), None))

    headers_mock.assert_awaited_once()


def test_worker_once_goes_live_when_offline_gate_says_due(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_schedule(tmp_path, NOT_DUE_ROWS)
    # Inside the T-40 window: offline gate is due=True, which is never
    # enough by itself -- kickoff can still move -- so it must go live.
    kickoff = datetime(2026, 9, 21, 0, 20, tzinfo=UTC)
    _patch_clock(monkeypatch, kickoff - timedelta(minutes=10))
    sentinel = RuntimeError("reached the live path")
    headers_mock = AsyncMock(side_effect=sentinel)
    monkeypatch.setattr("nfl_oracle.ingest.realsports.headers_or_capture", headers_mock)
    store = _StubStore()

    with pytest.raises(RuntimeError, match="reached the live path"):
        asyncio.run(cli._worker_once(tmp_path, store, Mock(), None))

    headers_mock.assert_awaited_once()


def test_worker_once_ignores_offline_gate_when_a_day_is_explicitly_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_schedule(tmp_path, NOT_DUE_ROWS)
    _patch_clock(monkeypatch, NOW_WELL_BEFORE_KICKOFF)
    sentinel = RuntimeError("reached the live path")
    headers_mock = AsyncMock(side_effect=sentinel)
    monkeypatch.setattr("nfl_oracle.ingest.realsports.headers_or_capture", headers_mock)
    store = _StubStore()

    with pytest.raises(RuntimeError, match="reached the live path"):
        asyncio.run(
            cli._worker_once(tmp_path, store, Mock(), datetime(2026, 9, 20, tzinfo=UTC).date())
        )

    headers_mock.assert_awaited_once()


def test_worker_once_goes_live_when_no_offline_schedule_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_clock(monkeypatch, NOW_WELL_BEFORE_KICKOFF)
    sentinel = RuntimeError("reached the live path")
    headers_mock = AsyncMock(side_effect=sentinel)
    monkeypatch.setattr("nfl_oracle.ingest.realsports.headers_or_capture", headers_mock)
    store = _StubStore()

    with pytest.raises(RuntimeError, match="reached the live path"):
        asyncio.run(cli._worker_once(tmp_path, store, Mock(), None))

    headers_mock.assert_awaited_once()

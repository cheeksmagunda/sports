"""#267: the poll loop's T-40 gate must not make live calls when not due."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine

from nfl_oracle.recommendations import cli
from nfl_oracle.recommendations.store import RecommendationStore, migrate


def _write_schedule(project: Path, *rows: tuple[str, str, str]) -> None:
    """Write a schedules.csv with one row per (season, gameday, gametime)."""
    schedule_dir = project / "data" / "schedule"
    schedule_dir.mkdir(parents=True, exist_ok=True)
    header = "season,week,game_id,gameday,home_team,away_team,game_type,gametime\n"
    lines = [
        f"{season},4,{season}_04_AAA_BBB,{gameday},AAA,BBB,REG,{gametime}"
        for season, gameday, gametime in rows
    ]
    (schedule_dir / "schedules.csv").write_text(header + "\n".join(lines) + "\n")


def _setup_store(tmp_path: Path) -> RecommendationStore:
    engine = create_engine(f"sqlite:///{tmp_path / 'decisions.db'}")
    migrate(engine)
    return RecommendationStore(engine, writable=True)


def test_offline_gate_blocks_live_headers_when_not_due(tmp_path, monkeypatch) -> None:
    # Ten days out is comfortably more than T-40 away no matter when this
    # runs. Season is the real current year, matching what
    # _offline_t40_gate filters by -- not future.year, which could roll
    # into next calendar year in late December.
    now = datetime.now(UTC)
    future = now + timedelta(days=10)
    _write_schedule(
        tmp_path,
        (str(now.year), future.date().isoformat(), f"{future.hour:02d}:{future.minute:02d}"),
    )
    store = _setup_store(tmp_path)
    headers_mock = AsyncMock(
        side_effect=AssertionError("headers_or_capture must not run when offline gate says not due")
    )
    monkeypatch.setattr("nfl_oracle.ingest.realsports.headers_or_capture", headers_mock)

    result = asyncio.run(cli._worker_once(tmp_path, store, pipeline=None, requested_day=None))

    assert result is None
    headers_mock.assert_not_awaited()
    record = store.latest_run(future.date())
    assert record["status"] == "waiting"
    assert record["detail_code"] == "waiting_for_t40_offline"
    assert record["details"]["source"] == "offline_schedule"
    assert "next_freeze" in record["details"]
    assert "cutoff_at" in record["details"]


def test_offline_gate_due_for_sunday_night_game_after_utc_rolls_to_monday(tmp_path) -> None:
    # Regression for the ET/UTC date-boundary bug: a 20:15 ET Sunday-night
    # kickoff is 00:15Z Monday (EDT). At `now` = Monday 00:05Z (Sunday
    # 20:05 ET, ten minutes before kickoff, well past the T-40 due point),
    # comparing the schedule's ET `gameday` against a UTC `now.date()`
    # would wrongly skip this game and fall back to the far-future
    # Thursday game below, reporting "not due" while the real next
    # kickoff is ten minutes away. _offline_t40_gate must report due=True
    # for the Sunday game, not "not due" for Thursday.
    now = datetime(2026, 9, 21, 0, 5, tzinfo=UTC)
    _write_schedule(
        tmp_path,
        ("2026", "2026-09-24", "20:15"),  # next Thursday -- must not win
        ("2026", "2026-09-20", "20:15"),  # tonight's SNF -- must win, and be due
    )

    gate = cli._offline_t40_gate(tmp_path, now)

    assert gate is not None
    gameday, due, details = gate
    assert gameday == date(2026, 9, 20)
    assert due is True
    assert details["cutoff_at"] == "2026-09-21T00:15:00+00:00"


def test_offline_gate_falls_through_when_schedule_missing(tmp_path, monkeypatch) -> None:
    # No data/schedule/schedules.csv at all: the gate must not claim "not due".
    store = _setup_store(tmp_path)
    headers_mock = AsyncMock(side_effect=RuntimeError("reached the live path as expected"))
    monkeypatch.setattr("nfl_oracle.ingest.realsports.headers_or_capture", headers_mock)

    with pytest.raises(RuntimeError, match="reached the live path as expected"):
        asyncio.run(cli._worker_once(tmp_path, store, pipeline=None, requested_day=None))

    headers_mock.assert_awaited_once()


def test_offline_gate_skipped_for_explicit_requested_day(tmp_path, monkeypatch) -> None:
    # An operator-triggered manual run (requested_day set) always uses the
    # live/authoritative path, even though the offline schedule would say
    # "not due" for the soonest upcoming game.
    now = datetime.now(UTC)
    future = now + timedelta(days=10)
    _write_schedule(
        tmp_path,
        (str(now.year), future.date().isoformat(), f"{future.hour:02d}:{future.minute:02d}"),
    )
    store = _setup_store(tmp_path)
    headers_mock = AsyncMock(side_effect=RuntimeError("reached the live path as expected"))
    monkeypatch.setattr("nfl_oracle.ingest.realsports.headers_or_capture", headers_mock)

    with pytest.raises(RuntimeError, match="reached the live path as expected"):
        asyncio.run(cli._worker_once(tmp_path, store, pipeline=None, requested_day=future.date()))

    headers_mock.assert_awaited_once()

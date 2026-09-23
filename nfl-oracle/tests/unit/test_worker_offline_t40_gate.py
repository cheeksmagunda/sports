"""#267: the poll loop's T-40 gate must not make live calls when not due."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine

from nfl_oracle.recommendations import cli
from nfl_oracle.recommendations.store import RecommendationStore, migrate


def _write_schedule(project: Path, row_gameday: str, gametime: str) -> None:
    schedule_dir = project / "data" / "schedule"
    schedule_dir.mkdir(parents=True, exist_ok=True)
    header = "season,week,game_id,gameday,home_team,away_team,game_type,gametime\n"
    row = f"2026,4,2026_04_AAA_BBB,{row_gameday},AAA,BBB,REG,{gametime}\n"
    (schedule_dir / "schedules.csv").write_text(header + row)


def _setup_store(tmp_path: Path) -> RecommendationStore:
    engine = create_engine(f"sqlite:///{tmp_path / 'decisions.db'}")
    migrate(engine)
    return RecommendationStore(engine, writable=True)


def test_offline_gate_blocks_live_headers_when_not_due(tmp_path, monkeypatch) -> None:
    # Ten days out is comfortably more than T-40 away no matter when this runs.
    future = datetime.now(UTC) + timedelta(days=10)
    _write_schedule(tmp_path, future.date().isoformat(), f"{future.hour:02d}:{future.minute:02d}")
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
    future = datetime.now(UTC) + timedelta(days=10)
    _write_schedule(tmp_path, future.date().isoformat(), f"{future.hour:02d}:{future.minute:02d}")
    store = _setup_store(tmp_path)
    headers_mock = AsyncMock(side_effect=RuntimeError("reached the live path as expected"))
    monkeypatch.setattr("nfl_oracle.ingest.realsports.headers_or_capture", headers_mock)

    with pytest.raises(RuntimeError, match="reached the live path as expected"):
        asyncio.run(cli._worker_once(tmp_path, store, pipeline=None, requested_day=future.date()))

    headers_mock.assert_awaited_once()

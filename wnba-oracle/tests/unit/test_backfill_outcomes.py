"""Truthful Real Sports historical-backfill completion semantics."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from wnba_oracle.ingest import backfill
from wnba_oracle.ingest.contest_stats import ContestRetryExhausted, ContestUnavailable
from wnba_oracle.ingest.realsports import PlatformAuthRequired


def _run_with_stats_result(monkeypatch, side_effect: Exception) -> int:
    monkeypatch.setenv("WNBA_DEVICE_UUID", "test-device")
    with (
        patch.object(
            backfill,
            "headers_or_capture",
            new=AsyncMock(return_value=MagicMock()),
        ),
        patch.object(backfill, "_force_reauth", return_value=MagicMock()),
        patch.object(backfill, "fetch_contest_stats", side_effect=side_effect),
        patch.object(backfill.time, "sleep"),
    ):
        return backfill.run_historical_backfill(
            start_id=2,
            stop_id=1,
            pause_seconds=0,
            dry_run=True,
        )


def test_historical_auth_failure_returns_nonzero(monkeypatch) -> None:
    rc = _run_with_stats_result(monkeypatch, PlatformAuthRequired("expired"))

    assert rc == 1


def test_historical_unavailable_window_is_successful_zero_row_noop(monkeypatch) -> None:
    rc = _run_with_stats_result(monkeypatch, ContestUnavailable("not a WNBA contest"))

    assert rc == 0


def test_historical_retry_exhaustion_returns_nonzero(monkeypatch) -> None:
    rc = _run_with_stats_result(monkeypatch, ContestRetryExhausted("rate limited"))

    assert rc == 1

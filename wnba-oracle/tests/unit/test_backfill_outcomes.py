"""Truthful Real Sports historical-backfill completion semantics."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from wnba_oracle.ingest import backfill
from wnba_oracle.ingest.contest_stats import (
    ContestNotFinalized,
    ContestRetryExhausted,
    ContestUnavailable,
)
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


def _walk_top_cid(monkeypatch, stats: dict[str, object]) -> tuple[int, dict[str, MagicMock]]:
    """Walk a one-contest window (the day-close top_cid) with persistence on."""
    monkeypatch.setenv("WNBA_DEVICE_UUID", "test-device")
    entries = [MagicMock()]
    with (
        patch.object(
            backfill,
            "headers_or_capture",
            new=AsyncMock(return_value=MagicMock()),
        ),
        patch.object(backfill, "_force_reauth", return_value=MagicMock()),
        patch.object(
            backfill, "get_settings", return_value=MagicMock(database_url="postgresql://x")
        ),
        patch.object(backfill, "fetch_contest_stats", **stats) as fetch_stats,
        patch.object(backfill, "fetch_contest_entries", return_value=entries) as fetch_entries,
        patch.object(backfill, "persist_labels") as persist_labels,
        patch.object(backfill, "persist_leaderboard_entries") as persist_entries,
        patch.object(backfill, "persist_supplemental_labels", return_value=0),
        patch.object(backfill, "labels_from_leaderboard_entries", return_value=[]),
        patch.object(backfill.time, "sleep"),
    ):
        rc = backfill.run_historical_backfill(
            start_id=2192,
            stop_id=2192,
            pause_seconds=0,
            dry_run=False,
        )
    assert fetch_stats.call_args.kwargs["require_finalized"] is True
    return rc, {
        "fetch_entries": fetch_entries,
        "persist_labels": persist_labels,
        "persist_entries": persist_entries,
    }


def test_unfinalized_contest_is_skipped_not_persisted(monkeypatch) -> None:
    """Issue #243: a pre-game / in-progress contest reached by the walk is
    logged skip_not_finalized and writes neither labels nor leaderboard."""
    rc, mocks = _walk_top_cid(
        monkeypatch, {"side_effect": ContestNotFinalized("contest 2192 isFinalized=False")}
    )

    assert rc == 0
    mocks["fetch_entries"].assert_not_called()
    mocks["persist_labels"].assert_not_called()
    mocks["persist_entries"].assert_not_called()


def test_finalized_top_cid_is_still_kept(monkeypatch) -> None:
    labels = [MagicMock(slate_date="2026-09-23")]
    rc, mocks = _walk_top_cid(monkeypatch, {"return_value": labels})

    assert rc == 0
    mocks["persist_labels"].assert_called_once_with(labels)
    mocks["persist_entries"].assert_called_once()

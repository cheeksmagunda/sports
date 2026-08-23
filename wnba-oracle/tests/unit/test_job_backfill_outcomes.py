"""Truthful completion semantics for the on-demand enrichment backfill."""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

from wnba_oracle.scheduler import job_backfill

SLATE_WITH_EXISTING = dt.date(2026, 5, 26)
HISTORICAL_SLATE = dt.date(2026, 5, 25)


def _run_backfill(
    existing_processor: MagicMock,
    historical_processor: MagicMock,
) -> tuple[int, MagicMock, MagicMock]:
    connection = MagicMock()
    logger = MagicMock()
    settings = MagicMock(log_level="INFO", database_url="postgresql://test")
    with (
        patch.object(job_backfill, "log", logger),
        patch.object(job_backfill, "get_settings", return_value=settings),
        patch.object(job_backfill, "configure_logging"),
        patch.object(job_backfill, "read_game_logs", return_value=[{"game_id": "fixture"}]),
        patch.object(job_backfill, "get_engine", return_value=MagicMock()),
        patch.object(job_backfill, "build_opp_dvp_lookup", return_value={}),
        patch.object(job_backfill.psycopg, "connect", return_value=connection),
        patch.object(
            job_backfill,
            "_get_all_slate_dates",
            return_value=[SLATE_WITH_EXISTING, HISTORICAL_SLATE],
        ),
        patch.object(
            job_backfill,
            "_get_existing_enrichment_dates",
            return_value={SLATE_WITH_EXISTING},
        ),
        patch.object(job_backfill, "_get_name_to_team_map", return_value={}),
        patch.object(job_backfill, "build_head_feature_lookup", return_value={}),
        patch.object(job_backfill, "_process_existing_slate", existing_processor),
        patch.object(job_backfill, "_process_historical_slate", historical_processor),
    ):
        exit_code = job_backfill.main()
    return exit_code, connection, logger


def test_existing_enrichment_dates_preserve_database_date_type() -> None:
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [(SLATE_WITH_EXISTING,)]

    dates = job_backfill._get_existing_enrichment_dates(connection)

    assert dates == {SLATE_WITH_EXISTING}
    cursor.execute.assert_called_once_with("SELECT DISTINCT slate_date FROM job1_enrichment")


def test_backfill_success_returns_zero() -> None:
    existing = MagicMock(return_value=2)
    historical = MagicMock(return_value=3)

    exit_code, connection, logger = _run_backfill(existing, historical)

    assert exit_code == 0
    existing.assert_called_once()
    historical.assert_called_once()
    connection.close.assert_called_once()
    logger.error.assert_not_called()
    logger.info.assert_any_call(
        "backfill_done",
        inserted=3,
        updated=2,
        attempted_slates=2,
        failed_slates=0,
        failed_feature_builds=0,
        failed_required_writes=0,
    )


def test_backfill_partial_write_failure_preserves_progress_and_returns_nonzero() -> None:
    existing = MagicMock(side_effect=RuntimeError("write failed"))
    historical = MagicMock(return_value=3)

    exit_code, connection, logger = _run_backfill(existing, historical)

    assert exit_code == 1
    existing.assert_called_once()
    historical.assert_called_once()
    connection.close.assert_called_once()
    logger.error.assert_called_once_with(
        "backfill_failed",
        inserted=3,
        updated=0,
        attempted_slates=2,
        failed_slates=1,
        failed_feature_builds=0,
        failed_required_writes=1,
    )


def test_backfill_total_write_failure_returns_nonzero() -> None:
    existing = MagicMock(side_effect=RuntimeError("update failed"))
    historical = MagicMock(side_effect=RuntimeError("insert failed"))

    exit_code, connection, logger = _run_backfill(existing, historical)

    assert exit_code == 1
    existing.assert_called_once()
    historical.assert_called_once()
    connection.close.assert_called_once()
    logger.error.assert_called_once_with(
        "backfill_failed",
        inserted=0,
        updated=0,
        attempted_slates=2,
        failed_slates=2,
        failed_feature_builds=0,
        failed_required_writes=2,
    )


def test_backfill_empty_game_log_corpus_fails_before_database_access() -> None:
    logger = MagicMock()
    settings = MagicMock(log_level="INFO", database_url="postgresql://test")
    with (
        patch.object(job_backfill, "log", logger),
        patch.object(job_backfill, "get_settings", return_value=settings),
        patch.object(job_backfill, "configure_logging"),
        patch.object(job_backfill, "read_game_logs", return_value=[]),
        patch.object(job_backfill, "get_engine") as get_engine,
        patch.object(job_backfill.psycopg, "connect") as connect,
    ):
        exit_code = job_backfill.main()

    assert exit_code == 1
    get_engine.assert_not_called()
    connect.assert_not_called()
    logger.error.assert_called_once_with("backfill_failed", reason="game_log_corpus_empty")


def test_backfill_empty_eligible_slate_set_fails_truthfully() -> None:
    connection = MagicMock()
    logger = MagicMock()
    settings = MagicMock(log_level="INFO", database_url="postgresql://test")
    with (
        patch.object(job_backfill, "log", logger),
        patch.object(job_backfill, "get_settings", return_value=settings),
        patch.object(job_backfill, "configure_logging"),
        patch.object(job_backfill, "read_game_logs", return_value=[{"game_id": "fixture"}]),
        patch.object(job_backfill, "get_engine", return_value=MagicMock()),
        patch.object(job_backfill, "build_opp_dvp_lookup", return_value={}),
        patch.object(job_backfill.psycopg, "connect", return_value=connection),
        patch.object(job_backfill, "_get_all_slate_dates", return_value=[]),
        patch.object(job_backfill, "_get_existing_enrichment_dates", return_value=set()),
        patch.object(job_backfill, "_get_name_to_team_map", return_value={}),
    ):
        exit_code = job_backfill.main()

    assert exit_code == 1
    connection.close.assert_called_once()
    logger.error.assert_called_once_with("backfill_failed", reason="eligible_slate_set_empty")

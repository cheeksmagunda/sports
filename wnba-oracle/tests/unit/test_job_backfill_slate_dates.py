"""Regression: slate_date type normalization for backfill (#312)."""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

import pytest

from wnba_oracle.scheduler import job_backfill


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (dt.date(2026, 7, 14), "2026-07-14"),
        (dt.datetime(2026, 7, 14, 12, 0, 0), "2026-07-14"),
        ("2026-07-14", "2026-07-14"),
        ("2026-07-14T00:00:00Z", "2026-07-14"),
        (" 2026-07-14 ", "2026-07-14"),
        (None, None),
        ("", None),
    ],
)
def test_as_iso_slate_date_normalizes_date_and_str(
    raw: dt.date | dt.datetime | str | None, expected: str | None
) -> None:
    assert job_backfill._as_iso_slate_date(raw) == expected


def test_get_all_slate_dates_coerces_varchar_strings() -> None:
    """slate_labels.slate_date is VARCHAR; psycopg returns str."""
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [("2026-07-14",), ("2026-07-15",)]

    dates = job_backfill._get_all_slate_dates(connection)

    assert dates == ["2026-07-14", "2026-07-15"]


def test_get_existing_enrichment_dates_coerces_date_objects() -> None:
    """job1_enrichment.slate_date is DATE; psycopg returns datetime.date."""
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [(dt.date(2026, 5, 26),)]

    dates = job_backfill._get_existing_enrichment_dates(connection)

    assert dates == {"2026-05-26"}


def test_backfill_passes_iso_string_not_isoformat_attr() -> None:
    """#312: VARCHAR slate dates must not call .isoformat() (AttributeError)."""
    connection = MagicMock()
    logger = MagicMock()
    settings = MagicMock(log_level="INFO", database_url="postgresql://test")
    build_hf = MagicMock(return_value={})
    existing_processor = MagicMock(return_value=1)
    historical_processor = MagicMock(return_value=0)

    with (
        patch.object(job_backfill, "log", logger),
        patch.object(job_backfill, "get_settings", return_value=settings),
        patch.object(job_backfill, "configure_logging"),
        patch.object(job_backfill, "read_game_logs", return_value=[{"game_id": "fixture"}]),
        patch.object(job_backfill, "get_engine", return_value=MagicMock()),
        patch.object(job_backfill, "build_opp_dvp_lookup", return_value={}),
        patch.object(job_backfill.psycopg, "connect", return_value=connection),
        patch.object(job_backfill, "_get_all_slate_dates", return_value=["2026-07-14"]),
        patch.object(job_backfill, "_get_existing_enrichment_dates", return_value={"2026-07-14"}),
        patch.object(job_backfill, "_get_name_to_team_map", return_value={}),
        patch.object(job_backfill, "build_head_feature_lookup", build_hf),
        patch.object(job_backfill, "_process_existing_slate", existing_processor),
        patch.object(job_backfill, "_process_historical_slate", historical_processor),
    ):
        exit_code = job_backfill.main()

    assert exit_code == 0
    build_hf.assert_called_once()
    kwargs = build_hf.call_args.kwargs
    assert kwargs["slate_date"] == "2026-07-14"
    assert isinstance(kwargs["slate_date"], str)
    existing_processor.assert_called_once()
    historical_processor.assert_not_called()

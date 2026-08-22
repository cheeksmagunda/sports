"""Truthful completion semantics for required and optional day-close work."""

from __future__ import annotations

import datetime as dt
from typing import Any
from unittest.mock import MagicMock, patch

from oracle_core.jobs import JobStatus

from wnba_oracle.scheduler import job_dayclose


def _success_steps() -> list[Any]:
    return [
        patch.object(job_dayclose, "get_settings", return_value=MagicMock(database_url="x")),
        patch.object(job_dayclose, "discover_wnba_contest_id", return_value=2100),
        patch.object(job_dayclose, "run_historical_backfill", return_value=0),
        patch.object(job_dayclose, "_audit_label_coverage", return_value={"status": "success"}),
        patch.object(job_dayclose, "_auto_record_placement", return_value={"status": "success"}),
        patch.object(job_dayclose, "_backfill_shadow_results", return_value={"status": "success"}),
        patch.object(
            job_dayclose, "_refresh_current_game_logs", return_value={"status": "success"}
        ),
        patch.object(
            job_dayclose, "_cleanup_append_only_tables", return_value={"status": "success"}
        ),
    ]


def test_all_required_and_optional_steps_complete_successfully() -> None:
    patches = _success_steps()
    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patches[4],
        patches[5],
        patches[6],
        patches[7],
    ):
        result = job_dayclose.run()

    assert result.status is JobStatus.SUCCESS
    assert set(result.details["substeps"]) == {
        "contest_discovery",
        "historical_backfill",
        "label_coverage",
        "placement_capture",
        "shadow_results",
        "game_log_refresh",
        "retention_cleanup",
    }


def test_required_game_log_failure_fails_dayclose() -> None:
    patches = _success_steps()
    patches[6] = patch.object(
        job_dayclose, "_refresh_current_game_logs", side_effect=RuntimeError("unavailable")
    )
    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patches[4],
        patches[5],
        patches[6],
        patches[7],
    ):
        result = job_dayclose.run()

    assert result.status is JobStatus.FAILED
    assert result.exit_code == 1
    assert result.details["required_failures"] == ["game_log_refresh"]
    assert result.details["substeps"]["game_log_refresh"] == {
        "status": "failed",
        "error_type": "RuntimeError",
    }


def test_game_log_refresh_requires_rows_during_active_season() -> None:
    with (
        patch.object(job_dayclose, "current_slate_date", return_value=dt.date(2026, 8, 22)),
        patch(
            "wnba_oracle.ingest.minutes_backfill.refresh_game_logs",
            return_value=12,
        ) as refresh,
    ):
        outcome = job_dayclose._refresh_current_game_logs()

    refresh.assert_called_once_with(["2026"], require_nonempty=True)
    assert outcome["active_season_expected"] is True
    assert outcome["rows"] == 12


def test_game_log_refresh_allows_offseason_zero_row_noop() -> None:
    with (
        patch.object(job_dayclose, "current_slate_date", return_value=dt.date(2027, 1, 15)),
        patch(
            "wnba_oracle.ingest.minutes_backfill.refresh_game_logs",
            return_value=0,
        ) as refresh,
    ):
        outcome = job_dayclose._refresh_current_game_logs()

    refresh.assert_called_once_with(["2027"], require_nonempty=False)
    assert outcome == {
        "status": "success",
        "season": "2027",
        "rows": 0,
        "active_season_expected": False,
    }


def test_required_historical_backfill_nonzero_fails_dayclose() -> None:
    patches = _success_steps()
    patches[2] = patch.object(job_dayclose, "run_historical_backfill", return_value=1)
    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patches[4],
        patches[5],
        patches[6],
        patches[7],
    ):
        result = job_dayclose.run()

    assert result.status is JobStatus.FAILED
    assert result.exit_code == 1
    assert result.details["required_failures"] == ["historical_backfill"]
    assert result.details["substeps"]["historical_backfill"]["status"] == "failed"
    assert result.details["substeps"]["historical_backfill"]["source_exit_code"] == 1


def test_required_historical_backfill_exception_is_durable_failure() -> None:
    patches = _success_steps()
    patches[2] = patch.object(
        job_dayclose,
        "run_historical_backfill",
        side_effect=RuntimeError("upstream unavailable"),
    )
    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patches[4],
        patches[5],
        patches[6],
        patches[7],
    ):
        result = job_dayclose.run()

    assert result.status is JobStatus.FAILED
    assert result.exit_code == 1
    assert result.details["required_failures"] == ["historical_backfill"]
    assert result.details["substeps"]["historical_backfill"] == {
        "status": "failed",
        "error_type": "RuntimeError",
    }


def test_optional_shadow_failure_is_persisted_as_degraded() -> None:
    patches = _success_steps()
    patches[5] = patch.object(
        job_dayclose, "_backfill_shadow_results", side_effect=RuntimeError("unavailable")
    )
    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patches[4],
        patches[5],
        patches[6],
        patches[7],
    ):
        result = job_dayclose.run()

    assert result.status is JobStatus.DEGRADED
    assert result.exit_code == 2
    assert result.details["degraded_substeps"] == ["shadow_results"]


def test_missing_placement_data_is_degraded_not_green() -> None:
    patches = _success_steps()
    patches[4] = patch.object(
        job_dayclose,
        "_auto_record_placement",
        return_value={"status": "degraded", "reason": "missing_labels_or_leaderboard"},
    )
    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patches[4],
        patches[5],
        patches[6],
        patches[7],
    ):
        result = job_dayclose.run()

    assert result.status is JobStatus.DEGRADED
    assert result.details["degraded_substeps"] == ["placement_capture"]

"""Production cron entry points fail closed before running without dependencies."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from wnba_oracle.common.settings import Settings
from wnba_oracle.scheduler import cron


def _run(job: str, settings: Settings, *, role: str | None) -> tuple[int, MagicMock]:
    logger = MagicMock()
    environment = {} if role is None else {"WNBA_CRON_ROLE": role}
    with (
        patch.dict("os.environ", environment, clear=True),
        patch("sys.argv", ["oracle-cron", "--job", job]),
        patch("wnba_oracle.scheduler.cron.get_settings", return_value=settings),
        patch("wnba_oracle.scheduler.cron.get_logger", return_value=logger),
    ):
        result = cron.main()
    return result, logger


def test_production_requires_explicit_runtime_role() -> None:
    result, logger = _run(
        "job1late",
        Settings(ENV="prod", DATABASE_URL="postgresql://configured"),
        role=None,
    )

    assert result == 1
    logger.critical.assert_called_once_with(
        "cron_role_unset_abort",
        job="job1late",
        msg="WNBA_CRON_ROLE is required in production",
    )


def test_role_mismatch_precedes_dependency_validation() -> None:
    result, logger = _run("job1", Settings(ENV="prod"), role="job2")

    assert result == 1
    logger.critical.assert_called_once_with(
        "cron_role_mismatch_abort",
        expected_role="job2",
        actual_job="job1",
        msg="WNBA_CRON_ROLE does not match the selected job",
    )


@pytest.mark.parametrize(
    ("job", "settings", "missing"),
    [
        (
            "job1",
            Settings(ENV="prod", REALSPORTS_STORAGE_STATE_B64GZ="configured"),
            ["DATABASE_URL"],
        ),
        (
            "job1games",
            Settings(ENV="prod", DATABASE_URL="postgresql://configured"),
            ["REALSPORTS_STORAGE_STATE_B64GZ"],
        ),
        (
            "job2",
            Settings(
                ENV="prod",
                DATABASE_URL="postgresql://configured",
                WNBA_ORACLE_MODEL_ARTIFACT_SHA="a" * 64,
            ),
            ["REDIS_URL"],
        ),
    ],
)
def test_production_missing_dependencies_fail_value_free(
    job: str,
    settings: Settings,
    missing: list[str],
) -> None:
    result, logger = _run(job, settings, role=job)

    assert result == 1
    logger.critical.assert_called_once_with(
        "cron_required_environment_missing",
        job=job,
        role=job,
        missing=missing,
        msg="Required production configuration is absent",
    )
    serialized = json.dumps(logger.critical.call_args.kwargs, sort_keys=True)
    assert "postgresql://configured" not in serialized
    assert "a" * 64 not in serialized


def test_development_keeps_lightweight_dispatch() -> None:
    with patch("wnba_oracle.scheduler.job1.main_lite", return_value=0) as job1late:
        result, logger = _run("job1late", Settings(), role=None)

    assert result == 0
    job1late.assert_called_once()
    logger.critical.assert_not_called()

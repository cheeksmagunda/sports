"""Acceptance tests against real PostgreSQL and Redis services."""

from __future__ import annotations

import datetime as dt
import os
import uuid
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from oracle_core.jobs import JobContext, JobResult
from oracle_core.storage import create_redis_client

from wnba_oracle.common.db_utils import normalize_postgres_url
from wnba_oracle.common.logging import get_logger
from wnba_oracle.scheduler.job_runtime import PostgresJobRunHook

pytestmark = pytest.mark.integration


def _database_url() -> str:
    value = os.environ.get("DATABASE_URL", "")
    if not value:
        pytest.fail("DATABASE_URL is required for integration tests")
    return normalize_postgres_url(value)


def _redis_url() -> str:
    value = os.environ.get("REDIS_URL", "")
    if not value:
        pytest.fail("REDIS_URL is required for integration tests")
    return value


def test_postgres_is_at_head_with_runtime_tables() -> None:
    engine = sa.create_engine(_database_url())
    try:
        with engine.connect() as connection:
            revision = connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
            tables = set(
                connection.execute(
                    sa.text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname = 'public'"
                    )
                ).scalars()
            )
    finally:
        engine.dispose()

    assert revision == "20260820_0010"
    assert {"frozen_lineups", "job_runs", "slate_labels"} <= tables


def test_degraded_job_details_are_durable() -> None:
    engine = sa.create_engine(_database_url())
    run_id = f"acceptance-{uuid.uuid4()}"
    now = dt.datetime.now(dt.UTC)
    context = JobContext(
        job_name="dayclose",
        role="dayclose",
        run_id=run_id,
        started_at=now,
        clock=lambda: now,
        logger=get_logger("test.integration.job_runtime"),
        metadata={"slate_date": now.date().isoformat()},
    )
    result = JobResult.degraded(
        "optional work degraded",
        degraded_substeps=["shadow_results"],
        substeps={"shadow_results": {"status": "degraded"}},
    )

    try:
        with patch("wnba_oracle.scheduler.job_runtime.get_engine", return_value=engine):
            hook = PostgresJobRunHook()
            hook.on_start(context)
            hook.on_complete(context, result)
        with engine.begin() as connection:
            row = connection.execute(
                sa.text(
                    "SELECT status, exit_code, details_json FROM job_runs "
                    "WHERE run_id = :run_id"
                ),
                {"run_id": run_id},
            ).one()
            connection.execute(
                sa.text("DELETE FROM job_runs WHERE run_id = :run_id"),
                {"run_id": run_id},
            )
    finally:
        engine.dispose()

    assert row.status == "degraded"
    assert row.exit_code == 2
    assert row.details_json["degraded_substeps"] == ["shadow_results"]


def test_redis_round_trip_and_atomic_lease_semantics() -> None:
    client = create_redis_client(_redis_url(), decode_responses=True)
    key = f"wnba.acceptance.{uuid.uuid4()}"
    try:
        assert client.set(key, "owner-1", nx=True, ex=30) is True
        assert client.set(key, "owner-2", nx=True, ex=30) is None
        assert client.get(key) == "owner-1"
    finally:
        client.delete(key)
        client.close()

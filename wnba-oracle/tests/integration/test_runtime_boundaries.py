"""Acceptance tests against real PostgreSQL and Redis services."""

from __future__ import annotations

import datetime as dt
import json
import os
import uuid
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from oracle_core.jobs import JobContext, JobResult
from oracle_core.storage import create_redis_client

from wnba_oracle.common.db_utils import normalize_postgres_url
from wnba_oracle.common.logging import get_logger
from wnba_oracle.scheduler.job_backfill import UPSERT_SQL as BACKFILL_UPSERT_SQL
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
            revision = connection.execute(
                sa.text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            tables = set(
                connection.execute(
                    sa.text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
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
                    "SELECT status, exit_code, details_json FROM job_runs WHERE run_id = :run_id"
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


def test_backfill_upsert_preserves_live_enrichment_fields() -> None:
    engine = sa.create_engine(_database_url())
    player_id = uuid.uuid4().int % 9_000_000_000 + 1_000_000_000
    slate_date = dt.date(2099, 12, 31)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        connection.execute(
            sa.text(
                """
                INSERT INTO job1_enrichment (
                    slate_date, player_id, real_sports_player_id, name, team,
                    opponent, position, card_boost, features_json, captured_at
                ) VALUES (
                    :slate_date, :player_id, :real_sports_player_id, :name, :team,
                    :opponent, :position, :card_boost, CAST(:features_json AS JSONB), now()
                )
                """
            ),
            {
                "slate_date": slate_date,
                "player_id": player_id,
                "real_sports_player_id": str(player_id),
                "name": "Preserved Player",
                "team": "CHI",
                "opponent": "NYL",
                "position": "G",
                "card_boost": 0.2,
                "features_json": json.dumps(
                    {
                        "head_features": None,
                        "rotowire_confirmed": 1,
                        "vegas_total": 161.5,
                    }
                ),
            },
        )
        connection.execute(
            BACKFILL_UPSERT_SQL,
            {
                "slate_date": slate_date,
                "player_id": player_id,
                "real_sports_player_id": str(player_id),
                "name": "Backfill Player",
                "team": "",
                "opponent": "",
                "position": "G",
                "card_boost": 0.0,
                "features_json": json.dumps(
                    {
                        "head_features": {"minutes_l10": 29.0},
                        "rotowire_confirmed": 0,
                        "vegas_total": 0.0,
                        "_backfilled": True,
                    }
                ),
            },
        )
        features = connection.execute(
            sa.text(
                """
                SELECT features_json FROM job1_enrichment
                WHERE slate_date = :slate_date AND player_id = :player_id
                """
            ),
            {"slate_date": slate_date, "player_id": player_id},
        ).scalar_one()
        assert features["head_features"] == {"minutes_l10": 29.0}
        assert features["rotowire_confirmed"] == 1
        assert features["vegas_total"] == 161.5
        assert "_backfilled" not in features
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()

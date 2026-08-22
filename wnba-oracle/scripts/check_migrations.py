#!/usr/bin/env python3
"""Exercise empty and existing-schema Alembic upgrades on a local PostgreSQL server."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import sqlalchemy as sa
from sqlalchemy.engine import make_url

from wnba_oracle.common.db_utils import normalize_postgres_url

WNBA_ROOT = Path(__file__).resolve().parents[1]
SAFE_HOSTS = {"127.0.0.1", "localhost", "postgres"}
PREVIOUS_REVISION = "20260820_0009"
HEAD_REVISION = "20260820_0010"


def _database_url(base_url: sa.URL, database: str) -> str:
    rendered = base_url.set(database=database).render_as_string(hide_password=False)
    return normalize_postgres_url(rendered)


def _upgrade(database_url: str, revision: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", revision],
        cwd=WNBA_ROOT,
        env=environment,
        check=True,
    )


def _verify_head(database_url: str) -> None:
    engine = sa.create_engine(database_url)
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
        if revision != HEAD_REVISION:
            raise RuntimeError(f"expected Alembic head {HEAD_REVISION}, found {revision}")
        if "job_runs" not in tables or "frozen_lineups" not in tables:
            raise RuntimeError("expected runtime tables are missing after migration")
    finally:
        engine.dispose()


def main() -> int:
    raw_admin_url = os.environ.get("POSTGRES_ADMIN_URL", "")
    if not raw_admin_url:
        raise RuntimeError("POSTGRES_ADMIN_URL must target the local acceptance server")
    admin_url = make_url(raw_admin_url)
    if admin_url.host not in SAFE_HOSTS or admin_url.database != "postgres":
        raise RuntimeError("migration acceptance is restricted to a local postgres database")

    suffix = uuid.uuid4().hex[:10]
    empty_name = f"wnba_acceptance_empty_{suffix}"
    existing_name = f"wnba_acceptance_existing_{suffix}"
    names = (empty_name, existing_name)

    with psycopg.connect(raw_admin_url, autocommit=True) as connection:
        for name in names:
            connection.execute(f'CREATE DATABASE "{name}"')

    try:
        empty_url = _database_url(admin_url, empty_name)
        _upgrade(empty_url, "head")
        _verify_head(empty_url)

        existing_url = _database_url(admin_url, existing_name)
        _upgrade(existing_url, PREVIOUS_REVISION)
        existing_engine = sa.create_engine(existing_url)
        try:
            with existing_engine.begin() as connection:
                connection.execute(
                    sa.text(
                        "INSERT INTO model_registry "
                        "(sha256, created_at, training_rows, status) "
                        "VALUES (:sha, now(), 1, 'challenger')"
                    ),
                    {"sha": "a" * 64},
                )
        finally:
            existing_engine.dispose()
        _upgrade(existing_url, "head")
        _verify_head(existing_url)
        existing_engine = sa.create_engine(existing_url)
        try:
            with existing_engine.connect() as connection:
                retained = connection.execute(
                    sa.text("SELECT count(*) FROM model_registry WHERE sha256 = :sha"),
                    {"sha": "a" * 64},
                ).scalar_one()
            if retained != 1:
                raise RuntimeError("existing-schema migration did not retain representative data")
        finally:
            existing_engine.dispose()
    finally:
        with psycopg.connect(raw_admin_url, autocommit=True) as connection:
            for name in names:
                connection.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')

    print("Migration acceptance passed for empty and existing schemas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

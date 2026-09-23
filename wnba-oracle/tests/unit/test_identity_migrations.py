from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import uuid
from contextlib import closing
from pathlib import Path

import psycopg
import pytest
import sqlalchemy as sa

WNBA_ROOT = Path(__file__).resolve().parents[2]
HEAD_REVISION = "20260920_0012"
PREVIOUS_REVISION = "20260919_0011"

pytestmark = pytest.mark.integration


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def postgres_admin_url() -> str:
    initdb = shutil.which("initdb")
    pg_ctl = shutil.which("pg_ctl")
    if not initdb or not pg_ctl:
        pytest.skip("postgres binaries not installed")

    base_dir = WNBA_ROOT / "tests" / "_postgres_identity_migrations"
    data_dir = base_dir / uuid.uuid4().hex
    port = _free_port()
    subprocess.run(
        [initdb, "-D", str(data_dir), "-A", "trust", "-U", "postgres"],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            pg_ctl,
            "-D",
            str(data_dir),
            "-w",
            "start",
            "-o",
            f"-F -p {port} -h 127.0.0.1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    url = f"postgresql://postgres@127.0.0.1:{port}/postgres"
    try:
        yield url
    finally:
        subprocess.run(
            [pg_ctl, "-D", str(data_dir), "-w", "stop", "-m", "immediate"],
            check=True,
            capture_output=True,
            text=True,
        )
        shutil.rmtree(data_dir, ignore_errors=True)


def _database_url(admin_url: str, database: str) -> str:
    return admin_url.rsplit("/", 1)[0] + f"/{database}"


def _create_database(admin_url: str, database: str) -> str:
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(f'CREATE DATABASE "{database}"')
    return _database_url(admin_url, database)


def _drop_database(admin_url: str, database: str) -> None:
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')


def _alembic(database_url: str, verb: str, revision: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", verb, revision],
        cwd=WNBA_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _revision_and_tables(database_url: str) -> tuple[str, set[str]]:
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
        return revision, tables
    finally:
        engine.dispose()


def test_migration_upgrades_empty_schema(postgres_admin_url: str) -> None:
    database = f"wnba_identity_empty_{uuid.uuid4().hex[:10]}"
    database_url = _create_database(postgres_admin_url, database)
    try:
        _alembic(database_url, "upgrade", "head")
        revision, tables = _revision_and_tables(database_url)
    finally:
        _drop_database(postgres_admin_url, database)

    assert revision == HEAD_REVISION
    assert "canonical_player_identities" in tables


def test_migration_upgrades_representative_existing_schema(postgres_admin_url: str) -> None:
    database = f"wnba_identity_existing_{uuid.uuid4().hex[:10]}"
    database_url = _create_database(postgres_admin_url, database)
    try:
        _alembic(database_url, "upgrade", PREVIOUS_REVISION)
        engine = sa.create_engine(database_url)
        try:
            with engine.begin() as connection:
                connection.execute(
                    sa.text(
                        "INSERT INTO model_registry "
                        "(sha256, created_at, training_rows, status) "
                        "VALUES (:sha, now(), 1, 'challenger')"
                    ),
                    {"sha": "b" * 64},
                )
                connection.execute(
                    sa.text(
                        """
                        INSERT INTO job1_enrichment (
                            slate_date, player_id, real_sports_player_id, name, team,
                            opponent, position, card_boost, features_json, captured_at
                        ) VALUES (
                            DATE '2026-09-20', 42, '42', 'A. Wilson', 'LVA',
                            'NYL', 'F', 1.5, '{}'::jsonb, now()
                        )
                        """
                    )
                )
        finally:
            engine.dispose()
        _alembic(database_url, "upgrade", "head")
        engine = sa.create_engine(database_url)
        try:
            with engine.connect() as connection:
                kept_model = connection.execute(
                    sa.text("SELECT count(*) FROM model_registry WHERE sha256 = :sha"),
                    {"sha": "b" * 64},
                ).scalar_one()
                kept_enrichment = connection.execute(
                    sa.text("SELECT count(*) FROM job1_enrichment WHERE player_id = 42")
                ).scalar_one()
        finally:
            engine.dispose()
    finally:
        _drop_database(postgres_admin_url, database)

    assert kept_model == 1
    assert kept_enrichment == 1


def test_migration_downgrade_round_trip(postgres_admin_url: str) -> None:
    database = f"wnba_identity_roundtrip_{uuid.uuid4().hex[:10]}"
    database_url = _create_database(postgres_admin_url, database)
    try:
        _alembic(database_url, "upgrade", "head")
        engine = sa.create_engine(database_url)
        try:
            with engine.begin() as connection:
                connection.execute(
                    sa.text(
                        """
                        INSERT INTO canonical_player_identities (
                            real_sports_player_id, wnba_player_id, provenance,
                            provider_nba_id, real_sports_display_name,
                            real_sports_first_name, real_sports_last_name,
                            real_sports_team, wnba_full_name,
                            first_seen_at, last_seen_at
                        ) VALUES (
                            '9001', 201939, 'explicit_override',
                            NULL, 'A. Wilson', 'A''ja', 'Wilson',
                            'LVA', 'A''ja Wilson',
                            now(), now()
                        )
                        """
                    )
                )
        finally:
            engine.dispose()
        _alembic(database_url, "downgrade", PREVIOUS_REVISION)
        revision, tables = _revision_and_tables(database_url)
    finally:
        _drop_database(postgres_admin_url, database)

    assert revision == PREVIOUS_REVISION
    assert "canonical_player_identities" not in tables

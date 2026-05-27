"""normalize_postgres_url is consumed in three places (db/engine.py,
ingest/backfill.py, migrations/env.py). Test it directly so a regression
shows up in one place."""

from __future__ import annotations

from wnba_oracle.common.db_utils import normalize_postgres_url


def test_postgres_legacy_scheme_gets_driver_suffix() -> None:
    assert (
        normalize_postgres_url("postgres://u:p@h:5432/db")
        == "postgresql+psycopg://u:p@h:5432/db"
    )


def test_postgresql_no_driver_gets_psycopg_suffix() -> None:
    assert (
        normalize_postgres_url("postgresql://u:p@h:5432/db")
        == "postgresql+psycopg://u:p@h:5432/db"
    )


def test_already_qualified_url_passes_through() -> None:
    url = "postgresql+psycopg://u:p@h:5432/db"
    assert normalize_postgres_url(url) == url


def test_empty_string_passes_through() -> None:
    assert normalize_postgres_url("") == ""


def test_non_postgres_url_passes_through() -> None:
    assert normalize_postgres_url("redis://h:6379") == "redis://h:6379"

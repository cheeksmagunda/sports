"""Isolation and boundedness for application database engine factories."""

from __future__ import annotations

from unittest.mock import MagicMock

from sqlalchemy.pool import NullPool

from wnba_oracle.db import engine as db_engine


def test_health_engine_isolated_from_model_and_job_pool(monkeypatch) -> None:
    settings = MagicMock(database_url="postgresql://user:secret@example.invalid/wnba")
    expected = MagicMock()
    create_engine = MagicMock(return_value=expected)
    monkeypatch.setattr(db_engine, "get_settings", lambda: settings)
    monkeypatch.setattr(db_engine.sa, "create_engine", create_engine)
    db_engine.get_health_engine.cache_clear()
    try:
        observed = db_engine.get_health_engine()
    finally:
        db_engine.get_health_engine.cache_clear()

    assert observed is expected
    create_engine.assert_called_once_with(
        "postgresql+psycopg://user:secret@example.invalid/wnba",
        poolclass=NullPool,
        pool_pre_ping=False,
        connect_args={
            "application_name": "wnba-oracle-health",
            "connect_timeout": 5,
            "options": "-c default_transaction_read_only=on -c statement_timeout=5000",
        },
    )


def test_api_engine_bounds_serving_queries_without_changing_job_engine(monkeypatch) -> None:
    settings = MagicMock(database_url="postgresql://user:secret@example.invalid/wnba")
    expected = MagicMock()
    create_postgres_engine = MagicMock(return_value=expected)
    monkeypatch.setattr(db_engine, "get_settings", lambda: settings)
    monkeypatch.setattr(db_engine, "create_postgres_engine", create_postgres_engine)
    db_engine.get_api_engine.cache_clear()
    try:
        observed = db_engine.get_api_engine()
    finally:
        db_engine.get_api_engine.cache_clear()

    assert observed is expected
    call = create_postgres_engine.call_args
    assert call.args == (settings.database_url,)
    assert call.kwargs["pool"] == db_engine.PoolOptions(
        pool_size=4,
        max_overflow=2,
        pool_timeout=5.0,
        pool_recycle=300,
    )
    assert call.kwargs["connect_args"] == {
        "application_name": "wnba-oracle-api",
        "connect_timeout": 5,
        "options": (
            "-c default_transaction_read_only=on "
            "-c statement_timeout=10000 "
            "-c idle_in_transaction_session_timeout=10000"
        ),
    }

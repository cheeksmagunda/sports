"""SQLAlchemy engine factory + Redis client helper.

Both clients are constructed lazily on first call so unit tests can run
without DATABASE_URL / REDIS_URL set.
"""

from __future__ import annotations

from functools import lru_cache

import sqlalchemy as sa
from oracle_core.storage import (
    PoolOptions,
    create_postgres_engine,
    create_redis_client,
    normalize_postgres_url,
)
from redis import Redis
from sqlalchemy.pool import NullPool

from wnba_oracle.common.settings import get_settings


@lru_cache(maxsize=1)
def get_engine() -> sa.Engine:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL not set")
    return create_postgres_engine(
        settings.database_url,
        pool=PoolOptions(pool_size=4, max_overflow=2, pool_timeout=5.0),
        connect_args={"connect_timeout": 5},
    )


@lru_cache(maxsize=1)
def get_api_engine() -> sa.Engine:
    """Return a serving-only pool with bounded checkout, connect, and SQL work."""

    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL not set")
    return create_postgres_engine(
        settings.database_url,
        pool=PoolOptions(
            pool_size=4,
            max_overflow=2,
            pool_timeout=5.0,
            pool_recycle=300,
        ),
        connect_args={
            "application_name": "wnba-oracle-api",
            "connect_timeout": 5,
            "options": (
                "-c default_transaction_read_only=on "
                "-c statement_timeout=10000 "
                "-c idle_in_transaction_session_timeout=10000"
            ),
        },
    )


@lru_cache(maxsize=1)
def get_health_engine() -> sa.Engine:
    """Return an API-only engine whose connection and query work is bounded."""

    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL not set")
    return sa.create_engine(
        normalize_postgres_url(settings.database_url),
        poolclass=NullPool,
        pool_pre_ping=False,
        connect_args={
            "application_name": "wnba-oracle-health",
            "connect_timeout": 5,
            "options": "-c default_transaction_read_only=on -c statement_timeout=5000",
        },
    )


@lru_cache(maxsize=1)
def get_redis() -> Redis:
    settings = get_settings()
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL not set")
    return create_redis_client(settings.redis_url, decode_responses=True)

"""SQLAlchemy engine factory + Redis client helper.

Both clients are constructed lazily on first call so unit tests can run
without DATABASE_URL / REDIS_URL set.
"""

from __future__ import annotations

from functools import lru_cache

import redis
import sqlalchemy as sa
from sqlalchemy import create_engine

from wnba_oracle.common.settings import get_settings


def _normalize_pg_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


@lru_cache(maxsize=1)
def get_engine() -> sa.Engine:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL not set")
    return create_engine(
        _normalize_pg_url(settings.database_url),
        future=True,
        pool_pre_ping=True,
        pool_size=4,
        max_overflow=2,
    )


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    settings = get_settings()
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL not set")
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)

"""SQLAlchemy engine factory + Redis client helper.

Both clients are constructed lazily on first call so unit tests can run
without DATABASE_URL / REDIS_URL set.
"""

from __future__ import annotations

from functools import lru_cache

import sqlalchemy as sa
from oracle_core.storage import PoolOptions, create_postgres_engine, create_redis_client
from redis import Redis

from wnba_oracle.common.settings import get_settings


@lru_cache(maxsize=1)
def get_engine() -> sa.Engine:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL not set")
    return create_postgres_engine(
        settings.database_url,
        pool=PoolOptions(pool_size=4, max_overflow=2),
    )


@lru_cache(maxsize=1)
def get_redis() -> Redis:
    settings = get_settings()
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL not set")
    return create_redis_client(settings.redis_url, decode_responses=True)

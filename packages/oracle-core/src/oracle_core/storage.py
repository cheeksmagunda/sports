"""Provider-neutral PostgreSQL transactions and Redis-backed stores."""

from __future__ import annotations

import secrets
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar, cast

from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

T = TypeVar("T")


@dataclass(frozen=True)
class PoolOptions:
    """Portable SQLAlchemy pool controls."""

    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: float = 30.0
    pool_recycle: int = 1800
    pool_pre_ping: bool = True

    def __post_init__(self) -> None:
        if self.pool_size < 1:
            raise ValueError("pool_size must be at least 1")
        if self.max_overflow < 0:
            raise ValueError("max_overflow cannot be negative")
        if self.pool_timeout <= 0:
            raise ValueError("pool_timeout must be positive")
        if self.pool_recycle < -1:
            raise ValueError("pool_recycle must be -1 or greater")


def normalize_postgres_url(url: str) -> str:
    """Normalize common PostgreSQL URL schemes to SQLAlchemy's psycopg driver."""

    value = url.strip()
    if not value:
        raise ValueError("PostgreSQL URL is required")
    if value.startswith("postgres://"):
        return f"postgresql+psycopg://{value.removeprefix('postgres://')}"
    if value.startswith("postgresql://"):
        return f"postgresql+psycopg://{value.removeprefix('postgresql://')}"
    if value.startswith("postgresql+"):
        return value
    raise ValueError("Expected a PostgreSQL URL")


def create_postgres_engine(
    url: str,
    *,
    pool: PoolOptions | None = None,
    **engine_options: Any,
) -> Engine:
    """Create a future-style SQLAlchemy engine with conservative pool defaults."""

    options = pool or PoolOptions()
    defaults: dict[str, Any] = {
        "pool_pre_ping": options.pool_pre_ping,
        "pool_size": options.pool_size,
        "max_overflow": options.max_overflow,
        "pool_timeout": options.pool_timeout,
        "pool_recycle": options.pool_recycle,
    }
    defaults.update(engine_options)
    return create_engine(normalize_postgres_url(url), **defaults)


def create_redis_client(
    url: str,
    *,
    decode_responses: bool = False,
    health_check_interval: int = 30,
    socket_connect_timeout: float = 5.0,
    socket_timeout: float = 5.0,
    **options: Any,
) -> Redis:
    """Create a Redis client without connecting eagerly."""

    if not url.strip():
        raise ValueError("Redis URL is required")
    defaults: dict[str, Any] = {
        "decode_responses": decode_responses,
        "health_check_interval": health_check_interval,
        "socket_connect_timeout": socket_connect_timeout,
        "socket_timeout": socket_timeout,
    }
    defaults.update(options)
    return Redis.from_url(url, **defaults)


class TransactionalStore(Protocol):
    """Capability for running work inside a database transaction."""

    def transaction(self) -> AbstractContextManager[Connection]:
        """Yield a connection whose transaction commits or rolls back atomically."""


class TransactionManager:
    """Thin transaction boundary around an application-owned SQLAlchemy engine."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def transaction(self) -> Generator[Connection, None, None]:
        with self.engine.begin() as connection:
            yield connection

    def run(self, operation: Callable[[Connection], T]) -> T:
        with self.transaction() as connection:
            return operation(connection)


SqlAlchemyTransactionStore = TransactionManager


class KeyValueStore(Protocol):
    """Minimal byte-oriented store used by technical caching primitives."""

    def get(self, key: str) -> bytes | None:
        """Return a value or ``None`` when the key is absent."""

    def set(self, key: str, value: bytes, *, ttl_seconds: int | None = None) -> None:
        """Atomically set a value with an optional TTL."""

    def delete(self, key: str) -> bool:
        """Delete a key and report whether it existed."""


class RedisKeyValueStore:
    """Redis implementation of :class:`KeyValueStore`."""

    def __init__(self, client: Redis, *, prefix: str = "") -> None:
        self.client = client
        self.prefix = prefix

    def _key(self, key: str) -> str:
        return f"{self.prefix}{key}"

    def get(self, key: str) -> bytes | None:
        value = cast(bytes | str | None, self.client.get(self._key(key)))
        if value is None:
            return None
        return value.encode() if isinstance(value, str) else bytes(value)

    def set(self, key: str, value: bytes, *, ttl_seconds: int | None = None) -> None:
        if ttl_seconds is not None and ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.client.set(self._key(key), value, ex=ttl_seconds)

    def delete(self, key: str) -> bool:
        return bool(self.client.delete(self._key(key)))


@dataclass(frozen=True)
class Lease:
    """Opaque proof that a caller owns a specific distributed lease."""

    key: str
    token: str


class LeaseStore(Protocol):
    """Distributed lease capability with ownership-safe mutation."""

    def acquire(self, key: str, *, ttl_seconds: int) -> Lease | None:
        """Acquire a lease or return ``None`` when another owner holds it."""

    def renew(self, lease: Lease, *, ttl_seconds: int) -> bool:
        """Extend a lease only if its ownership token still matches."""

    def release(self, lease: Lease) -> bool:
        """Release a lease only if its ownership token still matches."""


_RENEW_LEASE = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""

_RELEASE_LEASE = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


class RedisLeaseStore:
    """Redis lease store using random ownership tokens and atomic Lua checks."""

    def __init__(self, client: Redis, *, prefix: str = "lease:") -> None:
        self.client = client
        self.prefix = prefix

    def _key(self, key: str) -> str:
        return f"{self.prefix}{key}"

    def acquire(self, key: str, *, ttl_seconds: int) -> Lease | None:
        _validate_ttl(ttl_seconds)
        lease = Lease(key=key, token=secrets.token_urlsafe(32))
        acquired = self.client.set(
            self._key(key),
            lease.token,
            nx=True,
            ex=ttl_seconds,
        )
        return lease if acquired else None

    def renew(self, lease: Lease, *, ttl_seconds: int) -> bool:
        _validate_ttl(ttl_seconds)
        return bool(
            self.client.eval(
                _RENEW_LEASE,
                1,
                self._key(lease.key),
                lease.token,
                str(ttl_seconds),
            )
        )

    def release(self, lease: Lease) -> bool:
        return bool(
            self.client.eval(
                _RELEASE_LEASE,
                1,
                self._key(lease.key),
                lease.token,
            )
        )


def _validate_ttl(ttl_seconds: int) -> None:
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")

from __future__ import annotations

from typing import Any

import pytest
from oracle_core.cache import JsonTtlCache
from oracle_core.storage import (
    Lease,
    PoolOptions,
    RedisKeyValueStore,
    RedisLeaseStore,
    TransactionManager,
    create_postgres_engine,
    create_redis_client,
    normalize_postgres_url,
)
from oracle_core.testing import FakeKeyValueStore, FakeLeaseStore
from sqlalchemy import create_engine, text


def test_postgres_url_normalization() -> None:
    assert normalize_postgres_url("postgres://u:p@host/db") == ("postgresql+psycopg://u:p@host/db")
    assert normalize_postgres_url("postgresql://host/db") == "postgresql+psycopg://host/db"
    assert normalize_postgres_url("postgresql+psycopg://host/db") == (
        "postgresql+psycopg://host/db"
    )
    with pytest.raises(ValueError):
        normalize_postgres_url("")
    with pytest.raises(ValueError):
        normalize_postgres_url("sqlite:///local.db")
    with pytest.raises(ValueError):
        PoolOptions(pool_size=0)


def test_postgres_engine_factory_forwards_pool_options(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    sentinel = object()

    def fake_create_engine(url: str, **options: Any) -> object:
        captured.update(url=url, **options)
        return sentinel

    monkeypatch.setattr("oracle_core.storage.create_engine", fake_create_engine)
    result = create_postgres_engine(
        "postgres://host/db",
        pool=PoolOptions(pool_size=3, max_overflow=4, pool_timeout=9),
        echo=True,
    )

    assert result is sentinel
    assert captured["url"] == "postgresql+psycopg://host/db"
    assert captured["pool_size"] == 3
    assert captured["max_overflow"] == 4
    assert captured["pool_timeout"] == 9
    assert captured["echo"] is True


def test_redis_factory_is_lazy_and_configured() -> None:
    client = create_redis_client("redis://localhost:6379/4", socket_timeout=7)

    assert client.connection_pool.connection_kwargs["db"] == 4
    assert client.connection_pool.connection_kwargs["socket_timeout"] == 7
    with pytest.raises(ValueError):
        create_redis_client(" ")


def test_transaction_manager_commits_and_rolls_back() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    manager = TransactionManager(engine)
    with manager.transaction() as connection:
        connection.execute(text("CREATE TABLE records (value TEXT NOT NULL)"))
    manager.run(lambda connection: connection.execute(text("INSERT INTO records VALUES ('ok')")))

    with pytest.raises(RuntimeError):
        with manager.transaction() as connection:
            connection.execute(text("INSERT INTO records VALUES ('rolled-back')"))
            raise RuntimeError("stop")

    with engine.connect() as connection:
        assert connection.execute(text("SELECT value FROM records")).scalars().all() == ["ok"]


class StubRedis:
    def __init__(self) -> None:
        self.values: dict[str, bytes | str] = {}
        self.eval_calls: list[tuple[Any, ...]] = []

    def get(self, key: str) -> bytes | str | None:
        return self.values.get(key)

    def set(self, key: str, value: bytes | str, **options: Any) -> bool:
        if options.get("nx") and key in self.values:
            return False
        self.values[key] = value
        return True

    def delete(self, key: str) -> int:
        return int(self.values.pop(key, None) is not None)

    def eval(self, script: str, count: int, key: str, token: str, *args: Any) -> int:
        self.eval_calls.append((script, count, key, token, *args))
        if self.values.get(key) != token:
            return 0
        if "del" in script:
            del self.values[key]
        return 1


def test_redis_key_value_store_and_token_owned_leases() -> None:
    client = StubRedis()
    values = RedisKeyValueStore(client, prefix="cache:")  # type: ignore[arg-type]
    values.set("one", b"value", ttl_seconds=3)
    assert values.get("one") == b"value"
    assert values.delete("one")

    leases = RedisLeaseStore(client, prefix="locks:")  # type: ignore[arg-type]
    owner = leases.acquire("daily", ttl_seconds=30)
    assert owner is not None
    assert leases.acquire("daily", ttl_seconds=30) is None
    assert not leases.release(Lease(key="daily", token="other-owner"))
    assert leases.renew(owner, ttl_seconds=60)
    assert leases.release(owner)


def test_json_cache_expiry_serialization_and_invalid_data() -> None:
    current = [10.0]
    store = FakeKeyValueStore(clock=lambda: current[0])
    cache = JsonTtlCache(store, prefix="json:")

    cache.set("key", {"z": 1, "a": True}, ttl_seconds=5)
    assert store.values["json:key"][0] == b'{"a":true,"z":1}'
    assert cache.get("key") == {"a": True, "z": 1}
    current[0] = 15.0
    assert cache.get("key") is None

    store.set("json:broken", b"not-json")
    with pytest.raises(ValueError, match="broken"):
        cache.get("broken")
    with pytest.raises(ValueError):
        cache.set("key", {}, ttl_seconds=0)


def test_fake_lease_store_rejects_stale_owner() -> None:
    current = [0.0]
    store = FakeLeaseStore(clock=lambda: current[0])
    original = store.acquire("job", ttl_seconds=2)
    assert original is not None
    current[0] = 3
    replacement = store.acquire("job", ttl_seconds=2)
    assert replacement is not None
    assert not store.release(original)
    assert store.release(replacement)

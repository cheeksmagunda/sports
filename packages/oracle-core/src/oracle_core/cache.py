"""Atomic JSON TTL caching over a technical key-value capability."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, TypeVar

from oracle_core.storage import KeyValueStore

T = TypeVar("T")


class JsonTtlCache:
    """Canonical JSON serialization with TTL enforced by the underlying store."""

    def __init__(self, store: KeyValueStore, *, prefix: str = "") -> None:
        self.store = store
        self.prefix = prefix

    def _key(self, key: str) -> str:
        return f"{self.prefix}{key}"

    def get(self, key: str) -> Any | None:
        payload = self.store.get(self._key(key))
        if payload is None:
            return None
        try:
            return json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"Cached value for {key!r} is not valid JSON") from error

    def set(self, key: str, value: Any, *, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
        self.store.set(self._key(key), payload, ttl_seconds=ttl_seconds)

    def delete(self, key: str) -> bool:
        return self.store.delete(self._key(key))

    def get_or_set(self, key: str, factory: Callable[[], T], *, ttl_seconds: int) -> T:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value, ttl_seconds=ttl_seconds)
        return value

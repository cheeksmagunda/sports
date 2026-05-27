"""File cache round-trip + TTL semantics. Mocks CACHE_DIR to a tmp_path."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def _cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    """Patch the cache module's CACHE_DIR to a tmp dir, then return it."""
    from wnba_oracle.ingest import cache

    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    return cache


def test_cache_round_trip(_cache: Any) -> None:
    body = {"players": [{"id": "1", "name": "X"}]}
    _cache.cache_put("https://example/x", {"q": "a"}, body)
    got = _cache.cache_get("https://example/x", {"q": "a"}, ttl_s=3600.0)
    assert got == body


def test_cache_miss_returns_none(_cache: Any) -> None:
    assert _cache.cache_get("https://example/x", None, ttl_s=3600.0) is None


def test_cache_ttl_expired(_cache: Any) -> None:
    body = {"a": 1}
    _cache.cache_put("https://example/y", None, body)
    # Negative TTL means anything is "too old"
    assert _cache.cache_get("https://example/y", None, ttl_s=-1.0) is None


def test_cache_key_distinguishes_params(_cache: Any) -> None:
    _cache.cache_put("https://example/z", {"q": "a"}, {"v": "alpha"})
    _cache.cache_put("https://example/z", {"q": "b"}, {"v": "beta"})
    assert _cache.cache_get("https://example/z", {"q": "a"}, ttl_s=3600.0) == {"v": "alpha"}
    assert _cache.cache_get("https://example/z", {"q": "b"}, ttl_s=3600.0) == {"v": "beta"}

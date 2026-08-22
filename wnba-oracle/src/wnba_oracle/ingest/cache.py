"""Lightweight file-system cache for ingest responses.

Caches by URL hash + day. Used to keep stats.wnba.com retries cheap and to
make probe re-runs idempotent. The cache lives under data/raw/ and is
gitignored.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

from oracle_core.artifacts import atomic_write_json, sha256_bytes
from oracle_core.cache import JsonTtlCache

from wnba_oracle.common.paths import resolve_project_root

REPO_ROOT = resolve_project_root(__file__)
CACHE_DIR = REPO_ROOT / "data" / "raw"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
_STORE_TTL_SECONDS = 30 * 24 * 3600


class _FileKeyValueStore:
    """WNBA-local file adapter for the core byte-oriented cache contract."""

    @staticmethod
    def _path(key: str) -> Path:
        return CACHE_DIR / f"{key}.json"

    def get(self, key: str) -> bytes | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            envelope = json.loads(path.read_text())
            if time.time() >= float(envelope["expires_at"]):
                path.unlink(missing_ok=True)
                return None
            return base64.b64decode(envelope["payload"])
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None

    def set(self, key: str, value: bytes, *, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds or _STORE_TTL_SECONDS
        if ttl <= 0:
            raise ValueError("ttl_seconds must be positive")
        atomic_write_json(
            self._path(key),
            {
                "expires_at": time.time() + ttl,
                "payload": base64.b64encode(value).decode("ascii"),
            },
        )

    def delete(self, key: str) -> bool:
        path = self._path(key)
        existed = path.exists()
        path.unlink(missing_ok=True)
        return existed


_CACHE = JsonTtlCache(_FileKeyValueStore())


def _key(url: str, params: dict[str, Any] | None) -> str:
    payload = json.dumps({"u": url, "p": params or {}}, sort_keys=True)
    return sha256_bytes(payload.encode())[:32]


def cache_get(url: str, params: dict[str, Any] | None, *, ttl_s: float) -> dict[str, Any] | None:
    raw = _CACHE.get(_key(url, params))
    if raw is None:
        return None
    if time.time() - raw.get("_cached_at", 0) > ttl_s:
        return None
    return raw.get("body")


def cache_put(url: str, params: dict[str, Any] | None, body: dict[str, Any]) -> None:
    _CACHE.set(
        _key(url, params),
        {"_cached_at": time.time(), "url": url, "body": body},
        ttl_seconds=_STORE_TTL_SECONDS,
    )

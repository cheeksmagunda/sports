"""Lightweight file-system cache for ingest responses.

Caches by URL hash + day. Used to keep stats.wnba.com retries cheap and to
make probe re-runs idempotent. The cache lives under data/raw/ and is
gitignored.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = REPO_ROOT / "data" / "raw"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _key(url: str, params: dict[str, Any] | None) -> str:
    payload = json.dumps({"u": url, "p": params or {}}, sort_keys=True)
    return hashlib.blake2b(payload.encode(), digest_size=16).hexdigest()


def cache_get(url: str, params: dict[str, Any] | None, *, ttl_s: float) -> dict[str, Any] | None:
    p = CACHE_DIR / f"{_key(url, params)}.json"
    if not p.exists():
        return None
    raw = json.loads(p.read_text())
    if time.time() - raw.get("_cached_at", 0) > ttl_s:
        return None
    return raw.get("body")


def cache_put(url: str, params: dict[str, Any] | None, body: dict[str, Any]) -> None:
    p = CACHE_DIR / f"{_key(url, params)}.json"
    p.write_text(json.dumps({"_cached_at": time.time(), "url": url, "body": body}))

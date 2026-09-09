"""Thin Real Sports HTTP client for NFL Corpus G (read-only).

Auth mirrors the WNBA operator-seeded Playwright session pattern without
importing any wnba_oracle domain code.
"""

from __future__ import annotations

import asyncio
import base64
import gzip
import json
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from oracle_core.artifacts import atomic_write_json
from oracle_core.http import HttpxAsyncTransport, RetryPolicy, async_request_with_retry

from nfl_oracle.common.logging import get_logger
from nfl_oracle.common.paths import resolve_project_root

SPORT = "nfl"
BASE = "https://web.realapp.com"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
TOKEN_TTL_SECONDS = 1800
DEFAULT_DEVICE_NAME = "nfl-oracle-dev-01"

log = get_logger("nfl_oracle.ingest.realsports")


class PlatformAuthRequired(RuntimeError):
    pass


class StorageStateMissing(RuntimeError):
    pass


class StorageStateStale(RuntimeError):
    pass


@dataclass(frozen=True)
class RequestHeaders:
    real_request_token: str
    real_version: str
    real_device_type: str
    real_device_uuid: str
    real_device_id: str
    real_device_name: str
    real_auth_info: str | None
    user_agent: str
    captured_at: float


def _ensure_private_directory(path: Path) -> None:
    if path.is_symlink():
        raise RuntimeError("Real Sports secret directory must not be a symbolic link")
    if path.exists() and not path.is_dir():
        raise RuntimeError("Real Sports secret directory is not a directory")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)


def _ensure_private_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Real Sports secret path must be a regular file")
    path.chmod(0o600)


def _write_private_json(path: Path, payload: Any) -> None:
    _ensure_private_directory(path.parent)
    atomic_write_json(path, payload, mode=0o600)
    path.chmod(0o600)


def project_root() -> Path:
    return resolve_project_root(__file__)


def scraper_dir() -> Path:
    override = os.environ.get("NFL_ORACLE_SCRAPER_DIR", "").strip()
    path = Path(override).expanduser() if override else project_root() / "scraper"
    _ensure_private_directory(path)
    return path


def storage_state_path() -> Path:
    override = (
        os.environ.get("REALSPORTS_STORAGE_STATE_PATH", "").strip()
        or os.environ.get("NFL_REALSPORTS_STORAGE_STATE", "").strip()
    )
    if override and not _placeholder_secret(override) and not override.startswith("{"):
        return Path(override).expanduser()
    local = scraper_dir() / "storage_state.json"
    if local.exists():
        return local
    # Optional sibling bootstrap when an operator keeps one Real Sports session
    # under wnba-oracle/scraper (path only; no WNBA domain imports).
    sibling = project_root().parent / "wnba-oracle" / "scraper" / "storage_state.json"
    if sibling.exists():
        return sibling
    return local


def token_cache_path() -> Path:
    override = (
        os.environ.get("REALSPORTS_TOKEN_CACHE_PATH", "").strip()
        or os.environ.get("NFL_REALSPORTS_TOKEN_CACHE", "").strip()
    )
    if override:
        return Path(override).expanduser()
    return scraper_dir() / "request_token_cache.json"


def _placeholder_secret(value: str) -> bool:
    return value.strip().lower() in {
        "placeholder",
        "change-me",
        "changeme",
        "todo",
        "unused",
        "not-set",
        "not_set",
    }


def _storage_state_from_text(value: str) -> dict[str, Any]:
    if value.startswith("{"):
        payload = json.loads(value)
    else:
        payload = json.loads(gzip.decompress(base64.b64decode(value, validate=True)))
    if not isinstance(payload, dict) or not isinstance(payload.get("origins"), list):
        raise ValueError("invalid storage-state structure")
    return payload


def materialize_storage_state_from_env() -> Path | None:
    values = (
        ("REALSPORTS_STORAGE_STATE_B64GZ", os.environ.get("REALSPORTS_STORAGE_STATE_B64GZ", "")),
        ("NFL_REALSPORTS_STORAGE_STATE", os.environ.get("NFL_REALSPORTS_STORAGE_STATE", "")),
    )
    configured = [(key, value.strip()) for key, value in values if value.strip()]
    if not configured:
        return None
    for key, value in configured:
        if _placeholder_secret(value):
            continue
        if key == "NFL_REALSPORTS_STORAGE_STATE" and not value.startswith("{"):
            continue
        try:
            payload = _storage_state_from_text(value)
            break
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            raise StorageStateMissing(f"{key} is set but invalid") from exc
    else:
        return None
    raw = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode()
    target = scraper_dir() / "storage_state.json"
    import tempfile

    descriptor, temporary_name = tempfile.mkstemp(prefix=".storage-state-", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
        target.chmod(0o600)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return target


def load_cached_headers() -> RequestHeaders | None:
    path = token_cache_path()
    if not path.exists():
        # Optional sibling bootstrap from a shared Real Sports token cache.
        sibling = project_root().parent / "wnba-oracle" / "scraper" / "request_token_cache.json"
        if sibling.exists():
            path = sibling
        else:
            return None
    _ensure_private_file(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if time.time() - float(raw.get("captured_at", 0)) > TOKEN_TTL_SECONDS:
        return None
    if "real-request-token" not in raw or "real-auth-info" not in raw:
        return None
    return RequestHeaders(
        real_request_token=raw["real-request-token"],
        real_version=str(raw.get("real-version", "31")),
        real_device_type=str(raw.get("real-device-type", "desktop_web")),
        real_device_uuid=str(raw["real-device-uuid"]),
        real_device_id=str(raw.get("real-device-id", raw["real-device-uuid"])),
        real_device_name=str(raw.get("real-device-name", DEFAULT_DEVICE_NAME)),
        real_auth_info=raw.get("real-auth-info"),
        user_agent=str(raw.get("user-agent", DEFAULT_USER_AGENT)),
        captured_at=float(raw["captured_at"]),
    )


def _save_cached_headers(payload: dict[str, Any]) -> None:
    data = dict(payload)
    data["captured_at"] = time.time()
    _write_private_json(token_cache_path(), data)


def _device_uuid() -> str:
    return (
        os.environ.get("NFL_DEVICE_UUID", "").strip()
        or os.environ.get("WNBA_DEVICE_UUID", "").strip()
        or "00000000-0000-4000-8000-0000000000nfl"
    )


def _device_name() -> str:
    return (
        os.environ.get("NFL_DEVICE_NAME", "").strip()
        or os.environ.get("WNBA_DEVICE_NAME", "").strip()
        or DEFAULT_DEVICE_NAME
    )


async def capture_live_headers(
    device_uuid: str | None = None,
    device_name: str | None = None,
    *,
    headed: bool = False,
) -> RequestHeaders:
    materialize_storage_state_from_env()
    state_path = storage_state_path()
    if not state_path.exists():
        raise StorageStateMissing(
            "Real Sports storage state is missing. Recover it with an ordinary "
            "interactive browser, then seed scraper/storage_state.json or "
            "REALSPORTS_STORAGE_STATE_B64GZ."
        )
    _ensure_private_file(state_path)
    device_uuid = device_uuid or _device_uuid()
    device_name = device_name or _device_name()

    from playwright.async_api import async_playwright

    captured: dict[str, str] = {}
    done = asyncio.Event()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not headed)
        ctx = await browser.new_context(
            viewport={"width": 599, "height": 868},
            storage_state=str(state_path),
            user_agent=DEFAULT_USER_AGENT,
        )

        async def on_request(req: Any) -> None:
            if "realapp.com" not in req.url:
                return
            headers = req.headers
            if "real-request-token" in headers and "real-auth-info" in headers and not captured:
                for key, value in headers.items():
                    captured[key.lower()] = value
                captured["captured_at_url"] = req.url
                done.set()

        ctx.on("request", on_request)
        page = await ctx.new_page()
        try:
            await page.goto(
                "https://realsports.io/?sport=nfl",
                wait_until="domcontentloaded",
                timeout=25000,
            )
        except Exception:
            pass
        try:
            await asyncio.wait_for(done.wait(), timeout=20.0)
        except TimeoutError as exc:
            await browser.close()
            raise StorageStateStale(
                "Did not capture authenticated headers within 20s. Session may be expired."
            ) from exc
        refreshed_state = await ctx.storage_state()
        local = scraper_dir() / "storage_state.json"
        if (
            state_path.resolve() == local.resolve()
            or os.environ.get("NFL_REALSPORTS_WRITE_STATE") == "1"
        ):
            _write_private_json(local, refreshed_state)
        await browser.close()

    captured["real-device-uuid"] = device_uuid
    captured.setdefault("real-device-id", device_uuid)
    captured["real-device-name"] = device_name
    captured.setdefault("real-device-type", "desktop_web")
    captured.setdefault("real-version", "31")
    captured.setdefault("user-agent", DEFAULT_USER_AGENT)
    _save_cached_headers(captured)
    headers = load_cached_headers()
    if headers is None:
        raise RuntimeError("Captured headers but failed to round-trip through cache")
    return headers


async def headers_or_capture(
    device_uuid: str | None = None,
    device_name: str | None = None,
) -> RequestHeaders:
    cached = load_cached_headers()
    if cached is not None:
        return cached
    return await capture_live_headers(device_uuid, device_name)


def http_headers(headers: RequestHeaders) -> dict[str, str]:
    out = {
        "real-request-token": headers.real_request_token,
        "real-version": headers.real_version,
        "real-device-type": headers.real_device_type,
        "real-device-uuid": headers.real_device_uuid,
        "real-device-id": headers.real_device_id,
        "real-device-name": headers.real_device_name,
        "user-agent": headers.user_agent,
        "accept": "application/json",
        "content-type": "application/json",
        "referer": "https://realsports.io/",
        "origin": "https://realsports.io",
    }
    if headers.real_auth_info:
        out["real-auth-info"] = headers.real_auth_info
    return out


async def real_sports_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
    refresh_headers: Callable[[], Awaitable[RequestHeaders]] | None = None,
    max_attempts: int = 5,
    timeout_s: float = 30.0,
) -> httpx.Response:
    refreshed = False
    policy = RetryPolicy(
        max_attempts=max_attempts,
        base_delay=1.0,
        max_delay=60.0,
        retry_statuses=frozenset({429, 503}),
    )
    transport = HttpxAsyncTransport(client)
    for _ in range(2):
        response = await async_request_with_retry(
            transport,
            "GET",
            url,
            policy=policy,
            params=params,
            headers=headers,
            timeout=timeout_s,
        )
        if response.status_code == 200:
            return response
        if response.status_code == 401:
            if refresh_headers is not None and not refreshed:
                new_headers = await refresh_headers()
                headers.clear()
                headers.update(http_headers(new_headers))
                refreshed = True
                continue
            raise PlatformAuthRequired(f"401 on {url}")
        response.raise_for_status()
    raise PlatformAuthRequired(f"401 on {url}")


async def fetch_game_stats(
    client: httpx.AsyncClient,
    game_id: int,
    headers: RequestHeaders,
    *,
    refresh_headers: Callable[[], Awaitable[RequestHeaders]] | None = None,
) -> dict[str, Any]:
    wire = http_headers(headers)
    response = await real_sports_get(
        client,
        f"{BASE}/games/{game_id}/sport/{SPORT}/stats",
        headers=wire,
        refresh_headers=refresh_headers,
    )
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError(f"stats payload for game {game_id} must be an object")
    return payload


async def fetch_game_players(
    client: httpx.AsyncClient,
    game_id: int,
    headers: RequestHeaders,
    *,
    refresh_headers: Callable[[], Awaitable[RequestHeaders]] | None = None,
) -> dict[str, Any]:
    wire = http_headers(headers)
    response = await real_sports_get(
        client,
        f"{BASE}/games/{game_id}/sport/{SPORT}/players",
        headers=wire,
        refresh_headers=refresh_headers,
    )
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError(f"players payload for game {game_id} must be an object")
    return payload


async def fetch_game_feed(
    client: httpx.AsyncClient,
    game_id: int,
    headers: RequestHeaders,
    *,
    refresh_headers: Callable[[], Awaitable[RequestHeaders]] | None = None,
) -> dict[str, Any]:
    wire = http_headers(headers)
    response = await real_sports_get(
        client,
        f"{BASE}/games/{game_id}/sport/{SPORT}/feed",
        headers=wire,
        params={"version": 2, "view": "all", "viewFrame": "default"},
        refresh_headers=refresh_headers,
    )
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError(f"feed payload for game {game_id} must be an object")
    return payload

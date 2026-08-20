"""Provider-neutral HTTP transports with bounded retry behavior."""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Protocol

import httpx

from oracle_core.redaction import redact_url

_RETRYABLE_METHODS = frozenset({"DELETE", "GET", "HEAD", "OPTIONS", "PUT"})
_RETRYABLE_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


class SyncHttpTransport(Protocol):
    """Capability required by synchronous provider clients."""

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send one HTTP request without application-level retries."""


class AsyncHttpTransport(Protocol):
    """Capability required by asynchronous provider clients."""

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send one HTTP request without application-level retries."""


@dataclass(frozen=True)
class TimeoutConfig:
    """Explicit HTTP timeout values in seconds."""

    connect: float = 5.0
    read: float = 30.0
    write: float = 30.0
    pool: float = 5.0

    def __post_init__(self) -> None:
        if min(self.connect, self.read, self.write, self.pool) <= 0:
            raise ValueError("HTTP timeouts must be positive")

    def as_httpx(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=self.connect,
            read=self.read,
            write=self.write,
            pool=self.pool,
        )


@dataclass(frozen=True)
class RetryPolicy:
    """A bounded exponential-backoff policy with optional server hints."""

    max_attempts: int = 3
    base_delay: float = 0.25
    max_delay: float = 10.0
    jitter_ratio: float = 1.0
    retry_statuses: frozenset[int] = field(default_factory=lambda: _RETRYABLE_STATUSES)
    retry_methods: frozenset[str] = field(default_factory=lambda: _RETRYABLE_METHODS)
    respect_retry_after: bool = True

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay < 0 or self.max_delay < 0:
            raise ValueError("retry delays cannot be negative")
        if self.base_delay > self.max_delay:
            raise ValueError("base_delay cannot exceed max_delay")
        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError("jitter_ratio must be between 0 and 1")

    def supports_method(self, method: str) -> bool:
        return method.upper() in self.retry_methods

    def should_retry_response(self, method: str, response: httpx.Response) -> bool:
        return self.supports_method(method) and response.status_code in self.retry_statuses

    def delay(
        self,
        failed_attempt: int,
        *,
        retry_after: str | None = None,
        now: datetime | None = None,
        random_value: float | None = None,
    ) -> float:
        """Return a delay capped by ``max_delay`` for a failed 1-based attempt."""

        if failed_attempt < 1:
            raise ValueError("failed_attempt must be at least 1")
        exponential = min(self.max_delay, self.base_delay * (2 ** (failed_attempt - 1)))
        sample = random.random() if random_value is None else random_value
        low = exponential * (1 - self.jitter_ratio)
        jittered = low + ((exponential - low) * min(1.0, max(0.0, sample)))
        server_delay = parse_retry_after(retry_after, now=now) if self.respect_retry_after else None
        return min(self.max_delay, max(jittered, server_delay or 0.0))


@dataclass(frozen=True)
class RateLimitMetadata:
    """Normalized rate-limit response metadata when a provider supplies it."""

    limit: int | None = None
    remaining: int | None = None
    reset_at: datetime | None = None
    retry_after_seconds: float | None = None

    @classmethod
    def from_headers(
        cls,
        headers: Mapping[str, str],
        *,
        now: datetime | None = None,
    ) -> RateLimitMetadata:
        current = now or datetime.now(UTC)
        normalized = {key.casefold(): value for key, value in headers.items()}
        return cls(
            limit=_parse_int(normalized.get("x-ratelimit-limit")),
            remaining=_parse_int(normalized.get("x-ratelimit-remaining")),
            reset_at=_parse_reset(normalized.get("x-ratelimit-reset")),
            retry_after_seconds=parse_retry_after(normalized.get("retry-after"), now=current),
        )


class HttpRequestError(RuntimeError):
    """A final HTTP transport failure whose message cannot contain credentials."""

    def __init__(self, method: str, url: str, attempts: int, cause: BaseException) -> None:
        self.method = method.upper()
        self.url = redact_url(url)
        self.attempts = attempts
        self.cause_type = type(cause).__name__
        super().__init__(
            f"{self.method} {self.url} failed after {attempts} attempt(s): {self.cause_type}"
        )


class HttpxSyncTransport:
    """Synchronous transport backed by an owned or injected ``httpx.Client``."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        timeout: TimeoutConfig | None = None,
    ) -> None:
        self._owned = client is None
        self._client = client or httpx.Client(timeout=(timeout or TimeoutConfig()).as_httpx())

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        return self._client.request(method, url, **kwargs)

    def close(self) -> None:
        if self._owned:
            self._client.close()

    def __enter__(self) -> HttpxSyncTransport:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


class HttpxAsyncTransport:
    """Asynchronous transport backed by an owned or injected ``httpx.AsyncClient``."""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        timeout: TimeoutConfig | None = None,
    ) -> None:
        self._owned = client is None
        self._client = client or httpx.AsyncClient(timeout=(timeout or TimeoutConfig()).as_httpx())

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        return await self._client.request(method, url, **kwargs)

    async def close(self) -> None:
        if self._owned:
            await self._client.aclose()

    async def __aenter__(self) -> HttpxAsyncTransport:
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.close()


def request_with_retry(
    transport: SyncHttpTransport,
    method: str,
    url: str,
    *,
    policy: RetryPolicy | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    random_source: Callable[[], float] = random.random,
    **kwargs: Any,
) -> httpx.Response:
    """Send a synchronous request using the provided bounded retry policy."""

    retry = policy or RetryPolicy()
    for attempt in range(1, retry.max_attempts + 1):
        try:
            response = transport.request(method, url, **kwargs)
        except httpx.TransportError as error:
            if attempt == retry.max_attempts or not retry.supports_method(method):
                raise HttpRequestError(method, url, attempt, error) from None
            sleeper(retry.delay(attempt, random_value=random_source()))
            continue
        if attempt == retry.max_attempts or not retry.should_retry_response(method, response):
            return response
        sleeper(
            retry.delay(
                attempt,
                retry_after=response.headers.get("retry-after"),
                random_value=random_source(),
            )
        )
    raise AssertionError("unreachable")


async def async_request_with_retry(
    transport: AsyncHttpTransport,
    method: str,
    url: str,
    *,
    policy: RetryPolicy | None = None,
    sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    random_source: Callable[[], float] = random.random,
    **kwargs: Any,
) -> httpx.Response:
    """Send an asynchronous request using the provided bounded retry policy."""

    retry = policy or RetryPolicy()
    for attempt in range(1, retry.max_attempts + 1):
        try:
            response = await transport.request(method, url, **kwargs)
        except httpx.TransportError as error:
            if attempt == retry.max_attempts or not retry.supports_method(method):
                raise HttpRequestError(method, url, attempt, error) from None
            await sleeper(retry.delay(attempt, random_value=random_source()))
            continue
        if attempt == retry.max_attempts or not retry.should_retry_response(method, response):
            return response
        await sleeper(
            retry.delay(
                attempt,
                retry_after=response.headers.get("retry-after"),
                random_value=random_source(),
            )
        )
    raise AssertionError("unreachable")


def parse_retry_after(value: str | None, *, now: datetime | None = None) -> float | None:
    """Parse delta-seconds or an HTTP date, returning ``None`` when malformed."""

    if value is None:
        return None
    stripped = value.strip()
    try:
        seconds = float(stripped)
    except ValueError:
        try:
            target = parsedate_to_datetime(stripped)
        except (TypeError, ValueError, OverflowError):
            return None
        if target.tzinfo is None:
            target = target.replace(tzinfo=UTC)
        current = now or datetime.now(UTC)
        return max(0.0, (target - current).total_seconds())
    return max(0.0, seconds) if seconds >= 0 else None


def _parse_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _parse_reset(value: str | None) -> datetime | None:
    parsed = _parse_int(value)
    if parsed is None:
        return None
    try:
        return datetime.fromtimestamp(parsed, UTC)
    except (OverflowError, OSError, ValueError):
        return None

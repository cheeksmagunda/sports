"""Deterministic fakes and log capture helpers for application tests."""

from __future__ import annotations

import io
import json
import logging
from collections import deque
from collections.abc import Callable, Generator, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from oracle_core.logging import LoggingConfig, configure_json_logging
from oracle_core.storage import Lease


class FixedClock:
    """A callable UTC clock that tests can advance explicitly."""

    def __init__(self, value: datetime) -> None:
        if value.tzinfo is None:
            raise ValueError("FixedClock requires a timezone-aware datetime")
        self.value = value.astimezone(UTC)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, delta: timedelta) -> datetime:
        self.value += delta
        return self.value


@dataclass(frozen=True)
class RecordedRequest:
    method: str
    url: str
    kwargs: dict[str, Any]


class FakeSyncTransport:
    """Queue-backed synchronous HTTP transport."""

    def __init__(self, responses: Iterable[httpx.Response | BaseException] = ()) -> None:
        self.responses = deque(responses)
        self.requests: list[RecordedRequest] = []

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self.requests.append(RecordedRequest(method.upper(), url, kwargs))
        if not self.responses:
            raise AssertionError("FakeSyncTransport has no queued response")
        response = self.responses.popleft()
        if isinstance(response, BaseException):
            raise response
        return response


class FakeAsyncTransport:
    """Queue-backed asynchronous HTTP transport."""

    def __init__(self, responses: Iterable[httpx.Response | BaseException] = ()) -> None:
        self.responses = deque(responses)
        self.requests: list[RecordedRequest] = []

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self.requests.append(RecordedRequest(method.upper(), url, kwargs))
        if not self.responses:
            raise AssertionError("FakeAsyncTransport has no queued response")
        response = self.responses.popleft()
        if isinstance(response, BaseException):
            raise response
        return response


class FakeKeyValueStore:
    """In-memory key-value store with deterministic TTL expiry."""

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self.clock = clock or (lambda: 0.0)
        self.values: dict[str, tuple[bytes, float | None]] = {}

    def get(self, key: str) -> bytes | None:
        item = self.values.get(key)
        if item is None:
            return None
        value, expires_at = item
        if expires_at is not None and self.clock() >= expires_at:
            del self.values[key]
            return None
        return value

    def set(self, key: str, value: bytes, *, ttl_seconds: int | None = None) -> None:
        if ttl_seconds is not None and ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        expires_at = self.clock() + ttl_seconds if ttl_seconds is not None else None
        self.values[key] = (bytes(value), expires_at)

    def delete(self, key: str) -> bool:
        return self.values.pop(key, None) is not None


class FakeLeaseStore:
    """In-memory lease store that models ownership and expiration."""

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self.clock = clock or (lambda: 0.0)
        self._counter = 0
        self.leases: dict[str, tuple[str, float]] = {}

    def acquire(self, key: str, *, ttl_seconds: int) -> Lease | None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        current = self.leases.get(key)
        if current is not None and self.clock() < current[1]:
            return None
        self._counter += 1
        lease = Lease(key=key, token=f"fake-token-{self._counter}")
        self.leases[key] = (lease.token, self.clock() + ttl_seconds)
        return lease

    def renew(self, lease: Lease, *, ttl_seconds: int) -> bool:
        current = self.leases.get(lease.key)
        if (
            ttl_seconds <= 0
            or current is None
            or current[0] != lease.token
            or self.clock() >= current[1]
        ):
            return False
        self.leases[lease.key] = (lease.token, self.clock() + ttl_seconds)
        return True

    def release(self, lease: Lease) -> bool:
        current = self.leases.get(lease.key)
        if current is None or current[0] != lease.token or self.clock() >= current[1]:
            return False
        del self.leases[lease.key]
        return True


@dataclass
class CapturedLogs:
    """Structured JSON events captured from the root logger."""

    stream: io.StringIO

    @property
    def events(self) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self.stream.getvalue().splitlines() if line]


@contextmanager
def capture_json_logs(*, level: str = "DEBUG") -> Generator[CapturedLogs, None, None]:
    """Temporarily replace root handlers and yield decoded JSON log access."""

    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    previous_level = root.level
    stream = io.StringIO()
    configure_json_logging(LoggingConfig(level=level, replace_handlers=True), stream=stream)
    try:
        yield CapturedLogs(stream)
    finally:
        root.handlers.clear()
        root.handlers.extend(previous_handlers)
        root.setLevel(previous_level)

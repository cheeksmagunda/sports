from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
import pytest
from oracle_core.http import (
    HttpRequestError,
    HttpxAsyncTransport,
    HttpxSyncTransport,
    RateLimitMetadata,
    RetryPolicy,
    TimeoutConfig,
    async_request_with_retry,
    parse_retry_after,
    request_with_retry,
)
from oracle_core.testing import FakeAsyncTransport, FakeSyncTransport


def test_retry_policy_is_validated_and_bounded() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError):
        RetryPolicy(base_delay=2, max_delay=1)
    with pytest.raises(ValueError):
        RetryPolicy(jitter_ratio=1.1)
    with pytest.raises(ValueError):
        TimeoutConfig(read=0)

    policy = RetryPolicy(base_delay=2, max_delay=5, jitter_ratio=1)
    assert policy.delay(1, random_value=0.5) == 1
    assert policy.delay(4, retry_after="999", random_value=0) == 5


def test_retry_after_supports_delta_dates_and_malformed_values() -> None:
    now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)

    assert parse_retry_after("3.5", now=now) == 3.5
    assert parse_retry_after("Thu, 20 Aug 2026 12:00:09 GMT", now=now) == 9
    assert parse_retry_after("nonsense", now=now) is None
    assert parse_retry_after("-1", now=now) is None


def test_sync_retry_uses_server_hint_and_returns_last_response() -> None:
    transport = FakeSyncTransport(
        [httpx.Response(503, headers={"Retry-After": "8"}), httpx.Response(200)]
    )
    sleeps: list[float] = []

    response = request_with_retry(
        transport,
        "GET",
        "https://service.test/resource",
        policy=RetryPolicy(base_delay=1, max_delay=4),
        sleeper=sleeps.append,
        random_source=lambda: 0,
    )

    assert response.status_code == 200
    assert sleeps == [4]
    assert len(transport.requests) == 2


def test_non_idempotent_method_is_not_retried_by_default() -> None:
    transport = FakeSyncTransport([httpx.Response(503), httpx.Response(200)])

    response = request_with_retry(transport, "POST", "https://service.test")

    assert response.status_code == 503
    assert len(transport.requests) == 1


def test_transport_failure_raises_sanitized_error() -> None:
    request = httpx.Request("GET", "https://user:password@service.test/path?apiKey=super-secret")
    transport = FakeSyncTransport([httpx.ConnectError("connection failed", request=request)])

    with pytest.raises(HttpRequestError) as exc_info:
        request_with_retry(
            transport,
            "GET",
            str(request.url),
            policy=RetryPolicy(max_attempts=1),
        )

    rendered = str(exc_info.value)
    assert "super-secret" not in rendered
    assert "password" not in rendered
    assert "ConnectError" in rendered


def test_async_retry_matches_sync_semantics() -> None:
    transport = FakeAsyncTransport([httpx.Response(429), httpx.Response(204)])
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    response = asyncio.run(
        async_request_with_retry(
            transport,
            "GET",
            "https://service.test",
            policy=RetryPolicy(base_delay=2, max_delay=3),
            sleeper=sleep,
            random_source=lambda: 0.5,
        )
    )

    assert response.status_code == 204
    assert sleeps == [1]


def test_rate_limit_metadata_is_case_insensitive() -> None:
    metadata = RateLimitMetadata.from_headers(
        {
            "X-RateLimit-Limit": "100",
            "X-RateLimit-Remaining": "7",
            "X-RateLimit-Reset": "1787227200",
            "Retry-After": "2",
        }
    )

    assert metadata.limit == 100
    assert metadata.remaining == 7
    assert metadata.reset_at == datetime.fromtimestamp(1787227200, UTC)
    assert metadata.retry_after_seconds == 2


def test_httpx_transports_support_injected_clients() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"method": request.method})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with HttpxSyncTransport(client, timeout=TimeoutConfig()) as transport:
            assert transport.request("GET", "https://test.invalid").json() == {"method": "GET"}

    async def run_async() -> int:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            async with HttpxAsyncTransport(client) as transport:
                return (await transport.request("GET", "https://test.invalid")).status_code

    assert asyncio.run(run_async()) == 200

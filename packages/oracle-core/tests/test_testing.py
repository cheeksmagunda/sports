from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from oracle_core.logging import get_logger
from oracle_core.testing import (
    FakeAsyncTransport,
    FakeSyncTransport,
    FixedClock,
    capture_json_logs,
)


def test_fixed_clock_is_aware_and_advanceable() -> None:
    with pytest.raises(ValueError):
        FixedClock(datetime(2026, 8, 20))

    clock = FixedClock(datetime(2026, 8, 20, tzinfo=UTC))
    assert clock.advance(timedelta(minutes=3)) == datetime(2026, 8, 20, 0, 3, tzinfo=UTC)


def test_fake_transports_record_calls_and_raise_queue_items() -> None:
    sync = FakeSyncTransport([httpx.Response(200)])
    assert sync.request("get", "https://test.invalid", headers={"x": "y"}).status_code == 200
    assert sync.requests[0].method == "GET"

    async def use_async() -> int:
        transport = FakeAsyncTransport([httpx.Response(201)])
        response = await transport.request("post", "https://test.invalid")
        assert transport.requests[0].method == "POST"
        return response.status_code

    assert asyncio.run(use_async()) == 201


def test_log_capture_decodes_structured_events() -> None:
    with capture_json_logs() as captured:
        get_logger("test").info("event", count=3)

    assert captured.events[0]["message"] == "event"
    assert captured.events[0]["count"] == 3

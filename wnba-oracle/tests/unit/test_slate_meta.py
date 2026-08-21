"""D83: slate timing capture (job1) feeding the late-refreeze lock gate.

job1 reads per-game tip times from /home/wnba/next and UPSERTs the
earliest into slate_meta.first_tip_utc as the contest-lock proxy (the
platform exposes no lock timestamp, only a live isLocked boolean).
"""

from __future__ import annotations

import datetime as dt
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from wnba_oracle.ingest import realsports
from wnba_oracle.ingest.realsports import RequestHeaders
from wnba_oracle.scheduler import job1, job1_persist


def _fake_headers() -> RequestHeaders:
    return RequestHeaders(
        real_request_token="t",
        real_version="1.0",
        real_device_type="ios",
        real_device_uuid="uuid",
        real_device_id="did",
        real_device_name="dev",
        real_auth_info=None,
        user_agent="ua",
        captured_at=0.0,
    )


def test_parse_game_time_platform_format() -> None:
    out = job1.parse_game_time("2026-05-27T23:00:00.000Z")
    assert out == dt.datetime(2026, 5, 27, 23, 0, tzinfo=dt.UTC)


def test_parse_game_time_garbage_returns_none() -> None:
    assert job1.parse_game_time("") is None
    assert job1.parse_game_time("not-a-time") is None


def test_persist_slate_meta_takes_earliest_tip() -> None:
    eng = MagicMock()
    conn = MagicMock()
    eng.begin.return_value.__enter__.return_value = conn
    with patch.object(job1_persist, "get_engine", return_value=eng):
        job1._persist_slate_meta(
            "2026-05-27",
            ["2026-05-28T00:00:00.000Z", "2026-05-27T23:00:00.000Z"],
        )
    payload = conn.execute.call_args.args[1]
    assert payload["first_tip_utc"] == dt.datetime(2026, 5, 27, 23, 0, tzinfo=dt.UTC)
    assert payload["contest_lock_utc"] is None
    assert payload["source"] == "realsports_home_next"
    assert json.loads(payload["payload_json"])["game_times"] == [
        "2026-05-28T00:00:00.000Z",
        "2026-05-27T23:00:00.000Z",
    ]


def test_persist_slate_meta_writes_null_row_when_no_games() -> None:
    """A row with NULL first_tip_utc still lands: it distinguishes "job1
    looked and found nothing" from "job1 never ran"."""
    eng = MagicMock()
    conn = MagicMock()
    eng.begin.return_value.__enter__.return_value = conn
    with patch.object(job1_persist, "get_engine", return_value=eng):
        job1._persist_slate_meta("2026-05-27", [])
    payload = conn.execute.call_args.args[1]
    assert payload["first_tip_utc"] is None


@pytest.mark.asyncio
async def test_fetch_slate_game_times_reads_home_next() -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/home/wnba/next"
        return httpx.Response(
            200,
            json={
                "latestDayContent": {
                    "games": [
                        {"id": 1, "dateTime": "2026-05-27T23:00:00.000Z"},
                        {"id": 2, "dateTime": "2026-05-28T00:00:00.000Z"},
                        {"id": 3, "dateTime": None},
                    ]
                }
            },
        )

    transport = httpx.MockTransport(_handler)
    headers = _fake_headers()
    async with httpx.AsyncClient(transport=transport, base_url=realsports.BASE) as client:
        out = await realsports.fetch_slate_game_times(headers, client)
    assert out == ["2026-05-27T23:00:00.000Z", "2026-05-28T00:00:00.000Z"]


@pytest.mark.asyncio
async def test_fetch_slate_game_times_empty_payload() -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"latestDayContent": {}})

    transport = httpx.MockTransport(_handler)
    headers = _fake_headers()
    async with httpx.AsyncClient(transport=transport, base_url=realsports.BASE) as client:
        out = await realsports.fetch_slate_game_times(headers, client)
    assert out == []

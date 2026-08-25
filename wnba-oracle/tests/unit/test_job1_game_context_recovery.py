from __future__ import annotations

import json
from unittest.mock import MagicMock

import httpx
import pytest

from wnba_oracle.ingest.realsports import (
    PlayerGameContext,
    RequestHeaders,
    fetch_game_context_by_player,
)
from wnba_oracle.scheduler import job1


def _headers() -> RequestHeaders:
    return RequestHeaders(
        real_request_token="token",
        real_version="31",
        real_device_type="desktop_web",
        real_device_uuid="uuid",
        real_device_id="device-id",
        real_device_name="device-name",
        real_auth_info="auth",
        user_agent="user-agent",
        captured_at=0.0,
    )


@pytest.mark.asyncio
async def test_lightweight_fetch_preserves_authoritative_game_id_and_start() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/home/wnba/next":
            return httpx.Response(
                200,
                json={
                    "latestDayContent": {
                        "games": [{"id": 4512, "dateTime": "2026-08-25T23:00:00.000Z"}]
                    }
                },
            )
        if request.url.path == "/games/4512/sport/wnba/players":
            return httpx.Response(200, json={"players": [{"id": 9001}]})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        contexts = await fetch_game_context_by_player(
            "2026-08-25",
            _headers(),
            client,
        )

    assert contexts == {
        "9001": PlayerGameContext(
            game_id="4512",
            game_start_utc="2026-08-25T23:00:00.000Z",
        )
    }


@pytest.mark.asyncio
async def test_lightweight_fetch_rejects_player_on_multiple_game_rosters() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/home/wnba/next":
            return httpx.Response(
                200,
                json={
                    "latestDayContent": {
                        "games": [
                            {"id": 4512, "dateTime": "2026-08-25T23:00:00.000Z"},
                            {"id": 4513, "dateTime": "2026-08-26T00:00:00.000Z"},
                        ]
                    }
                },
            )
        if request.url.path in {
            "/games/4512/sport/wnba/players",
            "/games/4513/sport/wnba/players",
        }:
            return httpx.Response(200, json={"players": [{"id": 9001}]})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError, match="multiple game rosters"):
            await fetch_game_context_by_player(
                "2026-08-25",
                _headers(),
                client,
            )


def test_job1games_atomically_recovers_game_id_and_start(monkeypatch) -> None:
    async def fake_headers(_uuid: str, _name: str) -> RequestHeaders:
        return _headers()

    async def fake_contexts(
        _slate_date: str,
        _request_headers: RequestHeaders,
        _client: httpx.AsyncClient,
        **_kwargs: object,
    ) -> dict[str, PlayerGameContext]:
        return {
            "9001": PlayerGameContext(
                game_id="4512",
                game_start_utc="2026-08-25T23:00:00.000Z",
            )
        }

    connection = MagicMock()
    read_result = MagicMock()
    read_result.fetchall.return_value = [(77, "9001"), (78, "not-on-roster")]
    connection.execute.side_effect = [read_result, MagicMock()]
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value = connection

    monkeypatch.setattr(job1, "headers_or_capture", fake_headers)
    monkeypatch.setattr(job1, "fetch_game_context_by_player", fake_contexts)
    monkeypatch.setattr(job1, "get_engine", lambda: engine)

    assert job1.run_game_starts("2026-08-25") == 1

    assert connection.execute.call_count == 2
    update = connection.execute.call_args_list[1]
    assert str(update.args[0]) == str(job1.LITE_PATCH)
    assert update.args[1]["id"] == 77
    assert json.loads(update.args[1]["patch"]) == {
        "game_id": "4512",
        "game_start_utc": "2026-08-25T23:00:00.000Z",
    }

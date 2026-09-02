"""Parser tests for the Real Sports pool response. Hits no network."""

from __future__ import annotations

import httpx
import pytest

from wnba_oracle.ingest import realsports
from wnba_oracle.ingest.realsports import RequestHeaders, _parse_pool


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


def test_parse_pool_basic() -> None:
    body = {
        "players": [
            {
                "id": "12345",
                "firstName": "AJ",
                "lastName": "Wilson",
                "displayName": "A'ja Wilson",
                "position": "F",
                "team": {"key": "LAS"},
                "multiplierBonus": 1.5,
                "primaryRanking": 1,
                "injuryStatus": "",
            },
            {
                "id": "23456",
                "firstName": "Caitlin",
                "lastName": "Clark",
                "displayName": "Caitlin Clark",
                "position": "G",
                "team": "IND",
                "multiplierBonus": 0.0,
                "primaryRanking": 2,
                "injuryStatus": "",
            },
        ]
    }
    out = _parse_pool(body)
    assert len(out) == 2
    assert out[0].team == "LAS"
    assert out[0].position == "F"
    assert out[0].multiplier_bonus == 1.5
    assert out[1].team == "IND"
    assert out[1].multiplier_bonus == 0.0


def test_parse_pool_missing_boost_hard_fails() -> None:
    """Hard Rule 7: schema drift halts fetch, never imputes."""
    body = {"players": [{"id": "1", "team": "LAS", "position": "G"}]}
    with pytest.raises(RuntimeError, match="missing multiplierBonus"):
        _parse_pool(body)


def test_parse_pool_boost_out_of_range_hard_fails() -> None:
    body = {"players": [{"id": "1", "team": "LAS", "position": "G", "multiplierBonus": 5.0}]}
    with pytest.raises(RuntimeError, match="out of range"):
        _parse_pool(body)


def test_parse_pool_accepts_alternate_key() -> None:
    body = {"players": [{"id": "1", "team": "LAS", "position": "G", "multiplier_bonus": 0.5}]}
    out = _parse_pool(body)
    assert out[0].multiplier_bonus == 0.5


def test_parse_pool_empty_returns_empty() -> None:
    assert _parse_pool({"players": []}) == []
    assert _parse_pool({}) == []


def test_parse_pool_empty_display_name_falls_back_to_first_last() -> None:
    """The Real Sports pool endpoint occasionally returns ``displayName=""``
    on rookies while still populating ``firstName``/``lastName`` (observed
    2026-05-29 — first manifested as the frontend rendering ``Player 4322873``
    placeholders). Reconstruct from the parts so downstream (job1_enrichment
    -> job2._build_per_player -> frozen lineup JSONB -> frontend card)
    carries a real name.
    """
    body = {
        "players": [
            {
                "id": "4322873",
                "firstName": "Frieda",
                "lastName": "Buhner",
                "displayName": "",
                "position": "F-C",
                "team": "POR",
                "multiplierBonus": 3.0,
            }
        ]
    }
    out = _parse_pool(body)
    assert out[0].display_name == "Frieda Buhner"


@pytest.mark.asyncio
async def test_contest_discovery_selects_newest_validated_wnba_id() -> None:
    requested_ids: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        contest_id = int(request.url.path.rsplit("/", maxsplit=1)[-1])
        requested_ids.append(contest_id)
        sport = {2118: "soccer", 2117: "wnba", 2116: "mlb"}[contest_id]
        return httpx.Response(200, json={"info": {"contest": {"sport": sport}}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        contest_id = await realsports._select_wnba_contest_id(
            [2116, 2118, 2117], _headers(), client
        )

    assert contest_id == 2117
    assert requested_ids == [2118, 2117]


@pytest.mark.asyncio
async def test_contest_discovery_returns_none_when_no_candidate_is_wnba() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        contest_id = int(request.url.path.rsplit("/", maxsplit=1)[-1])
        sport = {2118: "soccer", 2116: "mlb"}[contest_id]
        return httpx.Response(200, json={"info": {"contest": {"sport": sport}}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        contest_id = await realsports._select_wnba_contest_id([2116, 2118], _headers(), client)

    assert contest_id is None

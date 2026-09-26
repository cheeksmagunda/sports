"""Multi-contest day selection for the NFL worker and NFLReader.collect."""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest

from nfl_oracle.ingest.realsports import RequestHeaders
from nfl_oracle.recommendations import cli
from nfl_oracle.recommendations.provider import NFLReader, ObservationStore, ProviderError

DAY = date(2026, 9, 17)
GAME_ID = 19500


def test_select_contest_id_defaults_to_first() -> None:
    assert cli._select_contest_id([100, 200]) == 100


def test_select_contest_id_empty_returns_none() -> None:
    assert cli._select_contest_id([]) is None


def test_select_contest_id_respects_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NFL_CONTEST_ID", "200")
    assert cli._select_contest_id([100, 200, 300]) == 200


def test_select_contest_id_explicit_override_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NFL_CONTEST_ID", "200")
    assert cli._select_contest_id([100, 200, 300], explicit="300") == 300


def test_select_contest_id_invalid_override_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NFL_CONTEST_ID", "999")
    assert cli._select_contest_id([100, 200]) is None
    monkeypatch.setenv("NFL_CONTEST_ID", "not-an-int")
    assert cli._select_contest_id([100, 200]) is None


def _game() -> dict[str, object]:
    return {
        "id": GAME_ID,
        "sport": "nfl",
        "season": 2026,
        "dateTime": "2026-09-17T20:25:00Z",
        "homeTeamId": 10,
        "awayTeamId": 11,
        "homeTeamKey": "H",
        "awayTeamKey": "A",
        "status": "scheduled",
    }


def _roster_player(pid: int) -> dict[str, object]:
    return {
        "id": pid,
        "sport": "nfl",
        "teamId": 10,
        "firstName": "P",
        "lastName": str(pid),
        "position": "WR",
        "injuryStatus": "Active",
    }


def _rated_player(pid: int, boost: float) -> dict[str, object]:
    return {**_roster_player(pid), "multiplierBonus": boost}


def _multi_contest_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/home/nfl/day/next":
        return httpx.Response(
            200,
            json={
                "content": {
                    "day": DAY.isoformat(),
                    "games": [_game()],
                    "config": {
                        "dailyDraftInfo": {
                            "contests": [{"id": 3001}, {"id": 3002}],
                        }
                    },
                }
            },
        )
    if path in {
        "/games/playerratingcontest/3001",
        "/games/playerratingcontest/3002",
    }:
        cid = int(path.rsplit("/", 1)[-1])
        return httpx.Response(
            200,
            json={
                "info": {
                    "contest": {
                        "id": cid,
                        "sport": "nfl",
                        "day": DAY.isoformat(),
                        "endDay": DAY.isoformat(),
                        "isFinalized": False,
                        "additionalInfo": {"lineupSize": 5},
                    },
                    "isLocked": False,
                }
            },
        )
    if path in {
        "/games/playerratingcontest/3001/draftinfo",
        "/games/playerratingcontest/3002/draftinfo",
    }:
        return httpx.Response(
            200,
            json={
                "info": {
                    "sport": "nfl",
                    "day": DAY.isoformat(),
                    "endDay": DAY.isoformat(),
                    "lineupSize": 5,
                    "defaultMultipliers": [2, 1.8, 1.6, 1.4, 1.2],
                }
            },
        )
    if path == f"/games/{GAME_ID}/sport/nfl/players":
        return httpx.Response(200, json={"players": [_roster_player(p) for p in (1, 2, 3)]})
    if path == "/players/sport/nfl/search":
        return httpx.Response(
            200,
            json={
                "players": [
                    _rated_player(1, 0.0),
                    _rated_player(2, 1.4),
                    _rated_player(3, 3.0),
                ]
            },
        )
    raise AssertionError(f"unexpected path {path}")


def _reader(tmp_path):
    return NFLReader(
        httpx.AsyncClient(transport=httpx.MockTransport(_multi_contest_handler)),
        RequestHeaders(
            real_request_token="test",
            real_version="test",
            real_device_type="web",
            real_device_uuid="test",
            real_device_id="test",
            real_device_name="test",
            real_auth_info=None,
            user_agent="test",
            captured_at=0,
        ),
        ObservationStore(tmp_path),
        clock=lambda: datetime(2026, 9, 8, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_collect_defaults_to_first_contest_when_none(tmp_path) -> None:
    client = _reader(tmp_path)
    slate = await client.collect(DAY, contest_id=None)
    assert slate.contest.contest_id == 3001


@pytest.mark.asyncio
async def test_collect_honors_explicit_contest_id(tmp_path) -> None:
    client = _reader(tmp_path)
    slate = await client.collect(DAY, contest_id=3002)
    assert slate.contest.contest_id == 3002


@pytest.mark.asyncio
async def test_collect_raises_when_no_contests(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/home/nfl/day/next":
            return httpx.Response(
                200,
                json={
                    "content": {
                        "day": DAY.isoformat(),
                        "games": [_game()],
                        "config": {"dailyDraftInfo": {"contests": []}},
                    }
                },
            )
        raise AssertionError(f"unexpected path {request.url.path}")

    client = NFLReader(
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        RequestHeaders(
            real_request_token="test",
            real_version="test",
            real_device_type="web",
            real_device_uuid="test",
            real_device_id="test",
            real_device_name="test",
            real_auth_info=None,
            user_agent="test",
            captured_at=0,
        ),
        ObservationStore(tmp_path),
        clock=lambda: datetime(2026, 9, 8, tzinfo=UTC),
    )
    with pytest.raises(ProviderError, match="ambiguous_or_missing_contest"):
        await client.collect(DAY, contest_id=None)

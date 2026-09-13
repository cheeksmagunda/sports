"""Pool completeness must be measured against games that can still be drafted.

The provider stops rating a player once their game kicks off. On a one-game
slate that never matters, because the contest is over the moment the game
starts. On a Sunday it matters from the first kickoff onward: the started games
contribute their full rosters to the denominator and nothing to the matched
pool, so `pool_complete` goes false and G1 refuses every remaining freeze for
the rest of the day.

Observed live on 2026-09-13, contest 2154: 2045 rostered across thirteen games,
781 matched, 1264 unmatched -- and the 781 were exactly the five games that had
not kicked off yet, each matching 100% of its roster.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest

from nfl_oracle.ingest.realsports import RequestHeaders
from nfl_oracle.recommendations.provider import NFLReader, ObservationStore

NOW = datetime(2026, 9, 13, 18, 0, tzinfo=UTC)
DAY = date(2026, 9, 13)
STARTED = 19458  # kicked off at 17:00Z
UPCOMING = 19466  # kicks off at 20:25Z


def _game(game_id: int, kickoff: str, status: str, home: int) -> dict[str, object]:
    return {
        "id": game_id,
        "sport": "nfl",
        "season": 2026,
        "dateTime": kickoff,
        "homeTeamId": home,
        "awayTeamId": home + 1,
        "homeTeamKey": f"H{game_id}",
        "awayTeamKey": f"A{game_id}",
        "status": status,
    }


def _player(pid: int, team_id: int, *, rated: bool) -> dict[str, object]:
    row: dict[str, object] = {
        "id": pid,
        "sport": "nfl",
        "teamId": team_id,
        "firstName": "P",
        "lastName": str(pid),
        "position": "WR",
        "injuryStatus": "Active",
    }
    if rated:
        row["multiplierBonus"] = 0
    return row


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/home/nfl/day/next":
        return httpx.Response(
            200,
            json={
                "content": {
                    "day": DAY.isoformat(),
                    "games": [
                        _game(STARTED, "2026-09-13T17:00:00Z", "inprogress", 10),
                        _game(UPCOMING, "2026-09-13T20:25:00Z", "scheduled", 20),
                    ],
                    "config": {"dailyDraftInfo": {"contests": [{"id": 2154}]}},
                }
            },
        )
    if path == "/games/playerratingcontest/2154":
        return httpx.Response(
            200,
            json={
                "info": {
                    "contest": {
                        "id": 2154,
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
    if path == "/games/playerratingcontest/2154/draftinfo":
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
    if path == f"/games/{STARTED}/sport/nfl/players":
        return httpx.Response(200, json={"players": [_player(p, 10, rated=False) for p in (1, 2)]})
    if path == f"/games/{UPCOMING}/sport/nfl/players":
        return httpx.Response(
            200, json={"players": [_player(p, 20, rated=False) for p in (3, 4, 5, 6, 7)]}
        )
    if path == "/players/sport/nfl/search":
        # The provider only rates players whose game has not started. Players 1
        # and 2 belong to the game already under way and are never returned.
        return httpx.Response(
            200, json={"players": [_player(p, 20, rated=True) for p in (3, 4, 5, 6, 7)]}
        )
    raise AssertionError(f"unexpected path {path}")


def _reader(tmp_path) -> NFLReader:
    return NFLReader(
        httpx.AsyncClient(transport=httpx.MockTransport(_handler)),
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
        clock=lambda: NOW,
    )


@pytest.mark.asyncio
async def test_started_games_do_not_make_the_pool_incomplete(tmp_path) -> None:
    slate = await _reader(tmp_path).collect(DAY, contest_id=2154)

    # Only the game that can still be drafted defines the pool.
    assert [game.game_id for game in slate.games] == [UPCOMING]
    assert slate.pool_roster_count == 5
    assert slate.pool_search_matched_count == 5
    assert slate.pool_unmatched_ids == ()
    assert slate.pool_complete is True

    # No candidate may come from a game already under way.
    assert {candidate.game_id for candidate in slate.candidates} == {UPCOMING}

    # The gate that refused every freeze after the first kickoff now passes.
    slate.assert_prelock(NOW)


@pytest.mark.asyncio
async def test_pool_still_fails_closed_when_a_draftable_player_is_unobserved(tmp_path) -> None:
    """Narrowing the denominator must not weaken the gate itself."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/players/sport/nfl/search":
            # Player 7 is draftable but never comes back from the search.
            return httpx.Response(
                200, json={"players": [_player(p, 20, rated=True) for p in (3, 4, 5, 6)]}
            )
        return _handler(request)

    reader = _reader(tmp_path)
    reader.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    slate = await reader.collect(DAY, contest_id=2154)

    assert slate.pool_unmatched_ids == (7,)
    assert slate.pool_complete is False
    with pytest.raises(ValueError, match="incomplete_player_pool"):
        slate.assert_prelock(NOW)

from datetime import UTC, date, datetime

import httpx
import pytest

from nfl_oracle.ingest.realsports import RequestHeaders
from nfl_oracle.recommendations.provider import NFLReader, NoSlate, ObservationStore, ProviderError

DAY = date(2026, 9, 17)
GAME_ID = 19500


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


def _boost_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/home/nfl/day/next":
        return httpx.Response(
            200,
            json={
                "content": {
                    "day": DAY.isoformat(),
                    "games": [_game()],
                    "config": {"dailyDraftInfo": {"contests": [{"id": 3001}]}},
                }
            },
        )
    if path == "/games/playerratingcontest/3001":
        return httpx.Response(
            200,
            json={
                "info": {
                    "contest": {
                        "id": 3001,
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
    if path == "/games/playerratingcontest/3001/draftinfo":
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
        # Player 2 carries float noise on its published boost, the same shape
        # the provider itself produces (see nfl_oracle.contests.boosts).
        return httpx.Response(
            200,
            json={
                "players": [
                    _rated_player(1, 0.0),
                    _rated_player(2, 1.4000000000000001),
                    _rated_player(3, 3.0),
                ]
            },
        )
    raise AssertionError(f"unexpected path {path}")


def reader(tmp_path, handler):
    return NFLReader(
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


@pytest.mark.asyncio
async def test_date_resolver_checks_echoed_day_and_no_slate(tmp_path):
    def handler(request):
        assert request.url.path == "/home/nfl/day/next"
        assert request.url.params["day"] == "2026-09-08"
        return httpx.Response(200, json={"content": {"day": "2026-09-08", "games": []}})

    client = reader(tmp_path, handler)
    with pytest.raises(NoSlate):
        await client.collect(date(2026, 9, 8))
    assert len(client.hashes) == 1


@pytest.mark.asyncio
async def test_wrong_day_cannot_be_treated_as_empty(tmp_path):
    client = reader(
        tmp_path,
        lambda request: httpx.Response(200, json={"content": {"day": "2026-09-09", "games": []}}),
    )
    with pytest.raises(ProviderError, match="day_identity"):
        await client.collect(date(2026, 9, 8))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/games/1/sport/nba/stats",
        "/games/playerratingcontest/1/submit",
        "/games/1/sport/nfl/players?token=x",
        "/games/../1/stats",
        "/games/playerratingcontest/1/payoutinfo",
    ],
)
async def test_nfl_read_route_allowlist_precedes_transport(tmp_path, path):
    def handler(request):
        pytest.fail("transport must not be reached")

    with pytest.raises(ProviderError, match="read_path_not_allowed"):
        await reader(tmp_path, handler).get(path)


@pytest.mark.asyncio
async def test_collect_declares_boost_regime_via_boost_observation(tmp_path):
    """The slate's boost classification must come from the tested
    BoostObservation capture, not a hand-rolled count, and card_boost must be
    snapped to the provider's published tenth (see nfl_oracle.contests.boosts).
    """
    client = NFLReader(
        httpx.AsyncClient(transport=httpx.MockTransport(_boost_handler)),
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
        clock=lambda: datetime(2026, 9, 17, 12, tzinfo=UTC),
    )
    slate = await client.collect(DAY, contest_id=3001)

    assert slate.boost_regime == "provider_boosts_present"
    assert slate.boost_nonzero_count == 2
    assert slate.boost_max == 3.0
    by_id = {c.player_id: c.card_boost for c in slate.candidates}
    assert by_id[1] == 0.0
    assert by_id[2] == 1.4  # snapped, no float noise
    assert by_id[3] == 3.0


@pytest.mark.asyncio
async def test_request_limit_and_redacted_observation(tmp_path):
    client = reader(
        tmp_path,
        lambda request: httpx.Response(200, json={"content": {"day": "2026-09-08"}}),
    )
    client.max_requests = 1
    await client.get("/home/nfl/day/next", day="2026-09-08")
    with pytest.raises(ProviderError, match="budget"):
        await client.get("/home/nfl/next")
    files = list(tmp_path.glob("*/*.json"))
    assert len(files) == 1
    assert files[0].stat().st_mode & 0o777 == 0o600
    assert '"method":"GET"' in files[0].read_text().replace(" ", "")

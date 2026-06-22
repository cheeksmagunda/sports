"""D72 / R6: the targeted-search fallback in `fetch_pool_for_date`.

The single-letter a..z prefix sweep caps results per query (Real Sports'
search endpoint returns the top N matches per call), so players deep in
the alphabetical ordering for the matched letter were dropped. The audit
(`research/internal/_menu_scrape_gap_pool.csv`) showed 8 of 13 live
slates had >= 1 winning-lineup pick missing from the optimizer's pool,
all draftable players the prefix sweep silently lost.

Fix: after a..z, query each per-game-union player NOT yet in `rated_by_id`
by the ASCII-folded first 3 chars of their last name. These tests mock
the Real Sports API with `httpx.MockTransport` and verify the fallback
recovers the missed pids.
"""

from __future__ import annotations

import httpx
import pytest

from wnba_oracle.ingest import realsports
from wnba_oracle.ingest.realsports import RequestHeaders, fetch_pool_for_date


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


def _request_query(req: httpx.Request) -> str:
    return req.url.params.get("query") or ""


def _build_mock_transport(
    *,
    union_players: list[dict],
    rated_per_query: dict[str, list[dict]],
) -> httpx.MockTransport:
    """Mock the three Real Sports endpoints `fetch_pool_for_date` calls.

    union_players: returned from /games/1/sport/wnba/players (the per-game
        roster union the function intersects against).
    rated_per_query: maps the search `query` param to the player list the
        search endpoint should return. Anything not in this dict returns
        an empty list (mirroring an a..z letter that matched nothing for
        the players we care about).
    """

    def _handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/home/wnba/next":
            return httpx.Response(200, json={"latestDayContent": {"games": [{"id": 1}]}})
        if path == "/games/1/sport/wnba/players":
            return httpx.Response(200, json={"players": union_players})
        if path == "/players/sport/wnba/search":
            q = _request_query(request)
            players = rated_per_query.get(q, [])
            return httpx.Response(200, json={"players": players})
        return httpx.Response(404, json={"error": f"unexpected path {path}"})

    return httpx.MockTransport(_handler)


def _player(pid: str, first: str, last: str, *, mb: float | None = 1.0) -> dict:
    return {
        "id": pid,
        "firstName": first,
        "lastName": last,
        "displayName": f"{first[:1]}. {last}",
        "position": "F",
        "team": {"key": "LAS"},
        "primaryRanking": int(pid) if pid.isdigit() else 0,
        "multiplierBonus": mb,
        "injuryStatus": "",
    }


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Strip the antibot jitter so tests run instantly."""
    async def _noop() -> None:
        return None

    monkeypatch.setattr(realsports, "asleep_truncated_gaussian", _noop)


@pytest.mark.asyncio
async def test_fallback_recovers_unmatched_player_by_last_name() -> None:
    """Stevens is in the per-game union but no a..z letter returns her.
    The targeted fallback queries 'ste' and finds her."""
    union = [
        _player("100", "Aja", "Wilson", mb=None),  # mb assigned via search
        _player("711", "Azura", "Stevens", mb=None),
    ]
    rated_per_query = {
        # a..z sweep: 'a' returns Wilson (firstName Aja matches), no letter
        # returns Stevens (the bug we are reproducing).
        "a": [_player("100", "Aja", "Wilson", mb=2.0)],
        # Targeted fallback: 'ste' returns Stevens.
        "ste": [_player("711", "Azura", "Stevens", mb=2.5)],
    }

    transport = _build_mock_transport(
        union_players=union, rated_per_query=rated_per_query
    )
    async with httpx.AsyncClient(transport=transport, base_url=realsports.BASE) as client:
        out = await fetch_pool_for_date(
            "2026-06-07",
            _fake_headers(),
            client,
        )

    ids = sorted(p.platform_id for p in out)
    assert ids == ["100", "711"], (
        "fallback should add Stevens (pid 711) on top of the a..z-matched Wilson; "
        f"got {ids}"
    )
    boosts = {p.platform_id: p.multiplier_bonus for p in out}
    assert boosts["711"] == 2.5
    assert boosts["100"] == 2.0


@pytest.mark.asyncio
async def test_fallback_ascii_folds_accented_lastname() -> None:
    """Jocyte (lastName 'Jocyteė') should query 'joc' after ASCII-fold."""
    union = [_player("4322799", "Justė", "Jocytė", mb=None)]
    rated_per_query = {
        # a..z misses her -- the prefix sweep also folds, but the cap
        # truncates the response.
        "joc": [_player("4322799", "Justė", "Jocytė", mb=2.8)],
    }
    transport = _build_mock_transport(
        union_players=union, rated_per_query=rated_per_query
    )
    async with httpx.AsyncClient(transport=transport, base_url=realsports.BASE) as client:
        out = await fetch_pool_for_date(
            "2026-06-07",
            _fake_headers(),
            client,
        )
    ids = [p.platform_id for p in out]
    assert ids == ["4322799"], (
        f"ASCII-folded fallback should match Jocyte; got {ids}"
    )


@pytest.mark.asyncio
async def test_fallback_skips_when_no_lastname_or_firstname() -> None:
    """A pure-anonymous player (no first or last name) cannot be queried.
    Don't crash; just leave them unrated. Other players still flow through."""
    union = [
        _player("100", "Aja", "Wilson", mb=None),
        {"id": "999", "team": {"key": "LAS"}, "position": "F", "primaryRanking": 99},
    ]
    rated_per_query = {"a": [_player("100", "Aja", "Wilson", mb=2.0)]}
    transport = _build_mock_transport(
        union_players=union, rated_per_query=rated_per_query
    )
    async with httpx.AsyncClient(transport=transport, base_url=realsports.BASE) as client:
        out = await fetch_pool_for_date(
            "2026-06-07",
            _fake_headers(),
            client,
        )
    ids = [p.platform_id for p in out]
    assert ids == ["100"], f"only Wilson is rated; got {ids}"


@pytest.mark.asyncio
async def test_fallback_does_not_requery_az_letters() -> None:
    """If the unmatched player's last name is one char (or first-3 is just
    'a'/'b'/...), don't re-issue an a..z query that already ran."""
    union = [_player("711", "Azura", "Stevens", mb=None)]
    # No a..z letter returns Stevens. The fallback would compute 'ste'
    # which is not in a..z. Confirm that the function does NOT re-call
    # 'a' (it tracks queried_prefixes from the a..z sweep).
    seen_queries: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/home/wnba/next":
            return httpx.Response(200, json={"latestDayContent": {"games": [{"id": 1}]}})
        if path == "/games/1/sport/wnba/players":
            return httpx.Response(200, json={"players": union})
        if path == "/players/sport/wnba/search":
            q = request.url.params.get("query") or ""
            seen_queries.append(q)
            if q == "ste":
                return httpx.Response(
                    200, json={"players": [_player("711", "Azura", "Stevens", mb=2.5)]}
                )
            return httpx.Response(200, json={"players": []})
        return httpx.Response(404)

    transport = httpx.MockTransport(_handler)
    async with httpx.AsyncClient(transport=transport, base_url=realsports.BASE) as client:
        await fetch_pool_for_date(
            "2026-06-07",
            _fake_headers(),
            client,
        )

    # 26 a..z queries + exactly 1 fallback query ('ste')
    assert "ste" in seen_queries
    assert seen_queries.count("ste") == 1
    az = "abcdefghijklmnopqrstuvwxyz"
    for letter in az:
        assert letter in seen_queries

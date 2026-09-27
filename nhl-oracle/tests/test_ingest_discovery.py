from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from nhl_oracle.ingest.discovery import (
    ContestIdentityMismatch,
    _verify_contest_identity,
    probe_next_slate,
    sample_contest,
    scan_contest_range,
)
from nhl_oracle.ingest.provenance import NhlCorpusStore
from nhl_oracle.ingest.realsports import RequestHeaders

pytestmark = pytest.mark.asyncio


def _headers() -> RequestHeaders:
    return RequestHeaders(
        real_request_token="test",
        real_version="test",
        real_device_type="web",
        real_device_uuid="test",
        real_device_id="test",
        real_device_name="test",
        real_auth_info=None,
        user_agent="test",
        captured_at=0,
    )


def _client(handler: object) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]


async def test_probe_next_slate_parses_populated_draft_info() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/home/nhl/next"
        return httpx.Response(
            200,
            json={
                "latestDay": "2026-09-13",
                "days": [{"day": "2026-09-13"}],
                "latestDayContent": {
                    "config": {"dailyDraftInfo": {"contests": [{"id": 2154, "source": "home"}]}}
                },
            },
        )

    async with _client(handler) as client:
        probe = await probe_next_slate(client, _headers())

    assert probe.latest_day == "2026-09-13"
    assert probe.has_draft_info is True
    assert probe.contest_ids == (2154,)


async def test_probe_next_slate_reports_no_draft_info_without_guessing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "latestDay": "2026-09-19",
                "days": [],
                "latestDayContent": {"config": {"dailyDraftInfo": None}},
            },
        )

    async with _client(handler) as client:
        probe = await probe_next_slate(client, _headers())

    assert probe.has_draft_info is False
    assert probe.contest_ids == ()


async def test_sample_contest_persists_nhl_sub_routes(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.startswith("/games/playerratingcontest/1918")
        route = request.url.path.rsplit("/", 1)[-1]
        if route == "1918":
            return httpx.Response(
                200,
                json={
                    "info": {
                        "contest": {
                            "id": 1918,
                            "sport": "nhl",
                            "day": "2022-11-17",
                            "gameId": 2022020263,
                            "isFinalized": True,
                            "numBrawlers": 6,
                        }
                    }
                },
            )
        if route == "entries":
            return httpx.Response(200, json={"contest": {"id": 1918}, "entries": []})
        if route == "draftinfo":
            return httpx.Response(500, json={"error": "internal"})
        if route == "stats":
            # Observed live: a stale contest's stats route can echo an
            # unrelated contest instead of erroring.
            return httpx.Response(200, json={"contest": {"id": 9999, "sport": "wnba"}})
        if route == "payoutinfo":
            return httpx.Response(200, json={"info": {"payoutInfoItems": []}})
        raise AssertionError(f"unexpected route {route}")

    store = NhlCorpusStore(tmp_path)
    async with _client(handler) as client:
        sample = await sample_contest(client, _headers(), 1918, store=store)

    assert sample.kind == "nhl"
    assert sample.game_id == 2022020263
    assert sample.entrants == 6
    assert sample.is_finalized is True
    assert set(sample.routes_persisted) == {"entries", "payoutinfo"}
    assert any(u.startswith("draftinfo:") for u in sample.routes_unavailable)
    assert any(u.startswith("stats:") for u in sample.routes_unavailable)

    persisted = store.raw_root / "2022" / "2022020263" / "contest.json"
    assert persisted.is_file()
    body = json.loads(persisted.read_text(encoding="utf-8"))
    assert body["contest_id"] == 1918
    assert set(body["routes"]) == {"meta", "entries", "payoutinfo"}
    assert "stats" not in body["routes"]


async def test_sample_contest_skips_other_sports_without_fetching_sub_routes() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(
            200, json={"info": {"contest": {"id": 2141, "sport": "nfl", "day": "2026-09-09"}}}
        )

    async with _client(handler) as client:
        sample = await sample_contest(client, _headers(), 2141)

    assert sample.kind == "other_sport"
    assert sample.sport == "nfl"
    assert calls == ["/games/playerratingcontest/2141"]


async def test_sample_contest_reports_absent_for_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(404, json={"error": "not_found"})

    async with _client(handler) as client:
        sample = await sample_contest(client, _headers(), 999999)

    assert sample.kind == "absent"


async def test_scan_contest_range_counts_every_id_honestly() -> None:
    nhl_contest = {
        "id": 1,
        "sport": "nhl",
        "day": "2022-05-06",
        "gameId": 1,
        "numBrawlers": 7,
    }
    nfl_contest = {"id": 2, "sport": "nfl", "day": "2026-09-09"}
    responses = {
        1: httpx.Response(200, json={"info": {"contest": nhl_contest}}),
        2: httpx.Response(200, json={"info": {"contest": nfl_contest}}),
        3: httpx.Response(404, json={}),
        4: httpx.Response(500, json={}),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        contest_id = int(request.url.path.rsplit("/", 1)[-1])
        return responses[contest_id]

    async with _client(handler) as client:
        coverage = await scan_contest_range(
            client, _headers(), [1, 2, 3, 4], fetch_sub_routes=False, request_pause_s=0
        )

    assert coverage.ids_scanned == 4
    assert coverage.nhl_found == 1
    assert coverage.other_sport_found == 1
    assert coverage.absent == 1
    assert coverage.failed == 1
    assert coverage.nhl_contests[0].contest_id == 1


async def test_contest_identity_mismatch_is_a_named_error() -> None:
    with pytest.raises(ContestIdentityMismatch):
        _verify_contest_identity({"contest": {"id": 5, "sport": "wnba"}}, contest_id=1918)

    # No embedded contest object at all is not a mismatch -- nothing to check.
    _verify_contest_identity({"entries": []}, contest_id=1918)

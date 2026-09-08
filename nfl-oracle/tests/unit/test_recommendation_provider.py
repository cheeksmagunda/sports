from datetime import UTC, date, datetime

import httpx
import pytest

from nfl_oracle.ingest.realsports import RequestHeaders
from nfl_oracle.recommendations.provider import NFLReader, NoSlate, ObservationStore, ProviderError


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

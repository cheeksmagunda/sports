"""Unit tests for contest_stats parsing."""

from __future__ import annotations

import httpx

from wnba_oracle.ingest.contest_stats import (
    ContestLabel,
    ContestUnavailable,
    _parse_drafts,
    _parse_real_score,
    _player_display_name,
    dedupe_by_player,
    fetch_contest_entries,
    fetch_contest_stats,
)
from wnba_oracle.ingest.realsports import RequestHeaders


def test_parse_drafts() -> None:
    assert _parse_drafts(None) is None
    assert _parse_drafts(7) == 7
    assert _parse_drafts("42") == 42
    assert _parse_drafts("1.1k") == 1100
    assert _parse_drafts("") is None
    assert _parse_drafts("nope") is None


def test_parse_real_score() -> None:
    assert _parse_real_score(None) is None
    assert _parse_real_score("7.24826") == 7.24826
    assert _parse_real_score("-0.45") == -0.45
    assert _parse_real_score("+1.2") == 1.2
    assert _parse_real_score("") is None
    assert _parse_real_score("nan-ish") is None


def _stub_headers() -> RequestHeaders:
    return RequestHeaders(
        real_request_token="t",
        real_version="32",
        real_device_type="desktop_web",
        real_device_uuid="u",
        real_device_id="u",
        real_device_name="test",
        real_auth_info="auth",
        user_agent="UA",
        captured_at=0.0,
    )


def test_player_display_name_falls_back_to_first_last() -> None:
    """D50: mirror the pool parser's D49 fallback. An empty ``displayName``
    must not leak an empty ``slate_labels.display_name`` row, since that
    table is the live freeze's defense-in-depth name source."""
    assert _player_display_name({"displayName": "A. Wilson"}) == "A. Wilson"
    assert (
        _player_display_name(
            {"displayName": "", "firstName": "Frieda", "lastName": "Buhner"}
        )
        == "Frieda Buhner"
    )
    assert (
        _player_display_name({"firstName": "Naz", "lastName": "Hillmon"})
        == "Naz Hillmon"
    )
    assert _player_display_name({}) == ""


def test_fetch_contest_stats_empty_display_name_falls_back() -> None:
    """End-to-end: an empty ``displayName`` in a draftStats player object
    is reconstructed from ``firstName``/``lastName`` in the ContestLabel."""
    payload = {
        "contest": {"id": 1840, "day": "2026-05-26", "sport": "wnba"},
        "draftStats": [
            {
                "sectionName": "popularPlayers",
                "players": [
                    {
                        "player": {
                            "id": 4322873,
                            "displayName": "",
                            "firstName": "Frieda",
                            "lastName": "Buhner",
                        },
                        "team": {"key": "por"},
                        "multiplierBonus": 3.0,
                        "value": "1.71",
                        "displayStats": [{"label": "Drafts", "value": "120"}],
                    }
                ],
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        out = fetch_contest_stats(1840, _stub_headers(), client)
    assert len(out) == 1
    assert out[0].platform_player_id == 4322873
    assert out[0].display_name == "Frieda Buhner"


def test_fetch_contest_entries_parses_lineup() -> None:
    payload = {
        "contest": {
            "id": 1831,
            "day": "2026-05-25",
            "sport": "wnba",
            "isFinalized": True,
            "numBrawlers": 9041,
        },
        "entries": [
            {
                "id": 66922805,
                "rank": 1,
                "pagedRank": 1,
                "userId": "7J6Olwav",
                "score": "40.60",
                "additionalInfo": {
                    "lineup": [
                        {
                            "playerId": 687,
                            "multiplier": 3.5,
                            "multiplierBonus": 1.5,
                            "value": "3.5421",
                            "score": 12.397,
                            "displayName": "E. Engstler",
                        },
                        {"playerId": 643, "multiplier": 2.7, "value": "3.6665"},
                    ]
                },
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/games/playerratingcontest/1831/entries"
        assert request.url.params.get("contestType") == "sport"
        assert request.url.params.get("isGuillotine") == "false"
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        out = fetch_contest_entries(1831, _stub_headers(), client)
    assert len(out) == 1
    e = out[0]
    assert e.contest_id == 1831
    assert e.slate_date == "2026-05-25"
    assert e.rank == 1
    assert e.user_id == "7J6Olwav"
    assert e.score == 40.60
    assert e.num_brawlers == 9041
    assert len(e.lineup) == 2
    assert e.lineup[0]["multiplier"] == 3.5


def test_fetch_contest_entries_rejects_wrong_sport() -> None:
    payload = {"contest": {"sport": "mlb", "day": "2026-05-25"}, "entries": []}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        try:
            fetch_contest_entries(1837, _stub_headers(), client)
        except ContestUnavailable as exc:
            assert "expected wnba" in str(exc)
        else:
            raise AssertionError("expected ContestUnavailable")


def test_dedupe_by_player_keeps_first() -> None:
    labels = [
        ContestLabel(
            contest_id=1, slate_date="2026-05-26", section="highestBoostedValuePlayers",
            platform_player_id=42, display_name="X", team_key="LVA",
            card_boost=1.5, drafts=100, real_score=5.0,
        ),
        ContestLabel(
            contest_id=1, slate_date="2026-05-26", section="popularPlayers",
            platform_player_id=42, display_name="X", team_key="LVA",
            card_boost=1.5, drafts=200, real_score=5.0,
        ),
        ContestLabel(
            contest_id=1, slate_date="2026-05-26", section="popularPlayers",
            platform_player_id=43, display_name="Y", team_key="NYL",
            card_boost=0.5, drafts=300, real_score=3.0,
        ),
    ]
    out = dedupe_by_player(labels)
    assert len(out) == 2
    assert out[0].platform_player_id == 42
    assert out[0].section == "highestBoostedValuePlayers"  # first wins
    assert out[1].platform_player_id == 43

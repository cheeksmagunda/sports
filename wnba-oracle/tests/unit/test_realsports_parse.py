"""Parser tests for the Real Sports pool response. Hits no network."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from wnba_oracle.ingest.contest_stats import ContestUnavailable
from wnba_oracle.ingest.realsports import _parse_pool, _validated_wnba_contest_id


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


def test_contest_discovery_skips_newer_non_wnba_contests() -> None:
    def fetch_stats(contest_id: int, *_args: object) -> list:
        if contest_id in {2118, 2116}:
            raise ContestUnavailable("wrong sport")
        return []

    with patch("wnba_oracle.ingest.contest_stats.fetch_contest_stats", side_effect=fetch_stats):
        contest_id = _validated_wnba_contest_id(
            [2118, 2117, 2116],
            MagicMock(),
            MagicMock(),
        )
    assert contest_id == 2117
    assert contest_id == 2117

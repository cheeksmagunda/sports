"""Tests for the portfolio draftStats section catalog (#526)."""

from __future__ import annotations

import json
from pathlib import Path

from oracle_core.draft_stats_catalog import (
    HV_SECTION,
    all_section_names,
    catalog_document,
    provider_section_names,
    train_label_sections,
)

FIXTURE = Path(__file__).parent / "fixtures" / "daily_draft_stats_sections.json"


def test_hv_is_sole_train_label_section() -> None:
    assert train_label_sections() == (HV_SECTION,)
    assert HV_SECTION in all_section_names()


def test_catalog_covers_wnba_provider_trio_and_nfl_most_drafted() -> None:
    names = set(all_section_names())
    assert {
        "highestBoostedValuePlayers",
        "popularPlayers",
        "mostCommon3xPlayers",
        "mostDrafted",
        "leaderboard_lineup",
        "mostValuablePlayers",
    } <= names
    wnba = set(provider_section_names(sport="wnba"))
    assert wnba == {
        "highestBoostedValuePlayers",
        "popularPlayers",
        "mostCommon3xPlayers",
    }
    assert "mostDrafted" in provider_section_names(sport="nfl")


def test_fixture_enumerates_provider_sections_and_fields() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["displayInfo"]["title"] == "Daily Draft Stats"
    sections = payload["draftStats"]
    names = [sec["sectionName"] for sec in sections]
    assert names == [
        "highestBoostedValuePlayers",
        "popularPlayers",
        "mostCommon3xPlayers",
        "mostDrafted",
    ]
    hv_player = sections[0]["players"][0]
    assert "multiplierBonus" in hv_player
    assert "value" in hv_player
    assert hv_player["displayStats"][0]["label"] == "Drafts"
    nfl_player = sections[3]["players"][0]
    assert nfl_player["count"] == 4102
    assert "mostCommonPosition" in nfl_player


def test_catalog_document_layout_paths() -> None:
    doc = catalog_document()
    assert doc["schema_version"] == 1
    assert "total_value_leaderboards" in doc["corpus_layout"]
    assert "recorded_states_draft_stats" in doc["corpus_layout"]
    assert "never train labels" in doc["corpus_layout"]["note"]

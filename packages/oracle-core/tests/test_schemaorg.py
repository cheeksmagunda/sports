"""schema.org contract helpers."""

from __future__ import annotations

from oracle_core.schemaorg import (
    SCHEMA_ORG,
    item_list,
    person_athlete,
    quantitative_value,
    sports_event,
    sports_team,
    with_context,
)


def test_sports_event_and_team_nodes() -> None:
    event = sports_event(
        identifier=1001,
        name="SEA at NE",
        start_date="2026-09-10T00:20:00Z",
        home_team=sports_team(identifier="NE", name="Patriots"),
        away_team=sports_team(identifier="SEA", name="Seahawks"),
    )
    assert event["@type"] == "SportsEvent"
    assert event["homeTeam"]["@type"] == "SportsTeam"
    doc = with_context(event)
    assert doc["@context"]["@vocab"] == SCHEMA_ORG


def test_item_list_ranks_athletes() -> None:
    board = item_list(
        [person_athlete(identifier=1), person_athlete(identifier=2)],
        name="Highest value",
    )
    assert board["numberOfItems"] == 2
    assert board["itemListElement"][0]["position"] == 1
    assert quantitative_value(3.5, name="raw_highest_score_pre_boost")["@type"] == (
        "QuantitativeValue"
    )

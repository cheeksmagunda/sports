"""schema.org contract helpers."""

from __future__ import annotations

from oracle_core.schemaorg import (
    SCHEMA_ORG,
    high_tv_label_observation,
    item_list,
    observation,
    person_athlete,
    property_value,
    punch_list_item_list,
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


def test_observation_wraps_numeric_value_and_context() -> None:
    event = sports_event(identifier="game-1", name="Home at Away")
    node = observation(
        about=event,
        measured_property=property_value(name="Raw score", unit_text="score"),
        value=8.25,
        unit_text="score",
        additional_properties=[property_value(name="Label", value="high_tv")],
    )

    assert node["@type"] == "Observation"
    assert node["observationAbout"] == event
    assert node["measuredProperty"]["@type"] == "PropertyValue"
    assert node["value"] == {
        "@type": "QuantitativeValue",
        "value": 8.25,
        "unitText": "score",
    }
    assert node["additionalProperty"][0]["value"] == "high_tv"
    assert with_context(node)["@context"]["@vocab"] == SCHEMA_ORG


def test_high_tv_label_observation_covers_event_and_athlete() -> None:
    event = sports_event(identifier="game-1")
    athlete = person_athlete(identifier="player-1", name="Player One")

    node = high_tv_label_observation(
        event=event,
        athletes=[athlete],
        label="high_tv",
        raw_score=7.5,
        high_tv_score=9.25,
    )

    assert node["@type"] == "Observation"
    assert node["observationAbout"] == [event, athlete]
    assert node["measuredProperty"]["name"] == "Raw score"
    assert node["value"]["value"] == 7.5
    assert node["additionalProperty"] == [
        property_value(name="High-TV label", value="high_tv"),
        property_value(
            name="High-TV score",
            value=quantitative_value(9.25, unit_text="score"),
        ),
    ]


def test_punch_list_item_list_links_priority_and_category() -> None:
    doc = punch_list_item_list(
        [
            {
                "priority": 1,
                "category": "infra",
                "title": "No freeze recorded for 2026-09-13",
                "detail": "Scheduled slate without a frozen lineup.",
                "evidence": {"day": "2026-09-13"},
            }
        ],
        name="NFL week 2026-W01 punch list",
        season=2026,
        week=1,
    )
    assert doc["@type"] == "ItemList"
    assert doc["@context"]["@vocab"] == SCHEMA_ORG
    assert doc["oracle:kind"] == "punch_list"
    assert doc["oracle:season"] == 2026
    assert doc["numberOfItems"] == 1
    item = doc["itemListElement"][0]["item"]
    assert item["@type"] == "CreativeWork"
    assert item["name"].startswith("No freeze")
    props = {p["name"]: p["value"] for p in item["additionalProperty"]}
    assert props["priority"] == 1
    assert props["category"] == "infra"

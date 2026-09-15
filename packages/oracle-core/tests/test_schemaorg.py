"""schema.org contract helpers."""

from __future__ import annotations

import pytest

from oracle_core.schemaorg import (
    PROV_NS,
    SCHEMA_ORG,
    attach_identifiers,
    high_tv_label_observation,
    identifier_value,
    item_list,
    observation,
    organization_role,
    person_athlete,
    place,
    property_value,
    prov_attribution,
    punch_list_item_list,
    quantitative_value,
    same_as_refs,
    sports_event,
    sports_organization,
    sports_team,
    validate_typed_node,
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
    assert doc["@context"]["prov"] == PROV_NS


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


def test_place_and_sports_organization_nodes() -> None:
    venue = place(
        identifier="gillette", name="Gillette Stadium", same_as="https://www.gillettestadium.com/"
    )
    org = sports_organization(identifier="nfl", name="NFL", sport="American Football")
    team = sports_team(
        identifier="NE",
        name="Patriots",
        member_of=org,
        identifiers=[identifier_value(value="NE", property_id="nflverse.team_abbr")],
    )
    event = sports_event(
        identifier=1001,
        location=venue,
        home_team=team,
    )
    assert venue["@type"] == "Place"
    assert org["@type"] == "SportsOrganization"
    assert event["location"]["name"] == "Gillette Stadium"
    assert isinstance(team["identifier"], list)
    assert team["identifier"][1]["propertyID"] == "nflverse.team_abbr"


def test_organization_role_time_bounded_membership() -> None:
    athlete = person_athlete(identifier="p1", name="Player")
    team = sports_team(identifier="NE", name="Patriots")
    role = organization_role(
        member=athlete,
        organization=team,
        role_name="QB",
        start_date="2024-03-01",
        end_date="2025-02-28",
    )
    assert role["@type"] == "OrganizationRole"
    assert role["roleName"] == "QB"
    assert role["startDate"] == "2024-03-01"
    assert role["oracle:organization"]["identifier"] == "NE"
    assert validate_typed_node(role, expected_type="OrganizationRole") == []


def test_same_as_requires_authoritative_uri() -> None:
    assert same_as_refs("https://www.nfl.com/players/example/") == (
        "https://www.nfl.com/players/example/"
    )
    with pytest.raises(ValueError, match="absolute http"):
        same_as_refs("A.J. Brown / PHI")
    with pytest.raises(ValueError, match="absolute http"):
        person_athlete(identifier=1, same_as="not-a-url")


def test_attach_identifiers_and_validate() -> None:
    person = person_athlete(identifier="21042", name="A.J. Brown")
    enriched = attach_identifiers(
        person,
        identifier_value(value="00-0035676", property_id="gsis_id"),
    )
    assert enriched["identifier"][0] == "21042"
    assert enriched["identifier"][1]["propertyID"] == "gsis_id"
    assert validate_typed_node(enriched, expected_type="Person", require_identifier=True) == []
    assert validate_typed_node({}, expected_type="Person", require_identifier=True) == [
        "missing @type",
        "missing identifier",
    ]


def test_prov_attribution_adds_prov_properties() -> None:
    event = sports_event(identifier="g1")
    attributed = prov_attribution(
        entity=event,
        agent={"@type": "Organization", "name": "Real Sports"},
        activity="corpus-g-ingest",
        generated_at_time="2026-09-15T00:00:00Z",
    )
    assert attributed["prov:wasAttributedTo"]["name"] == "Real Sports"
    assert attributed["prov:wasGeneratedBy"] == "corpus-g-ingest"
    assert attributed["prov:generatedAtTime"] == "2026-09-15T00:00:00Z"
    assert with_context(attributed)["@context"]["prov"] == PROV_NS

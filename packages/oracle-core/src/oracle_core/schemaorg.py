"""schema.org vocabulary helpers for shared Oracle data contracts.

Prefer schema.org types and properties for cross-sport abstractions:
SportsEvent, SportsTeam, Person (athlete), SportsOrganization,
QuantitativeValue, ItemList, and related properties.

Extend only with clearly namespaced additional properties
(``https://oracle.local/vocab#...`` or compact ``oracle:``) when schema.org
has no fit. Sport apps map provider payloads onto these shapes; oracle-core
does not import sport packages.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

SCHEMA_ORG = "https://schema.org/"
ORACLE_VOCAB = "https://oracle.local/vocab#"

# Compact aliases used in JSON-LD @context maps.
SCHEMA_CONTEXT: dict[str, str] = {
    "@vocab": SCHEMA_ORG,
    "schema": SCHEMA_ORG,
    "oracle": ORACLE_VOCAB,
}


def schema_type(*types: str) -> list[str] | str:
    """Return a schema.org @type value (single string or list)."""

    if len(types) == 1:
        return types[0]
    return list(types)


def quantitative_value(
    value: float,
    *,
    name: str | None = None,
    unit_text: str | None = None,
    additional: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema.org QuantitativeValue node."""

    node: dict[str, Any] = {
        "@type": "QuantitativeValue",
        "value": value,
    }
    if name is not None:
        node["name"] = name
    if unit_text is not None:
        node["unitText"] = unit_text
    if additional:
        for key, raw in additional.items():
            node[key if ":" in key or key.startswith("@") else f"oracle:{key}"] = raw
    return node


def property_value(
    *,
    name: str,
    value: Any | None = None,
    property_id: str | None = None,
    unit_text: str | None = None,
    value_reference: Mapping[str, Any] | None = None,
    additional: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema.org PropertyValue node for a named property."""

    node: dict[str, Any] = {
        "@type": "PropertyValue",
        "name": name,
    }
    if value is not None:
        node["value"] = value
    if property_id is not None:
        node["propertyID"] = property_id
    if unit_text is not None:
        node["unitText"] = unit_text
    if value_reference is not None:
        node["valueReference"] = dict(value_reference)
    if additional:
        for key, raw in additional.items():
            node[key if ":" in key or key.startswith("@") else f"oracle:{key}"] = raw
    return node


def observation(
    *,
    about: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    measured_property: str | Mapping[str, Any],
    value: float | int | Mapping[str, Any] | None = None,
    unit_text: str | None = None,
    additional_properties: Sequence[Mapping[str, Any]] | None = None,
    additional: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema.org Observation node.

    Numeric values become QuantitativeValue nodes. Callers can supply a
    structured schema.org value directly when a numeric score is not the
    appropriate representation.
    """

    observation_about: Any
    if isinstance(about, Mapping):
        observation_about = dict(about)
    else:
        observation_about = [dict(subject) for subject in about]

    node: dict[str, Any] = {
        "@type": "Observation",
        "observationAbout": observation_about,
        "measuredProperty": (
            property_value(name=measured_property)
            if isinstance(measured_property, str)
            else dict(measured_property)
        ),
    }
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        node["value"] = quantitative_value(float(value), unit_text=unit_text)
    elif isinstance(value, Mapping):
        node["value"] = dict(value)
    if additional_properties:
        node["additionalProperty"] = [
            dict(property_node) for property_node in additional_properties
        ]
    if additional:
        for key, raw in additional.items():
            node[key if ":" in key or key.startswith("@") else f"oracle:{key}"] = raw
    return node


def high_tv_label_observation(
    *,
    event: Mapping[str, Any],
    label: str,
    raw_score: float,
    athletes: Sequence[Mapping[str, Any]] = (),
    high_tv_score: float | None = None,
    additional: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an Observation for a high-TV label and its raw event score.

    The event is always the primary observed subject. Optional athlete Person
    nodes are additional observed subjects, keeping the contract useful for
    event-level and athlete-level labels without sport-specific fields.
    """

    subjects = [dict(event), *(dict(athlete) for athlete in athletes)]
    properties = [property_value(name="High-TV label", value=label)]
    if high_tv_score is not None:
        properties.append(
            property_value(
                name="High-TV score",
                value=quantitative_value(high_tv_score, unit_text="score"),
            )
        )
    return observation(
        about=subjects,
        measured_property=property_value(name="Raw score", unit_text="score"),
        value=raw_score,
        unit_text="score",
        additional_properties=properties,
        additional=additional,
    )


def person_athlete(
    *,
    identifier: str | int,
    name: str | None = None,
    additional: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema.org Person node used as an athlete reference."""

    node: dict[str, Any] = {
        "@type": schema_type("Person"),
        "identifier": str(identifier),
    }
    if name is not None:
        node["name"] = name
    if additional:
        for key, raw in additional.items():
            node[key if ":" in key or key.startswith("@") else f"oracle:{key}"] = raw
    return node


def sports_event(
    *,
    identifier: str | int,
    name: str | None = None,
    start_date: str | None = None,
    location_name: str | None = None,
    home_team: Mapping[str, Any] | None = None,
    away_team: Mapping[str, Any] | None = None,
    additional: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema.org SportsEvent node."""

    node: dict[str, Any] = {
        "@type": "SportsEvent",
        "identifier": str(identifier),
    }
    if name is not None:
        node["name"] = name
    if start_date is not None:
        node["startDate"] = start_date
    if location_name is not None:
        node["location"] = {"@type": "Place", "name": location_name}
    if home_team is not None:
        node["homeTeam"] = dict(home_team)
    if away_team is not None:
        node["awayTeam"] = dict(away_team)
    if additional:
        for key, raw in additional.items():
            node[key if ":" in key or key.startswith("@") else f"oracle:{key}"] = raw
    return node


def sports_team(
    *,
    identifier: str | int,
    name: str | None = None,
    additional: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema.org SportsTeam node."""

    node: dict[str, Any] = {
        "@type": "SportsTeam",
        "identifier": str(identifier),
    }
    if name is not None:
        node["name"] = name
    if additional:
        for key, raw in additional.items():
            node[key if ":" in key or key.startswith("@") else f"oracle:{key}"] = raw
    return node


def item_list(
    elements: Sequence[Mapping[str, Any]],
    *,
    name: str | None = None,
    list_order: str | None = "ItemListOrderDescending",
    additional: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema.org ItemList (e.g. Highest-value / high-TV board)."""

    node: dict[str, Any] = {
        "@type": "ItemList",
        "numberOfItems": len(elements),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index + 1,
                "item": dict(element),
            }
            for index, element in enumerate(elements)
        ],
    }
    if name is not None:
        node["name"] = name
    if list_order is not None:
        node["itemListOrder"] = list_order
    if additional:
        for key, raw in additional.items():
            node[key if ":" in key or key.startswith("@") else f"oracle:{key}"] = raw
    return node


def punch_list_item_list(
    items: Sequence[Mapping[str, Any]],
    *,
    name: str | None = None,
    season: int | None = None,
    week: int | None = None,
) -> dict[str, Any]:
    """Represent a prioritized audit punch list as schema.org ItemList.

    Each entry becomes a CreativeWork ListItem with priority/category as
    PropertyValue additionalProperty nodes so consumers can link without a
    sport-specific schema. Existing plain punch_list arrays remain the
    primary API; this shape is additive for JSON-LD linking.
    """

    elements: list[dict[str, Any]] = []
    for raw in items:
        item = dict(raw)
        additional_properties: list[dict[str, Any]] = []
        if "priority" in item:
            additional_properties.append(
                property_value(
                    name="priority",
                    value=item["priority"],
                    property_id="oracle:priority",
                )
            )
        if "category" in item:
            additional_properties.append(
                property_value(
                    name="category",
                    value=item["category"],
                    property_id="oracle:category",
                )
            )
        node: dict[str, Any] = {
            "@type": "CreativeWork",
            "name": str(item.get("title") or "punch item"),
            "description": str(item.get("detail") or ""),
        }
        if additional_properties:
            node["additionalProperty"] = additional_properties
        evidence = item.get("evidence")
        if isinstance(evidence, Mapping) and evidence:
            node["oracle:evidence"] = dict(evidence)
        elements.append(node)

    additional: dict[str, Any] = {"oracle:kind": "punch_list"}
    if season is not None:
        additional["oracle:season"] = season
    if week is not None:
        additional["oracle:week"] = week
    return with_context(
        item_list(
            elements,
            name=name or "Audit punch list",
            list_order="ItemListOrderAscending",
            additional=additional,
        )
    )


def with_context(node: Mapping[str, Any]) -> dict[str, Any]:
    """Return a JSON-LD document with the shared schema.org @context."""

    return {"@context": dict(SCHEMA_CONTEXT), **dict(node)}

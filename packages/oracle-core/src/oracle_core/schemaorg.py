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


def with_context(node: Mapping[str, Any]) -> dict[str, Any]:
    """Return a JSON-LD document with the shared schema.org @context."""

    return {"@context": dict(SCHEMA_CONTEXT), **dict(node)}

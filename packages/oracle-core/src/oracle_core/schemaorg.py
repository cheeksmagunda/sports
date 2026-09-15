"""schema.org vocabulary helpers for shared Oracle data contracts.

Prefer schema.org types and properties for cross-sport abstractions and
entity linking: Person, SportsTeam, SportsOrganization, SportsEvent, Place,
Role/OrganizationRole, identifier/PropertyValue, sameAs, Observation,
QuantitativeValue, and ItemList.

Hierarchy for shared portfolio contracts:
1. schema.org first (identity, events, places, observations, lists).
2. IPTC Sport Schema only where schema.org is weak (sport-specific
   participation, competitions, statistics) -- keep that mapping in apps
   or a later crosswalk, not forced into these helpers.
3. PROV-O for provenance (wasGeneratedBy / wasAttributedTo style claims)
   when source/time/process attribution is required; see drive research
   and issue #199. Compact ``prov_*`` helpers below are optional additives.

Extend only with clearly namespaced additional properties
(``https://oracle.local/vocab#...`` or compact ``oracle:``) when schema.org
has no fit. Sport apps map provider payloads onto these shapes; oracle-core
does not import sport packages. Never assert ``sameAs`` from a fuzzy
name+team match -- only authoritative URL/URI identity refs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

SCHEMA_ORG = "https://schema.org/"
ORACLE_VOCAB = "https://oracle.local/vocab#"

# Compact aliases used in JSON-LD @context maps.
PROV_NS = "http://www.w3.org/ns/prov#"

SCHEMA_CONTEXT: dict[str, str] = {
    "@vocab": SCHEMA_ORG,
    "schema": SCHEMA_ORG,
    "oracle": ORACLE_VOCAB,
    "prov": PROV_NS,
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
    same_as: str | Sequence[str] | None = None,
    identifiers: Sequence[Mapping[str, Any]] | None = None,
    additional: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema.org Person node used as an athlete reference."""

    node: dict[str, Any] = {
        "@type": schema_type("Person"),
        "identifier": str(identifier),
    }
    if name is not None:
        node["name"] = name
    if same_as is not None:
        node["sameAs"] = same_as_refs(same_as)
    if identifiers:
        node = attach_identifiers(node, *identifiers)
    return _apply_additional(node, additional)


def sports_event(
    *,
    identifier: str | int,
    name: str | None = None,
    start_date: str | None = None,
    location_name: str | None = None,
    location: Mapping[str, Any] | None = None,
    home_team: Mapping[str, Any] | None = None,
    away_team: Mapping[str, Any] | None = None,
    same_as: str | Sequence[str] | None = None,
    identifiers: Sequence[Mapping[str, Any]] | None = None,
    additional: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema.org SportsEvent node.

    Prefer passing a full ``location`` Place node. ``location_name`` remains as
    a convenience that builds a minimal Place.
    """

    node: dict[str, Any] = {
        "@type": "SportsEvent",
        "identifier": str(identifier),
    }
    if name is not None:
        node["name"] = name
    if start_date is not None:
        node["startDate"] = start_date
    if location is not None:
        node["location"] = dict(location)
    elif location_name is not None:
        node["location"] = place(name=location_name)
    if home_team is not None:
        node["homeTeam"] = dict(home_team)
    if away_team is not None:
        node["awayTeam"] = dict(away_team)
    if same_as is not None:
        node["sameAs"] = same_as_refs(same_as)
    if identifiers:
        node = attach_identifiers(node, *identifiers)
    return _apply_additional(node, additional)


def sports_team(
    *,
    identifier: str | int,
    name: str | None = None,
    sport: str | None = None,
    member_of: Mapping[str, Any] | None = None,
    same_as: str | Sequence[str] | None = None,
    identifiers: Sequence[Mapping[str, Any]] | None = None,
    additional: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema.org SportsTeam node."""

    node: dict[str, Any] = {
        "@type": "SportsTeam",
        "identifier": str(identifier),
    }
    if name is not None:
        node["name"] = name
    if sport is not None:
        node["sport"] = sport
    if member_of is not None:
        node["memberOf"] = dict(member_of)
    if same_as is not None:
        node["sameAs"] = same_as_refs(same_as)
    if identifiers:
        node = attach_identifiers(node, *identifiers)
    return _apply_additional(node, additional)


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
    return _apply_additional(node, additional)


def _apply_additional(node: dict[str, Any], additional: Mapping[str, Any] | None) -> dict[str, Any]:
    """Merge caller extras; namespace bare keys under oracle:."""

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


def _is_authoritative_uri(value: str) -> bool:
    """Return True when value looks like an absolute http(s)/urn identity ref."""

    lowered = value.strip().lower()
    return (
        lowered.startswith("https://")
        or lowered.startswith("http://")
        or lowered.startswith("urn:")
    )


def place(
    *,
    name: str | None = None,
    identifier: str | int | None = None,
    address: str | Mapping[str, Any] | None = None,
    same_as: str | Sequence[str] | None = None,
    additional: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema.org Place node (venue, city, or generic location)."""

    node: dict[str, Any] = {"@type": "Place"}
    if identifier is not None:
        node["identifier"] = str(identifier)
    if name is not None:
        node["name"] = name
    if isinstance(address, str):
        node["address"] = address
    elif isinstance(address, Mapping):
        node["address"] = dict(address)
    if same_as is not None:
        node["sameAs"] = same_as_refs(same_as)
    return _apply_additional(node, additional)


def sports_organization(
    *,
    identifier: str | int,
    name: str | None = None,
    sport: str | None = None,
    same_as: str | Sequence[str] | None = None,
    identifiers: Sequence[Mapping[str, Any]] | None = None,
    additional: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema.org SportsOrganization node (league, federation, club org)."""

    node: dict[str, Any] = {
        "@type": "SportsOrganization",
        "identifier": str(identifier),
    }
    if name is not None:
        node["name"] = name
    if sport is not None:
        node["sport"] = sport
    if same_as is not None:
        node["sameAs"] = same_as_refs(same_as)
    if identifiers:
        node["identifier"] = [
            str(identifier),
            *(dict(item) for item in identifiers),
        ]
    return _apply_additional(node, additional)


def organization_role(
    *,
    member: Mapping[str, Any],
    organization: Mapping[str, Any],
    role_name: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    additional: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema.org OrganizationRole for time-bounded membership.

    Dates belong on the role (not only on the person or team), matching
    schema.org Role / OrganizationRole guidance for roster periods.
    """

    node: dict[str, Any] = {
        "@type": "OrganizationRole",
        "member": dict(member),
        # schema.org OrganizationRole uses `roleName` plus the related org via
        # naming conventions; `oracle:organization` keeps the link explicit
        # when a pure schema.org property is ambiguous for our graph joins.
        "oracle:organization": dict(organization),
    }
    if role_name is not None:
        node["roleName"] = role_name
    if start_date is not None:
        node["startDate"] = start_date
    if end_date is not None:
        node["endDate"] = end_date
    return _apply_additional(node, additional)


def identifier_value(
    *,
    value: str | int,
    property_id: str,
    name: str | None = None,
    additional: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema.org PropertyValue suitable for structured ``identifier``."""

    return property_value(
        name=name or property_id,
        value=str(value),
        property_id=property_id,
        additional=additional,
    )


def attach_identifiers(
    node: Mapping[str, Any],
    *identifiers: Mapping[str, Any] | str | int,
) -> dict[str, Any]:
    """Return a copy of node with identifier expanded to Text and/or PropertyValue.

    Existing scalar identifier is preserved as the first list entry when present.
    """

    out = dict(node)
    existing = out.get("identifier")
    items: list[Any] = []
    if isinstance(existing, list):
        items.extend(existing)
    elif existing is not None:
        items.append(existing)
    for ident in identifiers:
        if isinstance(ident, Mapping):
            items.append(dict(ident))
        else:
            items.append(str(ident))
    out["identifier"] = items
    return out


def same_as_refs(values: str | Sequence[str]) -> str | list[str]:
    """Normalize authoritative sameAs URL/URI refs.

    Raises ValueError for non-absolute http(s)/urn values so callers cannot
    silently promote fuzzy name+team matches into identity links.
    """

    seq = [values] if isinstance(values, str) else list(values)
    if not seq:
        raise ValueError("sameAs requires at least one authoritative URL/URI")
    cleaned: list[str] = []
    for raw in seq:
        value = str(raw).strip()
        if not _is_authoritative_uri(value):
            raise ValueError(
                "sameAs must be an absolute http(s) or urn identity reference; "
                "do not assert sameAs from fuzzy name+team matches"
            )
        cleaned.append(value)
    return cleaned[0] if len(cleaned) == 1 else cleaned


def validate_typed_node(
    node: Mapping[str, Any],
    *,
    expected_type: str | Sequence[str],
    require_identifier: bool = False,
) -> list[str]:
    """Return a list of structural problems for a schema.org-like node (no I/O)."""

    problems: list[str] = []
    expected = {expected_type} if isinstance(expected_type, str) else set(expected_type)
    raw_type = node.get("@type")
    if raw_type is None:
        problems.append("missing @type")
    else:
        types = {raw_type} if isinstance(raw_type, str) else set(raw_type)
        if types.isdisjoint(expected):
            problems.append(f"@type {raw_type!r} not in {sorted(expected)}")
    if require_identifier and node.get("identifier") in (None, "", []):
        problems.append("missing identifier")
    return problems


def prov_attribution(
    *,
    entity: Mapping[str, Any],
    agent: Mapping[str, Any] | str | None = None,
    activity: Mapping[str, Any] | str | None = None,
    generated_at_time: str | None = None,
    additional: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach compact PROV-O provenance properties to an entity copy.

    Uses the ``prov:`` prefix registered in SCHEMA_CONTEXT. Prefer schema.org
    Observation for measured values; use this when the claim needs source /
    process attribution beyond Observation. See drive research and #199.
    """

    out = dict(entity)
    if agent is not None:
        out["prov:wasAttributedTo"] = dict(agent) if isinstance(agent, Mapping) else str(agent)
    if activity is not None:
        out["prov:wasGeneratedBy"] = (
            dict(activity) if isinstance(activity, Mapping) else str(activity)
        )
    if generated_at_time is not None:
        out["prov:generatedAtTime"] = generated_at_time
    return _apply_additional(out, additional)


def with_context(node: Mapping[str, Any]) -> dict[str, Any]:
    """Return a JSON-LD document with the shared schema.org @context."""

    return {"@context": dict(SCHEMA_CONTEXT), **dict(node)}

"""Cross-sport post-slate dossier contract and legacy dossier compatibility.

The portfolio needs a shared post-slate read contract that every sport can
populate with its own local scoring, lineup reconstruction, and provider
logic. This module therefore keeps the shared layer narrow and typed:

- schema.org anchors the portable shapes that already exist: ordered entries as
  ``ItemList``/``ListItem`` and measured outcomes as ``Observation`` with
  ``QuantitativeValue``;
- portfolio-specific semantics that schema.org does not name directly (for
  example a hindsight-only theoretical ceiling) travel in the existing
  ``oracle:`` JSON-LD namespace via ``additionalType`` and namespaced
  properties;
- sports continue to own feasibility rules, scoring algebra, provider payload
  parsing, and optimizer replay. ``oracle-core`` only defines the composition
  contract.

The new ``SlateDossier`` contract coexists with the earlier minimal ``Dossier``
entry/gap dataclasses so existing sport code can keep compiling until each app
migrates intentionally.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Any, Literal, cast

from oracle_core.schemaorg import (
    ORACLE_VOCAB,
    SCHEMA_CONTEXT,
    item_list,
    property_value,
    quantitative_value,
)

JsonScalar = str | int | float | bool | None


class Achievability(StrEnum):
    """How an entry relates to what was actually achievable or observed."""

    OBSERVED_FIELD = "observed_field"
    OUR_COMMITTED = "our_committed"
    THEORETICAL_HINDSIGHT_UPPER_BOUND = "theoretical_hindsight_upper_bound"


class ProvenanceStatus(StrEnum):
    """Shared provenance / censoring status for scores, gaps, and comparisons."""

    EXACT = "exact"
    CENSORED = "censored"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class SlotSelection:
    """One ordered slot in a contest entry payload."""

    position: int
    slot_id: str
    participant_id: str
    participant_name: str | None = None
    team_id: str | None = None
    team_name: str | None = None
    role_name: str | None = None

    def __post_init__(self) -> None:
        if self.position < 1:
            raise ValueError("Slot positions must be positive integers")
        if not self.slot_id:
            raise ValueError("slot_id is required")
        if not self.participant_id:
            raise ValueError("participant_id is required")

    def to_dict(self) -> dict[str, JsonScalar]:
        """Return a JSON-safe representation."""

        return {
            "position": self.position,
            "slot_id": self.slot_id,
            "participant_id": self.participant_id,
            "participant_name": self.participant_name,
            "team_id": self.team_id,
            "team_name": self.team_name,
            "role_name": self.role_name,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SlotSelection:
        """Build a slot selection from a mapping."""

        return cls(
            position=int(payload["position"]),
            slot_id=str(payload["slot_id"]),
            participant_id=str(payload["participant_id"]),
            participant_name=_optional_str(payload.get("participant_name")),
            team_id=_optional_str(payload.get("team_id")),
            team_name=_optional_str(payload.get("team_name")),
            role_name=_optional_str(payload.get("role_name")),
        )

    def to_jsonld(self) -> dict[str, Any]:
        """Return a ListItem-compatible JSON-LD node."""

        athlete: dict[str, Any] = {
            "@type": "Person",
            "identifier": self.participant_id,
        }
        if self.participant_name is not None:
            athlete["name"] = self.participant_name
        if self.team_id is not None or self.team_name is not None:
            team: dict[str, Any] = {"@type": "SportsTeam"}
            if self.team_id is not None:
                team["identifier"] = self.team_id
            if self.team_name is not None:
                team["name"] = self.team_name
            athlete["memberOf"] = team

        node: dict[str, Any] = {
            "@type": "ListItem",
            "position": self.position,
            "name": self.slot_id,
            "item": athlete,
        }
        if self.role_name is not None:
            node["oracle:roleName"] = self.role_name
        return node

    @classmethod
    def from_jsonld(cls, payload: Mapping[str, Any]) -> SlotSelection:
        """Rehydrate one slot from ``to_jsonld()`` output."""

        athlete = _mapping(payload["item"])
        team = _optional_mapping(athlete.get("memberOf"))
        return cls(
            position=int(payload["position"]),
            slot_id=str(payload["name"]),
            participant_id=str(athlete["identifier"]),
            participant_name=_optional_str(athlete.get("name")),
            team_id=_optional_str(team.get("identifier") if team else None),
            team_name=_optional_str(team.get("name") if team else None),
            role_name=_optional_str(payload.get("oracle:roleName")),
        )


@dataclass(frozen=True)
class FeasibilityConstraint:
    """One provider-neutral feasibility rule."""

    name: str
    value: JsonScalar
    operator: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Constraint name is required")

    def to_dict(self) -> dict[str, JsonScalar]:
        """Return a JSON-safe representation."""

        return {
            "name": self.name,
            "value": self.value,
            "operator": self.operator,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> FeasibilityConstraint:
        """Build a feasibility constraint from a mapping."""

        value = payload.get("value")
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            raise TypeError("Constraint values must be JSON scalars")
        return cls(
            name=str(payload["name"]),
            value=cast(JsonScalar, value),
            operator=_optional_str(payload.get("operator")),
            description=_optional_str(payload.get("description")),
        )

    def to_jsonld(self) -> dict[str, Any]:
        """Represent the constraint as a schema.org PropertyValue."""

        additional: dict[str, Any] = {}
        if self.operator is not None:
            additional["operator"] = self.operator
        if self.description is not None:
            additional["description"] = self.description
        return property_value(
            name=self.name,
            value=self.value,
            property_id=f"{ORACLE_VOCAB}feasibility_constraint",
            additional=additional or None,
        )

    @classmethod
    def from_jsonld(cls, payload: Mapping[str, Any]) -> FeasibilityConstraint:
        """Rehydrate a constraint from ``to_jsonld()`` output."""

        return cls(
            name=str(payload["name"]),
            value=cast(JsonScalar, payload.get("value")),
            operator=_optional_str(payload.get("oracle:operator")),
            description=_optional_str(payload.get("oracle:description")),
        )


@dataclass(frozen=True)
class SlateIdentity:
    """Cross-sport identity for a contest slate."""

    slate_id: str
    contest_id: str
    slate_date: str
    sport: str | None = None
    contest_name: str | None = None
    league: str | None = None

    def __post_init__(self) -> None:
        if not self.slate_id:
            raise ValueError("slate_id is required")
        if not self.contest_id:
            raise ValueError("contest_id is required")
        if not self.slate_date:
            raise ValueError("slate_date is required")

    def to_dict(self) -> dict[str, str | None]:
        """Return a JSON-safe representation."""

        return {
            "slate_id": self.slate_id,
            "contest_id": self.contest_id,
            "slate_date": self.slate_date,
            "sport": self.sport,
            "contest_name": self.contest_name,
            "league": self.league,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SlateIdentity:
        """Build a slate identity from a mapping."""

        return cls(
            slate_id=str(payload["slate_id"]),
            contest_id=str(payload["contest_id"]),
            slate_date=str(payload["slate_date"]),
            sport=_optional_str(payload.get("sport")),
            contest_name=_optional_str(payload.get("contest_name")),
            league=_optional_str(payload.get("league")),
        )

    def to_jsonld(self) -> dict[str, Any]:
        """Return a schema.org-anchored node for the slate identity."""

        identifiers: list[Any] = [self.slate_id]
        identifiers.append(
            property_value(
                name="contest_id",
                value=self.contest_id,
                property_id=f"{ORACLE_VOCAB}contest_id",
            )
        )
        node: dict[str, Any] = {
            "@type": "Thing",
            "additionalType": f"{ORACLE_VOCAB}SlateIdentity",
            "identifier": identifiers,
            "startDate": self.slate_date,
        }
        if self.contest_name is not None:
            node["name"] = self.contest_name
        if self.sport is not None:
            node["sport"] = self.sport
        if self.league is not None:
            node["oracle:league"] = self.league
        return node

    @classmethod
    def from_jsonld(cls, payload: Mapping[str, Any]) -> SlateIdentity:
        """Rehydrate a slate identity from ``to_jsonld()`` output."""

        identifiers = payload.get("identifier")
        slate_id = ""
        contest_id = ""
        if isinstance(identifiers, list):
            for value in identifiers:
                if isinstance(value, str) and not slate_id:
                    slate_id = value
                elif isinstance(value, Mapping) and value.get("name") == "contest_id":
                    contest_id = str(value.get("value"))
        elif isinstance(identifiers, str):
            slate_id = identifiers
        return cls(
            slate_id=slate_id,
            contest_id=contest_id,
            slate_date=str(payload["startDate"]),
            sport=_optional_str(payload.get("sport")),
            contest_name=_optional_str(payload.get("name")),
            league=_optional_str(payload.get("oracle:league")),
        )


@dataclass(frozen=True)
class KnowledgeState:
    """What was known, frozen, or versioned at decision time."""

    as_of: str
    decision_cutoff_at: str | None = None
    artifact_id: str | None = None
    artifact_version: str | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.as_of:
            raise ValueError("as_of is required")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""

        return {
            "as_of": self.as_of,
            "decision_cutoff_at": self.decision_cutoff_at,
            "artifact_id": self.artifact_id,
            "artifact_version": self.artifact_version,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> KnowledgeState:
        """Build a knowledge state from a mapping."""

        return cls(
            as_of=str(payload["as_of"]),
            decision_cutoff_at=_optional_str(payload.get("decision_cutoff_at")),
            artifact_id=_optional_str(payload.get("artifact_id")),
            artifact_version=_optional_str(payload.get("artifact_version")),
            notes=tuple(_string_sequence(payload.get("notes"))),
        )

    def to_jsonld(self) -> dict[str, Any]:
        """Return a schema.org-anchored node for the knowledge state."""

        node: dict[str, Any] = {
            "@type": "CreativeWork",
            "additionalType": f"{ORACLE_VOCAB}KnowledgeState",
            "dateCreated": self.as_of,
        }
        if self.decision_cutoff_at is not None:
            node["oracle:decisionCutoffAt"] = self.decision_cutoff_at
        if self.artifact_id is not None:
            node["oracle:artifactId"] = self.artifact_id
        if self.artifact_version is not None:
            node["version"] = self.artifact_version
        if self.notes:
            node["keywords"] = list(self.notes)
        return node

    @classmethod
    def from_jsonld(cls, payload: Mapping[str, Any]) -> KnowledgeState:
        """Rehydrate a knowledge state from ``to_jsonld()`` output."""

        keywords = payload.get("keywords")
        notes = tuple(_string_sequence(keywords)) if keywords is not None else ()
        return cls(
            as_of=str(payload["dateCreated"]),
            decision_cutoff_at=_optional_str(payload.get("oracle:decisionCutoffAt")),
            artifact_id=_optional_str(payload.get("oracle:artifactId")),
            artifact_version=_optional_str(payload.get("version")),
            notes=notes,
        )


@dataclass(frozen=True)
class FeasibleActionFamily:
    """Rule summary required to interpret what lineups were feasible."""

    ordered_slots: tuple[str, ...]
    constraints: tuple[FeasibilityConstraint, ...] = ()
    max_from_one_group: int | None = None
    summary: str | None = None

    def __post_init__(self) -> None:
        if not self.ordered_slots:
            raise ValueError("ordered_slots must not be empty")
        if len(set(self.ordered_slots)) != len(self.ordered_slots):
            raise ValueError("ordered_slots must be unique")
        if self.max_from_one_group is not None and self.max_from_one_group < 1:
            raise ValueError("max_from_one_group must be positive when provided")

    @property
    def entry_size(self) -> int:
        """Contest slot count K."""

        return len(self.ordered_slots)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""

        return {
            "ordered_slots": list(self.ordered_slots),
            "constraints": [constraint.to_dict() for constraint in self.constraints],
            "max_from_one_group": self.max_from_one_group,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> FeasibleActionFamily:
        """Build a feasible action family from a mapping."""

        return cls(
            ordered_slots=tuple(_string_sequence(payload.get("ordered_slots"))),
            constraints=tuple(
                FeasibilityConstraint.from_dict(_mapping(constraint))
                for constraint in _sequence(payload.get("constraints"))
            ),
            max_from_one_group=_optional_int(payload.get("max_from_one_group")),
            summary=_optional_str(payload.get("summary")),
        )

    def to_jsonld(self) -> dict[str, Any]:
        """Return a schema.org-anchored node for the feasible action family."""

        node: dict[str, Any] = {
            "@type": "Thing",
            "additionalType": f"{ORACLE_VOCAB}FeasibleActionFamily",
            "oracle:orderedSlots": list(self.ordered_slots),
            "oracle:entrySize": self.entry_size,
            "oracle:constraints": [constraint.to_jsonld() for constraint in self.constraints],
        }
        if self.max_from_one_group is not None:
            node["oracle:maxFromOneGroup"] = self.max_from_one_group
        if self.summary is not None:
            node["description"] = self.summary
        return node

    @classmethod
    def from_jsonld(cls, payload: Mapping[str, Any]) -> FeasibleActionFamily:
        """Rehydrate a feasible action family from ``to_jsonld()`` output."""

        return cls(
            ordered_slots=tuple(_string_sequence(payload.get("oracle:orderedSlots"))),
            constraints=tuple(
                FeasibilityConstraint.from_jsonld(_mapping(constraint))
                for constraint in _sequence(payload.get("oracle:constraints"))
            ),
            max_from_one_group=_optional_int(payload.get("oracle:maxFromOneGroup")),
            summary=_optional_str(payload.get("description")),
        )


@dataclass(frozen=True)
class SlateEntry:
    """One first-class entry record in committed slot order."""

    achievability: Achievability
    slots: tuple[SlotSelection, ...]
    entry_id: str | None = None
    label: str | None = None
    realized_score: float | None = None
    realized_payout: float | None = None
    payout_currency: str | None = None
    rank: int | None = None
    provenance: ProvenanceStatus = ProvenanceStatus.EXACT
    censoring_reason: str | None = None
    slot_order_basis: str | None = None

    def __post_init__(self) -> None:
        if not self.slots:
            raise ValueError("slots must not be empty")
        positions = tuple(slot.position for slot in self.slots)
        if len(set(positions)) != len(positions):
            raise ValueError("slot positions must be unique")

    @property
    def ordered_slots(self) -> tuple[SlotSelection, ...]:
        """Slots sorted by position."""

        return tuple(sorted(self.slots, key=lambda slot: slot.position))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""

        return {
            "achievability": self.achievability.value,
            "slots": [slot.to_dict() for slot in self.ordered_slots],
            "entry_id": self.entry_id,
            "label": self.label,
            "realized_score": self.realized_score,
            "realized_payout": self.realized_payout,
            "payout_currency": self.payout_currency,
            "rank": self.rank,
            "provenance": self.provenance.value,
            "censoring_reason": self.censoring_reason,
            "slot_order_basis": self.slot_order_basis,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SlateEntry:
        """Build a slate entry from a mapping."""

        return cls(
            achievability=Achievability(str(payload["achievability"])),
            slots=tuple(
                SlotSelection.from_dict(_mapping(slot)) for slot in _sequence(payload.get("slots"))
            ),
            entry_id=_optional_str(payload.get("entry_id")),
            label=_optional_str(payload.get("label")),
            realized_score=_optional_float(payload.get("realized_score")),
            realized_payout=_optional_float(payload.get("realized_payout")),
            payout_currency=_optional_str(payload.get("payout_currency")),
            rank=_optional_int(payload.get("rank")),
            provenance=ProvenanceStatus(
                str(payload.get("provenance", ProvenanceStatus.EXACT.value))
            ),
            censoring_reason=_optional_str(payload.get("censoring_reason")),
            slot_order_basis=_optional_str(payload.get("slot_order_basis")),
        )

    def to_jsonld(self) -> dict[str, Any]:
        """Return a schema.org ItemList representation."""

        node = item_list(
            [slot.to_jsonld()["item"] for slot in self.ordered_slots],
            name=self.label,
            list_order="https://schema.org/ItemListOrderAscending",
            additional={
                "achievability": self.achievability.value,
                "provenance": self.provenance.value,
            },
        )
        node["additionalType"] = f"{ORACLE_VOCAB}SlateEntry"
        node["itemListElement"] = [slot.to_jsonld() for slot in self.ordered_slots]
        if self.entry_id is not None:
            node["identifier"] = self.entry_id
        if self.realized_score is not None:
            node["oracle:realizedScore"] = self.realized_score
        if self.realized_payout is not None:
            node["oracle:realizedPayout"] = self.realized_payout
        if self.payout_currency is not None:
            node["oracle:payoutCurrency"] = self.payout_currency
        if self.rank is not None:
            node["position"] = self.rank
        if self.censoring_reason is not None:
            node["oracle:censoringReason"] = self.censoring_reason
        if self.slot_order_basis is not None:
            node["oracle:slotOrderBasis"] = self.slot_order_basis
        return node

    @classmethod
    def from_jsonld(cls, payload: Mapping[str, Any]) -> SlateEntry:
        """Rehydrate a slate entry from ``to_jsonld()`` output."""

        return cls(
            achievability=Achievability(str(payload["oracle:achievability"])),
            slots=tuple(
                SlotSelection.from_jsonld(_mapping(slot))
                for slot in _sequence(payload.get("itemListElement"))
            ),
            entry_id=_optional_str(payload.get("identifier")),
            label=_optional_str(payload.get("name")),
            realized_score=_optional_float(payload.get("oracle:realizedScore")),
            realized_payout=_optional_float(payload.get("oracle:realizedPayout")),
            payout_currency=_optional_str(payload.get("oracle:payoutCurrency")),
            rank=_optional_int(payload.get("position")),
            provenance=ProvenanceStatus(str(payload["oracle:provenance"])),
            censoring_reason=_optional_str(payload.get("oracle:censoringReason")),
            slot_order_basis=_optional_str(payload.get("oracle:slotOrderBasis")),
        )


@dataclass(frozen=True)
class GapMetric:
    """One explicit score-gap metric between two first-class entries."""

    name: str
    value: float | None
    provenance: ProvenanceStatus
    unit_text: str = "contest_points"
    note: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Gap metric name is required")
        if self.provenance is ProvenanceStatus.UNAVAILABLE and self.value is not None:
            raise ValueError("Unavailable gap metrics must not carry a numeric value")

    def to_dict(self) -> dict[str, JsonScalar]:
        """Return a JSON-safe representation."""

        return {
            "name": self.name,
            "value": self.value,
            "provenance": self.provenance.value,
            "unit_text": self.unit_text,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> GapMetric:
        """Build a gap metric from a mapping."""

        return cls(
            name=str(payload["name"]),
            value=_optional_float(payload.get("value")),
            provenance=ProvenanceStatus(str(payload["provenance"])),
            unit_text=str(payload.get("unit_text", "contest_points")),
            note=_optional_str(payload.get("note")),
        )

    def to_jsonld(self) -> dict[str, Any]:
        """Represent the metric as a schema.org Observation."""

        node: dict[str, Any] = {
            "@type": "Observation",
            "additionalType": f"{ORACLE_VOCAB}GapMetric",
            "name": self.name,
            "measuredProperty": property_value(name=self.name, unit_text=self.unit_text),
            "oracle:provenance": self.provenance.value,
        }
        if self.value is not None:
            node["value"] = quantitative_value(self.value, unit_text=self.unit_text)
        if self.note is not None:
            node["description"] = self.note
        return node

    @classmethod
    def from_jsonld(cls, payload: Mapping[str, Any]) -> GapMetric:
        """Rehydrate a gap metric from ``to_jsonld()`` output."""

        value = payload.get("value")
        parsed_value: float | None = None
        if isinstance(value, Mapping):
            parsed_value = _optional_float(value.get("value"))
        return cls(
            name=str(payload["name"]),
            value=parsed_value,
            provenance=ProvenanceStatus(str(payload["oracle:provenance"])),
            unit_text=str(_mapping(payload["measuredProperty"]).get("unitText", "contest_points")),
            note=_optional_str(payload.get("description")),
        )


@dataclass(frozen=True)
class GapAnalysis:
    """The three explicit shared score gaps required by issue #39."""

    our_to_field_winner_score_gap: GapMetric
    field_winner_to_theoretical_ceiling_gap: GapMetric
    our_to_theoretical_ceiling_gap: GapMetric

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""

        return {
            "our_to_field_winner_score_gap": self.our_to_field_winner_score_gap.to_dict(),
            "field_winner_to_theoretical_ceiling_gap": (
                self.field_winner_to_theoretical_ceiling_gap.to_dict()
            ),
            "our_to_theoretical_ceiling_gap": self.our_to_theoretical_ceiling_gap.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> GapAnalysis:
        """Build gap analysis from a mapping."""

        return cls(
            our_to_field_winner_score_gap=GapMetric.from_dict(
                _mapping(payload["our_to_field_winner_score_gap"])
            ),
            field_winner_to_theoretical_ceiling_gap=GapMetric.from_dict(
                _mapping(payload["field_winner_to_theoretical_ceiling_gap"])
            ),
            our_to_theoretical_ceiling_gap=GapMetric.from_dict(
                _mapping(payload["our_to_theoretical_ceiling_gap"])
            ),
        )

    def to_jsonld(self) -> dict[str, Any]:
        """Return a schema.org-anchored node for the gap analysis."""

        return {
            "@type": "Thing",
            "additionalType": f"{ORACLE_VOCAB}GapAnalysis",
            "oracle:ourToFieldWinnerScoreGap": self.our_to_field_winner_score_gap.to_jsonld(),
            "oracle:fieldWinnerToTheoreticalCeilingGap": (
                self.field_winner_to_theoretical_ceiling_gap.to_jsonld()
            ),
            "oracle:ourToTheoreticalCeilingGap": self.our_to_theoretical_ceiling_gap.to_jsonld(),
        }

    @classmethod
    def from_jsonld(cls, payload: Mapping[str, Any]) -> GapAnalysis:
        """Rehydrate gap analysis from ``to_jsonld()`` output."""

        return cls(
            our_to_field_winner_score_gap=GapMetric.from_jsonld(
                _mapping(payload["oracle:ourToFieldWinnerScoreGap"])
            ),
            field_winner_to_theoretical_ceiling_gap=GapMetric.from_jsonld(
                _mapping(payload["oracle:fieldWinnerToTheoreticalCeilingGap"])
            ),
            our_to_theoretical_ceiling_gap=GapMetric.from_jsonld(
                _mapping(payload["oracle:ourToTheoreticalCeilingGap"])
            ),
        )


@dataclass(frozen=True)
class RealizedOutcomes:
    """Outcome summary after the slate settles."""

    settled: bool | None = None
    settled_at: str | None = None
    field_size: int | None = None
    cash_line_score: float | None = None
    our_rank: int | None = None
    our_percentile: float | None = None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""

        return {
            "settled": self.settled,
            "settled_at": self.settled_at,
            "field_size": self.field_size,
            "cash_line_score": self.cash_line_score,
            "our_rank": self.our_rank,
            "our_percentile": self.our_percentile,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RealizedOutcomes:
        """Build realized outcomes from a mapping."""

        settled = payload.get("settled")
        return cls(
            settled=bool(settled) if isinstance(settled, bool) else None,
            settled_at=_optional_str(payload.get("settled_at")),
            field_size=_optional_int(payload.get("field_size")),
            cash_line_score=_optional_float(payload.get("cash_line_score")),
            our_rank=_optional_int(payload.get("our_rank")),
            our_percentile=_optional_float(payload.get("our_percentile")),
            notes=tuple(_string_sequence(payload.get("notes"))),
        )

    def to_jsonld(self) -> dict[str, Any]:
        """Return a schema.org-anchored node for realized outcomes."""

        node: dict[str, Any] = {
            "@type": "Observation",
            "additionalType": f"{ORACLE_VOCAB}RealizedOutcomes",
            "measuredProperty": property_value(name="realized_outcomes"),
        }
        if self.settled is not None:
            node["oracle:settled"] = self.settled
        if self.settled_at is not None:
            node["observationDate"] = self.settled_at
        if self.field_size is not None:
            node["oracle:fieldSize"] = self.field_size
        if self.cash_line_score is not None:
            node["oracle:cashLineScore"] = self.cash_line_score
        if self.our_rank is not None:
            node["oracle:ourRank"] = self.our_rank
        if self.our_percentile is not None:
            node["oracle:ourPercentile"] = self.our_percentile
        if self.notes:
            node["description"] = " | ".join(self.notes)
        return node

    @classmethod
    def from_jsonld(cls, payload: Mapping[str, Any]) -> RealizedOutcomes:
        """Rehydrate realized outcomes from ``to_jsonld()`` output."""

        description = _optional_str(payload.get("description"))
        notes = tuple(description.split(" | ")) if description else ()
        settled = payload.get("oracle:settled")
        return cls(
            settled=bool(settled) if isinstance(settled, bool) else None,
            settled_at=_optional_str(payload.get("observationDate")),
            field_size=_optional_int(payload.get("oracle:fieldSize")),
            cash_line_score=_optional_float(payload.get("oracle:cashLineScore")),
            our_rank=_optional_int(payload.get("oracle:ourRank")),
            our_percentile=_optional_float(payload.get("oracle:ourPercentile")),
            notes=notes,
        )


@dataclass(frozen=True)
class DataQualityAndCensoring:
    """How complete or censored the dossier's evidence is."""

    provenance: ProvenanceStatus
    leaderboard_capture_depth: int | None = None
    observed_entry_count: int | None = None
    missing_sources: tuple[str, ...] = ()
    censoring_reasons: tuple[str, ...] = ()
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""

        return {
            "provenance": self.provenance.value,
            "leaderboard_capture_depth": self.leaderboard_capture_depth,
            "observed_entry_count": self.observed_entry_count,
            "missing_sources": list(self.missing_sources),
            "censoring_reasons": list(self.censoring_reasons),
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> DataQualityAndCensoring:
        """Build data-quality metadata from a mapping."""

        return cls(
            provenance=ProvenanceStatus(str(payload["provenance"])),
            leaderboard_capture_depth=_optional_int(payload.get("leaderboard_capture_depth")),
            observed_entry_count=_optional_int(payload.get("observed_entry_count")),
            missing_sources=tuple(_string_sequence(payload.get("missing_sources"))),
            censoring_reasons=tuple(_string_sequence(payload.get("censoring_reasons"))),
            note=_optional_str(payload.get("note")),
        )

    def to_jsonld(self) -> dict[str, Any]:
        """Return a schema.org-anchored node for data quality."""

        node: dict[str, Any] = {
            "@type": "Thing",
            "additionalType": f"{ORACLE_VOCAB}DataQualityAndCensoring",
            "oracle:provenance": self.provenance.value,
            "oracle:missingSources": list(self.missing_sources),
            "oracle:censoringReasons": list(self.censoring_reasons),
        }
        if self.leaderboard_capture_depth is not None:
            node["oracle:leaderboardCaptureDepth"] = self.leaderboard_capture_depth
        if self.observed_entry_count is not None:
            node["oracle:observedEntryCount"] = self.observed_entry_count
        if self.note is not None:
            node["description"] = self.note
        return node

    @classmethod
    def from_jsonld(cls, payload: Mapping[str, Any]) -> DataQualityAndCensoring:
        """Rehydrate data-quality metadata from ``to_jsonld()`` output."""

        return cls(
            provenance=ProvenanceStatus(str(payload["oracle:provenance"])),
            leaderboard_capture_depth=_optional_int(payload.get("oracle:leaderboardCaptureDepth")),
            observed_entry_count=_optional_int(payload.get("oracle:observedEntryCount")),
            missing_sources=tuple(_string_sequence(payload.get("oracle:missingSources"))),
            censoring_reasons=tuple(_string_sequence(payload.get("oracle:censoringReasons"))),
            note=_optional_str(payload.get("description")),
        )


@dataclass(frozen=True)
class LearningSummary:
    """Human-readable postmortem summary and follow-up hooks."""

    summary: str | None = None
    takeaways: tuple[str, ...] = ()
    follow_ups: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""

        return {
            "summary": self.summary,
            "takeaways": list(self.takeaways),
            "follow_ups": list(self.follow_ups),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> LearningSummary:
        """Build a learning summary from a mapping."""

        return cls(
            summary=_optional_str(payload.get("summary")),
            takeaways=tuple(_string_sequence(payload.get("takeaways"))),
            follow_ups=tuple(_string_sequence(payload.get("follow_ups"))),
        )

    def to_jsonld(self) -> dict[str, Any]:
        """Return a schema.org-anchored node for learning summary."""

        node: dict[str, Any] = {
            "@type": "CreativeWork",
            "additionalType": f"{ORACLE_VOCAB}LearningSummary",
            "keywords": list(self.takeaways),
            "oracle:followUps": list(self.follow_ups),
        }
        if self.summary is not None:
            node["description"] = self.summary
        return node

    @classmethod
    def from_jsonld(cls, payload: Mapping[str, Any]) -> LearningSummary:
        """Rehydrate a learning summary from ``to_jsonld()`` output."""

        return cls(
            summary=_optional_str(payload.get("description")),
            takeaways=tuple(_string_sequence(payload.get("keywords"))),
            follow_ups=tuple(_string_sequence(payload.get("oracle:followUps"))),
        )


@dataclass(frozen=True)
class SlateDossier:
    """Top-level cross-sport post-slate dossier composition."""

    slate_identity: SlateIdentity
    knowledge_state: KnowledgeState
    feasible_action_family: FeasibleActionFamily
    our_committed_entry: SlateEntry
    best_observed_field_entry: SlateEntry
    theoretical_best_entry: SlateEntry
    gap_analysis: GapAnalysis
    realized_outcomes: RealizedOutcomes
    data_quality_and_censoring: DataQualityAndCensoring
    learning_summary: LearningSummary

    def __post_init__(self) -> None:
        expected_slots = self.feasible_action_family.ordered_slots
        entry_expectations = (
            (self.our_committed_entry, Achievability.OUR_COMMITTED, "our_committed_entry"),
            (
                self.best_observed_field_entry,
                Achievability.OBSERVED_FIELD,
                "best_observed_field_entry",
            ),
            (
                self.theoretical_best_entry,
                Achievability.THEORETICAL_HINDSIGHT_UPPER_BOUND,
                "theoretical_best_entry",
            ),
        )
        for entry, expected, label in entry_expectations:
            if entry.achievability is not expected:
                raise ValueError(f"{label} must use achievability {expected.value!r}")
            slot_ids = tuple(slot.slot_id for slot in entry.ordered_slots)
            if slot_ids != expected_slots:
                raise ValueError(f"{label} must be serialized in committed slot order")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""

        return {
            "slate_identity": self.slate_identity.to_dict(),
            "knowledge_state": self.knowledge_state.to_dict(),
            "feasible_action_family": self.feasible_action_family.to_dict(),
            "our_committed_entry": self.our_committed_entry.to_dict(),
            "best_observed_field_entry": self.best_observed_field_entry.to_dict(),
            "theoretical_best_entry": self.theoretical_best_entry.to_dict(),
            "gap_analysis": self.gap_analysis.to_dict(),
            "realized_outcomes": self.realized_outcomes.to_dict(),
            "data_quality_and_censoring": self.data_quality_and_censoring.to_dict(),
            "learning_summary": self.learning_summary.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SlateDossier:
        """Build a slate dossier from a mapping."""

        return cls(
            slate_identity=SlateIdentity.from_dict(_mapping(payload["slate_identity"])),
            knowledge_state=KnowledgeState.from_dict(_mapping(payload["knowledge_state"])),
            feasible_action_family=FeasibleActionFamily.from_dict(
                _mapping(payload["feasible_action_family"])
            ),
            our_committed_entry=SlateEntry.from_dict(_mapping(payload["our_committed_entry"])),
            best_observed_field_entry=SlateEntry.from_dict(
                _mapping(payload["best_observed_field_entry"])
            ),
            theoretical_best_entry=SlateEntry.from_dict(
                _mapping(payload["theoretical_best_entry"])
            ),
            gap_analysis=GapAnalysis.from_dict(_mapping(payload["gap_analysis"])),
            realized_outcomes=RealizedOutcomes.from_dict(_mapping(payload["realized_outcomes"])),
            data_quality_and_censoring=DataQualityAndCensoring.from_dict(
                _mapping(payload["data_quality_and_censoring"])
            ),
            learning_summary=LearningSummary.from_dict(_mapping(payload["learning_summary"])),
        )

    def to_jsonld(self) -> dict[str, Any]:
        """Return a schema.org-anchored JSON-LD document.

        The dossier itself is a ``CreativeWork`` with a stable portfolio-specific
        ``additionalType``. Ordered entries use ``ItemList``/``ListItem``; gap
        metrics and realized outcomes use ``Observation`` with
        ``QuantitativeValue``. Unmatched semantics travel in the ``oracle:``
        namespace defined in ``SCHEMA_CONTEXT``.
        """

        slate_name = self.slate_identity.contest_name or self.slate_identity.slate_id
        return {
            "@context": dict(SCHEMA_CONTEXT),
            "@type": "CreativeWork",
            "additionalType": f"{ORACLE_VOCAB}SlateDossier",
            "identifier": f"{self.slate_identity.contest_id}:{self.slate_identity.slate_id}",
            "name": f"Slate dossier for {slate_name}",
            "about": self.slate_identity.to_jsonld(),
            "oracle:knowledgeState": self.knowledge_state.to_jsonld(),
            "oracle:feasibleActionFamily": self.feasible_action_family.to_jsonld(),
            "oracle:ourCommittedEntry": self.our_committed_entry.to_jsonld(),
            "oracle:bestObservedFieldEntry": self.best_observed_field_entry.to_jsonld(),
            "oracle:theoreticalBestEntry": self.theoretical_best_entry.to_jsonld(),
            "oracle:gapAnalysis": self.gap_analysis.to_jsonld(),
            "oracle:realizedOutcomes": self.realized_outcomes.to_jsonld(),
            "oracle:dataQualityAndCensoring": self.data_quality_and_censoring.to_jsonld(),
            "oracle:learningSummary": self.learning_summary.to_jsonld(),
        }

    @classmethod
    def from_jsonld(cls, payload: Mapping[str, Any]) -> SlateDossier:
        """Rehydrate a ``SlateDossier`` from this module's JSON-LD output."""

        return cls(
            slate_identity=SlateIdentity.from_jsonld(_mapping(payload["about"])),
            knowledge_state=KnowledgeState.from_jsonld(_mapping(payload["oracle:knowledgeState"])),
            feasible_action_family=FeasibleActionFamily.from_jsonld(
                _mapping(payload["oracle:feasibleActionFamily"])
            ),
            our_committed_entry=SlateEntry.from_jsonld(
                _mapping(payload["oracle:ourCommittedEntry"])
            ),
            best_observed_field_entry=SlateEntry.from_jsonld(
                _mapping(payload["oracle:bestObservedFieldEntry"])
            ),
            theoretical_best_entry=SlateEntry.from_jsonld(
                _mapping(payload["oracle:theoreticalBestEntry"])
            ),
            gap_analysis=GapAnalysis.from_jsonld(_mapping(payload["oracle:gapAnalysis"])),
            realized_outcomes=RealizedOutcomes.from_jsonld(
                _mapping(payload["oracle:realizedOutcomes"])
            ),
            data_quality_and_censoring=DataQualityAndCensoring.from_jsonld(
                _mapping(payload["oracle:dataQualityAndCensoring"])
            ),
            learning_summary=LearningSummary.from_jsonld(
                _mapping(payload["oracle:learningSummary"])
            ),
        )


def gap_metric_from_entries(
    name: str,
    from_entry: SlateEntry,
    to_entry: SlateEntry,
    *,
    unit_text: str = "contest_points",
    note: str | None = None,
) -> GapMetric:
    """Compute one named gap metric from two first-class entry records."""

    provenance = _gap_provenance(from_entry.provenance, to_entry.provenance)
    if provenance is ProvenanceStatus.UNAVAILABLE:
        return GapMetric(
            name=name,
            value=None,
            provenance=provenance,
            unit_text=unit_text,
            note=note,
        )
    if from_entry.realized_score is None or to_entry.realized_score is None:
        return GapMetric(
            name=name,
            value=None,
            provenance=ProvenanceStatus.UNAVAILABLE,
            unit_text=unit_text,
            note=note,
        )
    return GapMetric(
        name=name,
        value=to_entry.realized_score - from_entry.realized_score,
        provenance=provenance,
        unit_text=unit_text,
        note=note,
    )


def build_gap_analysis(
    our_committed_entry: SlateEntry,
    best_observed_field_entry: SlateEntry,
    theoretical_best_entry: SlateEntry,
) -> GapAnalysis:
    """Build the three explicit gap metrics required by the shared contract."""

    return GapAnalysis(
        our_to_field_winner_score_gap=gap_metric_from_entries(
            "our_to_field_winner_score_gap",
            our_committed_entry,
            best_observed_field_entry,
        ),
        field_winner_to_theoretical_ceiling_gap=gap_metric_from_entries(
            "field_winner_to_theoretical_ceiling_gap",
            best_observed_field_entry,
            theoretical_best_entry,
        ),
        our_to_theoretical_ceiling_gap=gap_metric_from_entries(
            "our_to_theoretical_ceiling_gap",
            our_committed_entry,
            theoretical_best_entry,
        ),
    )


def _gap_provenance(*statuses: ProvenanceStatus) -> ProvenanceStatus:
    if any(status is ProvenanceStatus.UNAVAILABLE for status in statuses):
        return ProvenanceStatus.UNAVAILABLE
    if any(status is ProvenanceStatus.CENSORED for status in statuses):
        return ProvenanceStatus.CENSORED
    if any(status is ProvenanceStatus.PARTIAL for status in statuses):
        return ProvenanceStatus.PARTIAL
    return ProvenanceStatus.EXACT


# ---------------------------------------------------------------------------
# Legacy compatibility surface used by current WNBA dossier code.
# ---------------------------------------------------------------------------


class EntryKind(str, Enum):  # noqa: UP042
    """Kind of legacy dossier entry."""

    COMMITTED = "committed"
    FIELD_BEST = "field_best"
    THEORETICAL_CEILING = "theoretical_ceiling"


class Exactness(str, Enum):  # noqa: UP042
    """Legacy certainty level of a gap measurement."""

    EXACT = "exact"
    LOWER_BOUND = "lower_bound"
    UNKNOWN = "unknown"


class CensoringReason(str, Enum):  # noqa: UP042
    """Legacy reason why a measurement is censored or partial."""

    UNOBSERVED = "unobserved"
    INCOMPLETE_LABELS = "incomplete_labels"
    LEADERBOARD_DEPTH = "leaderboard_depth"
    UNKNOWN_PLACEMENT = "unknown_placement"


@dataclass(frozen=True)
class DossierEntry:
    """Legacy entry contract kept until sport packages migrate to SlateDossier."""

    kind: EntryKind
    score: float
    achievable: bool
    slot_order_basis: Literal["committed", "as_entered", "optimal_resort"]
    censor_reason: CensoringReason | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "score": self.score,
            "achievable": self.achievable,
            "slot_order_basis": self.slot_order_basis,
            "censor_reason": self.censor_reason.value if self.censor_reason else None,
        }


@dataclass(frozen=True)
class Gap:
    """Legacy gap contract kept until sport packages migrate to SlateDossier."""

    from_kind: EntryKind
    to_kind: EntryKind
    value: float
    exactness: Exactness
    from_censor: CensoringReason | None = None
    to_censor: CensoringReason | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_kind": self.from_kind.value,
            "to_kind": self.to_kind.value,
            "value": self.value,
            "exactness": self.exactness.value,
            "from_censor": self.from_censor.value if self.from_censor else None,
            "to_censor": self.to_censor.value if self.to_censor else None,
        }


@dataclass(frozen=True)
class Dossier:
    """Legacy dossier contract kept until sport packages migrate to SlateDossier."""

    slate_date: str
    entries: dict[EntryKind, DossierEntry]
    gap_to_field: Gap
    gap_field_to_ceiling: Gap
    gap_to_ceiling: Gap

    def to_dict(self) -> dict[str, Any]:
        return {
            "slate_date": self.slate_date,
            "entries": {key.value: value.to_dict() for key, value in self.entries.items()},
            "gap_to_field": self.gap_to_field.to_dict(),
            "gap_field_to_ceiling": self.gap_field_to_ceiling.to_dict(),
            "gap_to_ceiling": self.gap_to_ceiling.to_dict(),
        }


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("Expected a mapping")
    return value


def _optional_mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _sequence(value: Any) -> Sequence[Any]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError("Expected a sequence")
    return value


def _string_sequence(value: Any) -> tuple[str, ...]:
    return tuple(str(item) for item in _sequence(value))


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)

"""Provider-neutral dossier entry and gap schema for contest analysis.

A dossier entry represents a single contest entry (our committed pick, field
winner, or theoretical ceiling) with its score and metadata. Gaps quantify the
performance difference between entries with explicit censoring semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal


class EntryKind(str, Enum):  # noqa: UP042
    """Kind of dossier entry."""

    COMMITTED = "committed"
    FIELD_BEST = "field_best"
    THEORETICAL_CEILING = "theoretical_ceiling"


class Exactness(str, Enum):  # noqa: UP042
    """Certainty level of a gap measurement."""

    EXACT = "exact"
    LOWER_BOUND = "lower_bound"
    UNKNOWN = "unknown"


class CensoringReason(str, Enum):  # noqa: UP042
    """Why a measurement is censored or partially known."""

    UNOBSERVED = "unobserved"
    INCOMPLETE_LABELS = "incomplete_labels"
    LEADERBOARD_DEPTH = "leaderboard_depth"
    UNKNOWN_PLACEMENT = "unknown_placement"


@dataclass(frozen=True)
class DossierEntry:
    """A single contest entry with score and metadata.

    Attributes:
        kind: Type of entry (our pick, field best, or theoretical best)
        score: Contest score for this entry
        achievable: Whether this score is guaranteed achievable (vs. theoretical)
        slot_order_basis: How the entry was scored ('committed', 'as_entered', 'optimal_resort')
        censor_reason: If score is uncertain, why (leaderboard depth, incomplete labels, etc.)
    """

    kind: EntryKind
    score: float
    achievable: bool
    slot_order_basis: Literal["committed", "as_entered", "optimal_resort"]
    censor_reason: CensoringReason | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "kind": self.kind.value,
            "score": self.score,
            "achievable": self.achievable,
            "slot_order_basis": self.slot_order_basis,
            "censor_reason": self.censor_reason.value if self.censor_reason else None,
        }


@dataclass(frozen=True)
class Gap:
    """Performance gap between two dossier entries.

    Attributes:
        from_kind: Kind of entry at the start of the gap
        to_kind: Kind of entry at the end of the gap
        value: Gap magnitude (to_score - from_score)
        exactness: Whether the gap is exact, lower-bound, or unknown
        from_censor: Censoring reason for the 'from' endpoint, if any
        to_censor: Censoring reason for the 'to' endpoint, if any
    """

    from_kind: EntryKind
    to_kind: EntryKind
    value: float
    exactness: Exactness
    from_censor: CensoringReason | None = None
    to_censor: CensoringReason | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
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
    """Complete dossier for a finalized slate.

    Attributes:
        slate_date: Contest slate date (YYYY-MM-DD)
        entries: Dict of EntryKind to DossierEntry for this slate
        gap_to_field: Gap from our entry to field best
        gap_field_to_ceiling: Gap from field best to theoretical ceiling
        gap_to_ceiling: Gap from our entry to theoretical ceiling
    """

    slate_date: str
    entries: dict[EntryKind, DossierEntry]
    gap_to_field: Gap
    gap_field_to_ceiling: Gap
    gap_to_ceiling: Gap

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "slate_date": self.slate_date,
            "entries": {k.value: v.to_dict() for k, v in self.entries.items()},
            "gap_to_field": self.gap_to_field.to_dict(),
            "gap_field_to_ceiling": self.gap_field_to_ceiling.to_dict(),
            "gap_to_ceiling": self.gap_to_ceiling.to_dict(),
        }

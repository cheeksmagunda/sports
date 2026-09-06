"""Coverage matrix row schema (STATUS vocabulary)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

CoverageStatus = Literal["known", "unknown", "blocked"]


@dataclass(frozen=True)
class SeasonCoverageRow:
    season: int
    status: CoverageStatus
    game_ids: tuple[int, ...] = ()
    value_presence_note: str = ""
    blocked_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def infer_status_from_seeds(game_ids: tuple[int, ...]) -> CoverageStatus:
    return "known" if game_ids else "unknown"

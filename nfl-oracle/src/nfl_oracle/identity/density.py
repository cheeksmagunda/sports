"""Offline identity density summaries (observation only)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from nfl_oracle.identity.map import IdentityMap, IdentityRecord


@dataclass(frozen=True)
class IdentityDensity:
    """Field-fill density over an IdentityMap (no secrets)."""

    n_identities: int
    n_with_display_name: int
    n_with_position: int
    n_with_team_id: int
    n_complete: int
    complete_ratio: float
    position_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_complete(record: IdentityRecord) -> bool:
    return bool(record.display_name) and bool(record.position) and record.team_id is not None


def summarize_identity_density(identity: IdentityMap) -> IdentityDensity:
    n_name = 0
    n_pos = 0
    n_team = 0
    n_complete = 0
    position_counts: dict[str, int] = {}
    for pid in identity.player_ids():
        record = identity.get(pid)
        if record is None:
            continue
        if record.display_name:
            n_name += 1
        if record.position:
            n_pos += 1
            key = str(record.position)
            position_counts[key] = position_counts.get(key, 0) + 1
        if record.team_id is not None:
            n_team += 1
        if _is_complete(record):
            n_complete += 1
    total = len(identity)
    ratio = (n_complete / total) if total else 0.0
    return IdentityDensity(
        n_identities=total,
        n_with_display_name=n_name,
        n_with_position=n_pos,
        n_with_team_id=n_team,
        n_complete=n_complete,
        complete_ratio=ratio,
        position_counts=dict(sorted(position_counts.items())),
    )

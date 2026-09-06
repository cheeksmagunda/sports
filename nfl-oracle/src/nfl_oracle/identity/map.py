"""Real-primary identity map stubs — no cross-app imports."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IdentityRecord:
    real_player_id: int
    display_name: str | None = None
    position: str | None = None
    team_id: int | None = None
    external_ids: dict[str, str] = field(default_factory=dict)


@dataclass
class IdentityMap:
    """In-memory map keyed by Real Sports player id."""

    _by_real: dict[int, IdentityRecord] = field(default_factory=dict)

    def upsert(self, record: IdentityRecord) -> None:
        self._by_real[record.real_player_id] = record

    def get(self, real_player_id: int) -> IdentityRecord | None:
        return self._by_real.get(real_player_id)

    def __len__(self) -> int:
        return len(self._by_real)

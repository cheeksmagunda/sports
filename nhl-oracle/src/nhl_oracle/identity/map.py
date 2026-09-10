"""NHL identity map keyed by the provider's primary player id."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class NhlIdentityRecord:
    real_player_id: int
    display_name: str | None = None
    position: str | None = None
    team_id: int | None = None
    external_ids: dict[str, str] = field(default_factory=dict)


@dataclass
class NhlIdentityMap:
    """In-memory map keyed by the provider's primary NHL player id."""

    _by_id: dict[int, NhlIdentityRecord] = field(default_factory=dict)

    def upsert(self, record: NhlIdentityRecord) -> None:
        self._by_id[record.real_player_id] = record

    def get(self, real_player_id: int) -> NhlIdentityRecord | None:
        return self._by_id.get(real_player_id)

    def __len__(self) -> int:
        return len(self._by_id)

    def player_ids(self) -> list[int]:
        return sorted(self._by_id)

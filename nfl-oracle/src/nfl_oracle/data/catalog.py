"""Committed season → game-id seed catalog."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nfl_oracle.data.paths import resolve_data_paths


@dataclass(frozen=True)
class SeasonGameCatalog:
    """Seed anchors only — not a full season schedule."""

    seasons: dict[int, tuple[int, ...]]

    def game_ids(self, season: int) -> tuple[int, ...]:
        return self.seasons.get(season, ())

    def seasons_sorted(self) -> list[int]:
        return sorted(self.seasons)

    def to_json_obj(self) -> dict[str, list[int]]:
        return {str(k): list(v) for k, v in sorted(self.seasons.items())}


def load_season_game_catalog(path: Path | None = None) -> SeasonGameCatalog:
    catalog_path = path or (resolve_data_paths().catalog / "season_game_ids.json")
    raw: dict[str, Any] = json.loads(catalog_path.read_text(encoding="utf-8"))
    seasons: dict[int, tuple[int, ...]] = {}
    for key, values in raw.items():
        season = int(key)
        if not isinstance(values, list):
            raise ValueError(f"season {season} game ids must be a list")
        seasons[season] = tuple(int(g) for g in values)
    return SeasonGameCatalog(seasons=seasons)

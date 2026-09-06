"""Filesystem layout helpers for nfl-oracle data roots (no secrets)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nfl_oracle.common.paths import resolve_project_root


@dataclass(frozen=True)
class DataPaths:
    root: Path
    catalog: Path
    raw_corpus_g: Path
    artifacts: Path

    def corpus_g_game(self, season: int, game_id: int) -> Path:
        return self.raw_corpus_g / str(season) / str(game_id)


def resolve_data_paths(project_root: Path | None = None) -> DataPaths:
    root = project_root or resolve_project_root(__file__)
    data = root / "data"
    return DataPaths(
        root=data,
        catalog=data / "catalog",
        raw_corpus_g=data / "raw" / "corpus_g",
        artifacts=data / "artifacts",
    )

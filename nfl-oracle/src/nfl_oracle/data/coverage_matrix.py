"""Coverage matrix load/save helpers (STATUS vocabulary).

Wraps the on-disk ``data/catalog/coverage_matrix.json`` shape used by ingest
backfill without requiring a live CorpusGStore for read-only tooling.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from oracle_core.artifacts import atomic_write_json

from nfl_oracle.data.coverage import CoverageStatus, SeasonCoverageRow, infer_status_from_seeds
from nfl_oracle.data.paths import resolve_data_paths

SEASON_STATUSES: tuple[CoverageStatus, ...] = ("known", "unknown", "blocked")


@dataclass(frozen=True)
class CoverageMatrixDocument:
    generated_at: str | None
    seasons: dict[str, Any]
    gaps: list[Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "seasons": self.seasons,
            "gaps": self.gaps,
        }

    def season_rows(self) -> list[SeasonCoverageRow]:
        rows: list[SeasonCoverageRow] = []
        for key, block in sorted(self.seasons.items()):
            if not isinstance(block, dict):
                continue
            season = int(key)
            games = block.get("games") or {}
            game_ids = tuple(int(g) for g in games.keys()) if isinstance(games, dict) else ()
            status_raw = block.get("status") or infer_status_from_seeds(game_ids)
            status: CoverageStatus
            if status_raw in SEASON_STATUSES:
                status = status_raw
            else:
                status = infer_status_from_seeds(game_ids)
            rows.append(
                SeasonCoverageRow(
                    season=season,
                    status=status,
                    game_ids=game_ids,
                    value_presence_note=str(block.get("value_note") or ""),
                    blocked_reason=(
                        str(block.get("blocked_reason"))
                        if block.get("blocked_reason") is not None
                        else None
                    ),
                )
            )
        return rows


def coverage_matrix_file(catalog_dir: Path | None = None) -> Path:
    root = catalog_dir or resolve_data_paths().catalog
    return root / "coverage_matrix.json"


def load_coverage_matrix_doc(path: Path | None = None) -> CoverageMatrixDocument:
    target = path or coverage_matrix_file()
    if not target.is_file():
        return CoverageMatrixDocument(generated_at=None, seasons={}, gaps=[])
    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("coverage matrix must be a JSON object")
    seasons = raw.get("seasons") or {}
    if not isinstance(seasons, dict):
        raise TypeError("coverage matrix seasons must be an object")
    gaps = raw.get("gaps") or []
    if not isinstance(gaps, list):
        gaps = []
    generated = raw.get("generated_at")
    return CoverageMatrixDocument(
        generated_at=str(generated) if generated is not None else None,
        seasons=seasons,
        gaps=list(gaps),
    )


def save_coverage_matrix_doc(doc: CoverageMatrixDocument, path: Path | None = None) -> Path:
    target = path or coverage_matrix_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(target, doc.to_dict())
    return target


def catalog_matrix_alignment(
    *,
    catalog_seasons: dict[str, list[int]] | dict[int, tuple[int, ...]],
    matrix: CoverageMatrixDocument,
) -> dict[str, Any]:
    """Compare seed catalog seasons against coverage matrix rows (observation only)."""

    cat_keys = {str(k) for k in catalog_seasons.keys()}
    mat_keys = {str(k) for k in matrix.seasons.keys()}
    only_catalog = sorted(cat_keys - mat_keys)
    only_matrix = sorted(mat_keys - cat_keys)
    known_empty: list[str] = []
    for key, block in matrix.seasons.items():
        if not isinstance(block, dict):
            continue
        status = block.get("status")
        games = block.get("games") or {}
        game_n = len(games) if isinstance(games, dict) else 0
        if status == "known" and game_n == 0:
            known_empty.append(str(key))
    return {
        "catalog_season_count": len(cat_keys),
        "matrix_season_count": len(mat_keys),
        "seasons_only_in_catalog": only_catalog,
        "seasons_only_in_matrix": only_matrix,
        "known_status_with_zero_games": sorted(known_empty),
        "aligned_season_count": len(cat_keys & mat_keys),
        "contest_entry": False,
        "observation_only": True,
    }

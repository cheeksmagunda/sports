"""Read-only research summaries over catalog + coverage matrix."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nfl_oracle.data.catalog import SeasonGameCatalog, load_season_game_catalog
from nfl_oracle.data.coverage_matrix import load_coverage_matrix_doc
from nfl_oracle.data.density import summarize_coverage_density
from nfl_oracle.data.paths import resolve_data_paths


def research_data_summary(
    *,
    project_root: Path | None = None,
    catalog_path: Path | None = None,
    matrix_path: Path | None = None,
) -> dict[str, Any]:
    """Offline JSON summary for research service / daily-shadow artifacts."""

    paths = resolve_data_paths(project_root) if project_root is not None else resolve_data_paths()
    cat_file = catalog_path or (paths.catalog / "season_game_ids.json")
    mat_file = matrix_path or (paths.catalog / "coverage_matrix.json")

    catalog_error: str | None = None
    catalog: SeasonGameCatalog | None = None
    try:
        catalog = load_season_game_catalog(cat_file)
        seasons = catalog.to_json_obj()
        season_count = len(catalog.seasons)
        seed_game_count = sum(len(v) for v in catalog.seasons.values())
    except FileNotFoundError:
        seasons = {}
        season_count = 0
        seed_game_count = 0
        catalog_error = "catalog_missing"
    except (TypeError, ValueError, OSError) as exc:
        seasons = {}
        season_count = 0
        seed_game_count = 0
        catalog_error = type(exc).__name__

    matrix = load_coverage_matrix_doc(mat_file)
    rows = matrix.season_rows()
    status_counts: dict[str, int] = {"known": 0, "unknown": 0, "blocked": 0}
    for row in rows:
        status_counts[row.status] = status_counts.get(row.status, 0) + 1

    density = summarize_coverage_density(catalog=catalog, matrix=matrix)

    return {
        "contest_entry": False,
        "observation_only": True,
        "catalog": {
            "path_exists": cat_file.is_file(),
            "season_count": season_count,
            "seed_game_count": seed_game_count,
            "seasons": seasons,
            "error": catalog_error,
        },
        "coverage_matrix": {
            "path_exists": mat_file.is_file(),
            "generated_at": matrix.generated_at,
            "season_row_count": len(rows),
            "status_counts": status_counts,
            "gap_count": len(matrix.gaps),
        },
        "density": density.to_dict(),
    }

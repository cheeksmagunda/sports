"""Read-only research summaries over catalog + coverage matrix + schedule."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from nfl_oracle.calendar.schedule import research_schedule_summary
from nfl_oracle.data.catalog import SeasonGameCatalog, load_season_game_catalog
from nfl_oracle.data.coverage_matrix import catalog_matrix_alignment, load_coverage_matrix_doc
from nfl_oracle.data.density import summarize_coverage_density
from nfl_oracle.data.label_depth import label_depth_report
from nfl_oracle.data.paths import resolve_data_paths

if TYPE_CHECKING:
    from nfl_oracle.recommendations.high_tv import TvBoardCoverage


def _tv_board_coverage_from_disk(*, project_root: Path | None):
    """Scan on-disk Corpus C for reconstructable high Total-Value boards.

    Missing or empty corpus_c yields an empty coverage object so the summary
    stays on the raw rung. Parse errors on individual contests are skipped by
    ``iter_contests``; store/root failures also degrade to empty coverage.

    Imports are local to avoid data <-> contests <-> recommendations cycles.
    """

    from nfl_oracle.recommendations.high_tv import TvBoardCoverage, tv_board_coverage_from_contests

    try:
        from nfl_oracle.contests.parse import iter_contests
        from nfl_oracle.contests.store import ContestStore

        store = ContestStore(project=project_root) if project_root is not None else ContestStore()
        if not store.root.exists():
            return TvBoardCoverage()
        return tv_board_coverage_from_contests(iter_contests(store, finalized_only=True))
    except (OSError, TypeError, ValueError):
        return TvBoardCoverage()


def research_data_summary(
    *,
    project_root: Path | None = None,
    catalog_path: Path | None = None,
    matrix_path: Path | None = None,
    identity_players_path: Path | None = None,
    schedule_path: Path | None = None,
    tv_board_coverage: TvBoardCoverage | None = None,
) -> dict[str, Any]:
    """Offline JSON summary for research service / daily-shadow artifacts."""

    paths = resolve_data_paths(project_root) if project_root is not None else resolve_data_paths()
    cat_file = catalog_path or (paths.catalog / "season_game_ids.json")
    mat_file = matrix_path or (paths.catalog / "coverage_matrix.json")

    catalog_error: str | None = None
    catalog: SeasonGameCatalog | None = None
    seasons: dict[str, list[int]] = {}
    try:
        catalog = load_season_game_catalog(cat_file)
        seasons = catalog.to_json_obj()
        season_count = len(catalog.seasons)
        seed_game_count = sum(len(v) for v in catalog.seasons.values())
    except FileNotFoundError:
        season_count = 0
        seed_game_count = 0
        catalog_error = "catalog_missing"
    except (TypeError, ValueError, OSError) as exc:
        season_count = 0
        seed_game_count = 0
        catalog_error = type(exc).__name__

    matrix = load_coverage_matrix_doc(mat_file)
    rows = matrix.season_rows()
    status_counts: dict[str, int] = {"known": 0, "unknown": 0, "blocked": 0}
    for row in rows:
        status_counts[row.status] = status_counts.get(row.status, 0) + 1

    density = summarize_coverage_density(catalog=catalog, matrix=matrix)
    # Prefer an explicit coverage arg (tests); otherwise scan on-disk Corpus C
    # so offline summary upgrades raw -> high-TV without a manual arg. Missing
    # corpus_c keeps the raw rung. Catalog seasons the matrix has not reached
    # are listed unlabeled; no year cap is applied.
    coverage = (
        tv_board_coverage
        if tv_board_coverage is not None
        else _tv_board_coverage_from_disk(project_root=project_root)
    )
    depth = label_depth_report(
        matrix,
        catalog_seasons=sorted(catalog.seasons) if catalog else (),
        tv_board_game_ids=coverage.game_ids,
        tv_board_seasons=coverage.seasons,
    )
    alignment = catalog_matrix_alignment(catalog_seasons=seasons, matrix=matrix)
    schedule = research_schedule_summary(
        project_root=project_root,
        schedule_path=schedule_path,
        catalog_seed_count=seed_game_count,
        catalog_seasons=seasons,
    )
    # Local import avoids identity <-> data package init cycles.
    from nfl_oracle.identity.load import research_identity_summary

    identity = research_identity_summary(
        project_root=project_root,
        players_path=identity_players_path,
    )

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
            "alignment": alignment,
        },
        "schedule": schedule,
        "density": density.to_dict(),
        "label_depth": depth,
        "tv_board_coverage": coverage.to_dict(),
        "identity": identity,
    }

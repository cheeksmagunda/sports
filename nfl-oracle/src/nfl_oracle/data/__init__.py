"""NFL data-layer scaffolding: catalog, coverage, paths."""

from nfl_oracle.data.catalog import SeasonGameCatalog, load_season_game_catalog
from nfl_oracle.data.coverage import CoverageStatus, SeasonCoverageRow
from nfl_oracle.data.coverage_matrix import (
    CoverageMatrixDocument,
    load_coverage_matrix_doc,
    save_coverage_matrix_doc,
)
from nfl_oracle.data.paths import DataPaths, resolve_data_paths

__all__ = [
    "CoverageMatrixDocument",
    "CoverageStatus",
    "DataPaths",
    "SeasonCoverageRow",
    "SeasonGameCatalog",
    "load_coverage_matrix_doc",
    "load_season_game_catalog",
    "resolve_data_paths",
    "save_coverage_matrix_doc",
]

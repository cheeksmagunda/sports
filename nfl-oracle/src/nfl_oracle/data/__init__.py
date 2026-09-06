"""NFL data-layer scaffolding: catalog, coverage, paths."""

from nfl_oracle.data.catalog import SeasonGameCatalog, load_season_game_catalog
from nfl_oracle.data.coverage import CoverageStatus, SeasonCoverageRow
from nfl_oracle.data.coverage_matrix import (
    CoverageMatrixDocument,
    load_coverage_matrix_doc,
    save_coverage_matrix_doc,
)
from nfl_oracle.data.density import CoverageDensity, summarize_coverage_density
from nfl_oracle.data.paths import DataPaths, resolve_data_paths
from nfl_oracle.data.summary import research_data_summary

__all__ = [
    "CoverageDensity",
    "CoverageMatrixDocument",
    "CoverageStatus",
    "DataPaths",
    "SeasonCoverageRow",
    "SeasonGameCatalog",
    "load_coverage_matrix_doc",
    "load_season_game_catalog",
    "research_data_summary",
    "resolve_data_paths",
    "save_coverage_matrix_doc",
    "summarize_coverage_density",
]

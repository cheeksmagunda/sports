"""NFL data-layer scaffolding: catalog, coverage, paths."""

from nfl_oracle.data.catalog import SeasonGameCatalog, load_season_game_catalog
from nfl_oracle.data.coverage import CoverageStatus, SeasonCoverageRow
from nfl_oracle.data.paths import DataPaths, resolve_data_paths

__all__ = [
    "CoverageStatus",
    "DataPaths",
    "SeasonCoverageRow",
    "SeasonGameCatalog",
    "load_season_game_catalog",
    "resolve_data_paths",
]

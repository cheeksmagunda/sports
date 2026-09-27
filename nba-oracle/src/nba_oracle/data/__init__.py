"""NBA data-layer scaffolding: coverage vocabulary and paths."""

from nba_oracle.data.coverage import CoverageStatus, SeasonCoverageRow
from nba_oracle.data.coverage_matrix import empty_gap_matrix, matrix_to_dict
from nba_oracle.data.paths import app_root, corpus_g_root, coverage_matrix_path, data_root

__all__ = [
    "CoverageStatus",
    "SeasonCoverageRow",
    "app_root",
    "corpus_g_root",
    "coverage_matrix_path",
    "data_root",
    "empty_gap_matrix",
    "matrix_to_dict",
]

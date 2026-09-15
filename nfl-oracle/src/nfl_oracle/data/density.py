"""Offline coverage / catalog density summaries (observation only)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from nfl_oracle.data.catalog import SeasonGameCatalog
from nfl_oracle.data.coverage_matrix import CoverageMatrixDocument
from nfl_oracle.data.label_depth import LABEL_KIND_HIGH_TV, LABEL_KIND_RAW, NO_LABEL


@dataclass(frozen=True)
class CoverageDensity:
    """Seed + matrix density metrics for research STATUS honesty."""

    catalog_season_count: int
    catalog_seed_game_count: int
    mean_seeds_per_season: float
    min_seeds_per_season: int | None
    max_seeds_per_season: int | None
    matrix_season_row_count: int
    status_counts: dict[str, int]
    known_ratio: float
    matrix_game_id_count: int
    seasons_with_zero_matrix_games: int
    # #185/#189 ladder: which rung each classified season can train on. No
    # year cap is applied; an old season with only raw pre-boost Real score
    # is still fit-eligible.
    label_kind_counts: dict[str, int] = field(default_factory=dict)
    seasons_with_total_value_board: list[int] = field(default_factory=list)
    seasons_with_raw_score_only: list[int] = field(default_factory=list)
    seasons_without_labels: list[int] = field(default_factory=list)
    fit_eligible_season_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def summarize_coverage_density(
    *,
    catalog: SeasonGameCatalog | None,
    matrix: CoverageMatrixDocument,
) -> CoverageDensity:
    seasons = catalog.seasons if catalog is not None else {}
    season_count = len(seasons)
    seed_counts = [len(ids) for ids in seasons.values()]
    seed_total = sum(seed_counts)
    mean_seeds = (seed_total / season_count) if season_count else 0.0
    min_seeds = min(seed_counts) if seed_counts else None
    max_seeds = max(seed_counts) if seed_counts else None

    rows = matrix.season_rows()
    status_counts: dict[str, int] = {"known": 0, "unknown": 0, "blocked": 0}
    label_counts: dict[str, int] = {
        LABEL_KIND_HIGH_TV: 0,
        LABEL_KIND_RAW: 0,
        NO_LABEL: 0,
    }
    high_tv: list[int] = []
    raw_only: list[int] = []
    unlabeled: list[int] = []
    matrix_games = 0
    zero_games = 0
    for row in rows:
        status_counts[row.status] = status_counts.get(row.status, 0) + 1
        matrix_games += len(row.game_ids)
        if not row.game_ids:
            zero_games += 1
        kind = row.label_kind or NO_LABEL
        label_counts[kind] = label_counts.get(kind, 0) + 1
        if kind == LABEL_KIND_HIGH_TV:
            high_tv.append(row.season)
        elif kind == LABEL_KIND_RAW:
            raw_only.append(row.season)
        else:
            unlabeled.append(row.season)
    row_count = len(rows)
    known_ratio = (status_counts["known"] / row_count) if row_count else 0.0
    return CoverageDensity(
        catalog_season_count=season_count,
        catalog_seed_game_count=seed_total,
        mean_seeds_per_season=mean_seeds,
        min_seeds_per_season=min_seeds,
        max_seeds_per_season=max_seeds,
        matrix_season_row_count=row_count,
        status_counts=status_counts,
        known_ratio=known_ratio,
        matrix_game_id_count=matrix_games,
        seasons_with_zero_matrix_games=zero_games,
        label_kind_counts=label_counts,
        seasons_with_total_value_board=sorted(high_tv),
        seasons_with_raw_score_only=sorted(raw_only),
        seasons_without_labels=sorted(unlabeled),
        fit_eligible_season_count=len(high_tv) + len(raw_only),
    )

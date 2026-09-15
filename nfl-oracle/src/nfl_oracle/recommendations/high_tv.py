"""NFL wiring for shared high-potential training (issue #185).

Domain-free contracts and weight builders live in ``oracle_core.high_tv``.
This module maps Real Sports Corpus C / Corpus G shapes onto those APIs,
applies the label ladder (high-TV board else raw pre-boost Real score),
and reports full archive season depth (no artificial year cap).
Board/label serializations prefer schema.org via oracle_core.schemaorg.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from oracle_core.high_tv import (
    ArchiveSeasonDepth,
    HighTvBoard,
    build_high_tv_board,
    game_value_rank_weights,
    player_weights_from_values,
    sample_weights_for_labeled_rows,
    summarize_archive_season_depth,
)

from nfl_oracle.contests.field import counterfactual_best
from nfl_oracle.contests.parse import ParsedContest
from nfl_oracle.contests.schema import DraftStatRow

# Re-export shared names so NFL call sites can import from one place.
__all__ = [
    "ArchiveSeasonDepth",
    "HighTvBoard",
    "game_value_rank_weights",
    "high_tv_board_from_draft_stats",
    "player_high_tv_weights_from_draft_stats",
    "report_nfl_archive_season_depth",
    "sample_weights_for_history",
]


def high_tv_board_from_draft_stats(parsed: ParsedContest, *, top_n: int = 5) -> HighTvBoard | None:
    """NFL: reconstruct Highest-value / best-possible from contest draft_stats.

    Corpus C stores top-20 entries + draft_stats, not a separate Highest-value
    UI board. Ranking ignores draft_count so chalk popularity cannot enter.
    """

    values = {
        row.player_id: float(row.value) for row in parsed.draft_stats if row.value is not None
    }
    hindsight = counterfactual_best(parsed)
    boosts = [float(row.card_boost) for row in parsed.draft_stats]
    # TV board exists when the contest exposes draft-context multipliers or a
    # reconstructable best-possible set. Zero-boost eras still use value ranks
    # as raw highest Real score (ladder fallback).
    has_tv = bool(hindsight is not None) or any(b > 0 for b in boosts)
    return build_high_tv_board(
        contest_id=parsed.contest.contest_id,
        values=values,
        best_possible_player_ids=() if hindsight is None else hindsight.player_ids,
        top_n=top_n,
        complete_pool=False if hindsight is None else hindsight.complete_pool,
        has_total_value_board=has_tv,
        source="nfl_draft_stats_reconstructed",
    )


def player_high_tv_weights_from_draft_stats(
    rows: Sequence[DraftStatRow],
    *,
    top_fraction: float = 0.2,
    high_weight: float = 4.0,
    best_possible_ids: Iterable[int] = (),
    best_possible_weight: float = 5.0,
    base_weight: float = 1.0,
) -> dict[int, float]:
    """NFL adapter: draft_stats rows -> shared value-based sample weights."""

    values = {row.player_id: float(row.value) for row in rows if row.value is not None}
    return player_weights_from_values(
        values,
        top_fraction=top_fraction,
        high_weight=high_weight,
        best_possible_ids=best_possible_ids,
        best_possible_weight=best_possible_weight,
        base_weight=base_weight,
    )


def sample_weights_for_history(
    rows: Sequence[object],
    *,
    top_k: int = 5,
    high_weight: float = 4.0,
    base_weight: float = 1.0,
) -> list[float]:
    """NFL history rows -> shared per-game top-k high-TV sample weights."""

    return sample_weights_for_labeled_rows(
        rows, top_k=top_k, high_weight=high_weight, base_weight=base_weight
    )


def _season_game_counts_from_catalog(path: Path) -> dict[int, int]:
    import json

    raw = json.loads(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError("catalog_must_be_object")
    out: dict[int, int] = {}
    for season, games in raw.items():
        if isinstance(games, list):
            out[int(season)] = len(games)
        elif isinstance(games, int):
            out[int(season)] = games
    return out


def _season_game_counts_on_disk(corpus_g_root: Path) -> dict[int, int]:
    counts: dict[int, int] = {}
    if not corpus_g_root.is_dir():
        return counts
    for season_dir in sorted(corpus_g_root.iterdir()):
        if not season_dir.is_dir() or not season_dir.name.isdigit():
            continue
        n = 0
        for game_dir in season_dir.iterdir():
            if (
                game_dir.is_dir()
                and game_dir.name.isdigit()
                and (game_dir / "stats.json").is_file()
            ):
                n += 1
        if n:
            counts[int(season_dir.name)] = n
    return counts


def _season_game_counts_from_history_rows(rows: Sequence[Any]) -> dict[int, int]:
    """Count distinct games per season when rows expose kickoff year or season."""

    games: dict[int, set[int]] = {}
    for row in rows:
        season = getattr(row, "season", None)
        if season is None:
            kickoff = getattr(row, "kickoff_at", None)
            if kickoff is None:
                continue
            season = int(kickoff.year)
        else:
            season = int(season)
        games.setdefault(season, set()).add(int(row.game_id))
    return {season: len(ids) for season, ids in games.items()}


def report_nfl_archive_season_depth(
    *,
    project_root: Path | None = None,
    catalog_path: Path | None = None,
    corpus_g_root: Path | None = None,
    fit_rows: Sequence[Any] | None = None,
) -> ArchiveSeasonDepth:
    """Report catalog vs on-disk vs fit season depth for NFL Corpus G.

    Policy: use the FULL available archive (catalog seasons 2002+ when
    present). Never apply a ~2y lookback cap. Fit seasons default to every
    on-disk finalized game when ``fit_rows`` is omitted.
    """

    root = project_root or Path("nfl-oracle")
    catalog = catalog_path or (root / "data" / "catalog" / "season_game_ids.json")
    corpus = corpus_g_root or (root / "data" / "raw" / "corpus_g")
    catalog_counts = _season_game_counts_from_catalog(catalog) if catalog.is_file() else {}
    disk_counts = _season_game_counts_on_disk(corpus)
    fit_counts = _season_game_counts_from_history_rows(fit_rows) if fit_rows is not None else None
    return summarize_archive_season_depth(
        catalog_seasons=catalog_counts,
        on_disk_seasons=disk_counts,
        fit_seasons=fit_counts,
    )

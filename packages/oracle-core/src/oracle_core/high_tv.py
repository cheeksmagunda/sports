"""Domain-free high-potential training contracts and dataset helpers.

Sport apps train across the FULL available archive depth (no artificial year
cap). Appearance counts and "good enough to win" chalk are not targets.

Label priority ladder (issue #185):
1. High Total-Value / Highest-value / best-possible board when that era
   exposes draft-context multipliers and a reconstructable TV board.
2. Else raw highest Real (or sport-equivalent) score BEFORE draft-context
   boost / multipliers. Older seasons without boosts or TV boards remain
   usable under this fallback.

A season is fit-eligible when ANY rung of the ladder has labels. Do not drop
seasons merely because boosts or TV boards are missing.

This module stays provider-neutral: player ids are opaque ints, slate/game
keys are opaque ints, and values are finalized scoring units supplied by the
sport. Sport packages own ingest endpoints, position maps, and schedule
wiring; they call these helpers after parsing.

Shared serializations prefer schema.org: SportsEvent for slates/games,
Person for athletes, QuantitativeValue for scores, and ItemList for
Highest-value / high-TV boards (see ``oracle_core.schemaorg``). Oracle-only
fields use the ``oracle:`` namespace.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from oracle_core.schemaorg import (
    item_list,
    person_athlete,
    quantitative_value,
    sports_event,
    with_context,
)


class HighPotentialLabelKind(str, Enum):  # noqa: UP042
    """Which rung of the #185 training-label ladder a row/board used."""

    HIGH_TOTAL_VALUE_BOARD = "high_total_value_board"
    RAW_HIGHEST_SCORE = "raw_highest_score_pre_boost"


@dataclass(frozen=True)
class HighPotentialLabel:
    """One ownership-agnostic high-potential training label.

    ``score`` is the mathematical high-potential signal for that era:
    Total-Value under draft-context rules when available, otherwise the raw
    pre-boost score. ``kind`` records which ladder rung produced it.
    """

    player_id: int
    slate_id: int
    score: float
    kind: HighPotentialLabelKind
    season: int | None = None
    rank: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "player_id": self.player_id,
            "slate_id": self.slate_id,
            "score": self.score,
            "kind": self.kind.value,
            "season": self.season,
            "rank": self.rank,
        }

    def to_schemaorg(self) -> dict[str, Any]:
        """JSON-LD Person + QuantitativeValue for one high-potential label."""

        score = quantitative_value(
            self.score,
            name=self.kind.value,
            additional={"labelKind": self.kind.value},
        )
        node = person_athlete(
            identifier=self.player_id,
            additional={
                "score": score,
                "rank": self.rank,
                "season": self.season,
                "about": sports_event(identifier=self.slate_id),
            },
        )
        return with_context(node)


def select_label_kind(*, has_total_value_board: bool) -> HighPotentialLabelKind:
    """Return the highest available ladder rung for a slate/season."""

    if has_total_value_board:
        return HighPotentialLabelKind.HIGH_TOTAL_VALUE_BOARD
    return HighPotentialLabelKind.RAW_HIGHEST_SCORE


def build_high_potential_labels(
    values: Mapping[int, float],
    *,
    slate_id: int,
    has_total_value_board: bool,
    season: int | None = None,
    top_k: int | None = None,
) -> tuple[HighPotentialLabel, ...]:
    """Build ranked high-potential labels from a value map.

    When ``has_total_value_board`` is true, ``values`` should already be the
    Total-Value (or equivalent best-potential) numbers for that era. When
    false, ``values`` must be raw pre-boost scores. Ranking is always by
    descending score; popularity is never consulted.
    """

    if not values:
        return ()
    kind = select_label_kind(has_total_value_board=has_total_value_board)
    ranked = rank_player_ids_by_value(values)
    if top_k is not None:
        ranked = ranked[: max(1, top_k)]
    return tuple(
        HighPotentialLabel(
            player_id=pid,
            slate_id=slate_id,
            score=float(values[pid]),
            kind=kind,
            season=season,
            rank=index + 1,
        )
        for index, pid in enumerate(ranked)
    )


def game_is_fit_eligible(values: Mapping[int, float]) -> bool:
    """True when the slate has any usable high-potential (or raw) scores."""

    return any(True for _ in values)


class LabeledRow(Protocol):
    """Minimal row shape for sample-weight builders (duck-typed)."""

    @property
    def player_id(self) -> int: ...

    @property
    def game_id(self) -> int: ...

    @property
    def value(self) -> float | None: ...

    @property
    def did_not_play(self) -> bool: ...


@dataclass(frozen=True)
class HighTvBoard:
    """Ownership-agnostic high-potential board for one contest/slate.

    ``contest_id`` is whatever opaque id the sport archive uses. Ranking is by
    finalized value only; popularity / draft_count must not be supplied here.

    ``label_kind`` records whether this board is a Total-Value / best-possible
    reconstruction or a raw pre-boost highest-score fallback (#185 ladder).
    """

    contest_id: int
    value_ranked_player_ids: tuple[int, ...]
    top_value_player_ids: tuple[int, ...]
    best_possible_player_ids: tuple[int, ...]
    n_players_with_value: int
    complete_pool: bool
    label_kind: HighPotentialLabelKind = HighPotentialLabelKind.HIGH_TOTAL_VALUE_BOARD
    source: str = "value_rank_reconstructed"
    note: str = (
        "Highest-value / best-possible board when available; otherwise raw "
        "pre-boost highest score. Not win-chalk and not appearance frequency."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contest_id": self.contest_id,
            "value_ranked_player_ids": list(self.value_ranked_player_ids),
            "top_value_player_ids": list(self.top_value_player_ids),
            "best_possible_player_ids": list(self.best_possible_player_ids),
            "n_players_with_value": self.n_players_with_value,
            "complete_pool": self.complete_pool,
            "label_kind": self.label_kind.value,
            "source": self.source,
            "note": self.note,
        }

    def to_schemaorg(self) -> dict[str, Any]:
        """JSON-LD ItemList of Person athletes for the high-potential board."""

        elements = [
            person_athlete(
                identifier=pid,
                additional={"boardRank": index + 1},
            )
            for index, pid in enumerate(self.value_ranked_player_ids)
        ]
        board = item_list(
            elements,
            name="Highest value / high Total-Value board",
            additional={
                "labelKind": self.label_kind.value,
                "bestPossiblePlayerIds": list(self.best_possible_player_ids),
                "completePool": self.complete_pool,
                "source": self.source,
                "about": sports_event(identifier=self.contest_id),
            },
        )
        return with_context(board)


@dataclass(frozen=True)
class ArchiveSeasonDepth:
    """How much historical depth is cataloged, on disk, and used in a fit."""

    catalog_seasons: tuple[int, ...]
    on_disk_seasons: tuple[int, ...]
    fit_seasons: tuple[int, ...]
    catalog_game_count: int
    on_disk_game_count: int
    fit_game_count: int
    seasons_with_total_value_board: tuple[int, ...] = ()
    seasons_with_raw_score_only: tuple[int, ...] = ()
    year_cap: None = None  # explicit: never artificially cap archive depth

    def to_dict(self) -> dict[str, Any]:
        return {
            "catalog_seasons": list(self.catalog_seasons),
            "on_disk_seasons": list(self.on_disk_seasons),
            "fit_seasons": list(self.fit_seasons),
            "catalog_game_count": self.catalog_game_count,
            "on_disk_game_count": self.on_disk_game_count,
            "fit_game_count": self.fit_game_count,
            "seasons_with_total_value_board": list(self.seasons_with_total_value_board),
            "seasons_with_raw_score_only": list(self.seasons_with_raw_score_only),
            "year_cap": self.year_cap,
            "policy": "full_available_archive_no_year_cap",
            "label_ladder": [
                HighPotentialLabelKind.HIGH_TOTAL_VALUE_BOARD.value,
                HighPotentialLabelKind.RAW_HIGHEST_SCORE.value,
            ],
        }


def rank_player_ids_by_value(values: Mapping[int, float]) -> tuple[int, ...]:
    """Return player ids sorted by descending value (stable on player_id)."""

    return tuple(pid for pid, _ in sorted(values.items(), key=lambda kv: (-kv[1], kv[0])))


def build_high_tv_board(
    *,
    contest_id: int,
    values: Mapping[int, float],
    best_possible_player_ids: Sequence[int] = (),
    top_n: int = 5,
    complete_pool: bool = False,
    has_total_value_board: bool = True,
    source: str = "value_rank_reconstructed",
) -> HighTvBoard | None:
    """Build a high-potential board from a value map (sport supplies numbers).

    Pass ``has_total_value_board=False`` for eras with only raw pre-boost
    scores so ``label_kind`` records the ladder fallback.
    """

    if not values:
        return None
    ranked = rank_player_ids_by_value(values)
    kind = select_label_kind(has_total_value_board=has_total_value_board)
    return HighTvBoard(
        contest_id=contest_id,
        value_ranked_player_ids=ranked,
        top_value_player_ids=ranked[: max(1, top_n)],
        best_possible_player_ids=tuple(best_possible_player_ids),
        n_players_with_value=len(ranked),
        complete_pool=complete_pool,
        label_kind=kind,
        source=source,
    )


def player_weights_from_values(
    values: Mapping[int, float],
    *,
    top_fraction: float = 0.2,
    high_weight: float = 4.0,
    best_possible_ids: Iterable[int] = (),
    best_possible_weight: float = 5.0,
    base_weight: float = 1.0,
) -> dict[int, float]:
    """Map player_id -> sample weight from finalized values only."""

    if not values:
        return {}
    if not 0 < top_fraction <= 1:
        raise ValueError("top_fraction_out_of_range")
    ranked = rank_player_ids_by_value(values)
    cutoff_index = max(1, int(len(ranked) * top_fraction))
    top_ids = set(ranked[:cutoff_index])
    best_ids = set(best_possible_ids)
    weights: dict[int, float] = {}
    for pid in ranked:
        weight = base_weight
        if pid in top_ids:
            weight = max(weight, high_weight)
        if pid in best_ids:
            weight = max(weight, best_possible_weight)
        weights[pid] = weight
    return weights


def game_value_rank_weights(
    game_values: Mapping[int, float],
    *,
    top_k: int = 5,
    high_weight: float = 4.0,
    base_weight: float = 1.0,
) -> dict[int, float]:
    """Up-weight the top-k values in one game/slate (Highest-value proxy)."""

    if not game_values:
        return {}
    ranked = rank_player_ids_by_value(game_values)
    top = set(ranked[: max(1, top_k)])
    return {pid: (high_weight if pid in top else base_weight) for pid in ranked}


def sample_weights_for_labeled_rows(
    rows: Sequence[Any],
    *,
    top_k: int = 5,
    high_weight: float = 4.0,
    base_weight: float = 1.0,
) -> list[float]:
    """Per-row weights aligned with ``rows`` grouping by ``game_id``.

    Rows need ``player_id`` and ``game_id`` attributes (duck-typed). ``value``
    and ``did_not_play`` default to ``None`` and ``False`` when absent. DNP /
    missing-value rows keep ``base_weight``.
    """

    by_game: dict[int, dict[int, float]] = defaultdict(dict)
    for row in rows:
        if bool(getattr(row, "did_not_play", False)):
            continue
        value = getattr(row, "value", None)
        if value is None:
            continue
        game_id = int(row.game_id)
        player_id = int(row.player_id)
        by_game[game_id][player_id] = float(value)

    weight_by_game_player: dict[tuple[int, int], float] = {}
    for game_id, mapping in by_game.items():
        for pid, weight in game_value_rank_weights(
            mapping, top_k=top_k, high_weight=high_weight, base_weight=base_weight
        ).items():
            weight_by_game_player[(game_id, pid)] = weight

    out: list[float] = []
    for row in rows:
        key = (int(row.game_id), int(row.player_id))
        out.append(weight_by_game_player.get(key, base_weight))
    return out


def summarize_archive_season_depth(
    *,
    catalog_seasons: Mapping[int, int] | Mapping[str, int],
    on_disk_seasons: Mapping[int, int] | Mapping[str, int],
    fit_seasons: Mapping[int, int] | Mapping[str, int] | None = None,
    seasons_with_total_value_board: Sequence[int] = (),
    seasons_with_raw_score_only: Sequence[int] = (),
) -> ArchiveSeasonDepth:
    """Compare cataloged vs on-disk vs fit season depth (no year cap).

    Each mapping is ``season -> game_count``. Fit defaults to on-disk when the
    trainer uses every available finalized game without a lookback filter.
    Seasons remain eligible under the raw-score ladder rung when TV boards
    are absent.
    """

    def _norm(raw: Mapping[int, int] | Mapping[str, int]) -> dict[int, int]:
        out: dict[int, int] = {}
        for key, count in raw.items():
            out[int(key)] = int(count)
        return out

    catalog = _norm(catalog_seasons)
    disk = _norm(on_disk_seasons)
    fit = _norm(fit_seasons) if fit_seasons is not None else dict(disk)
    return ArchiveSeasonDepth(
        catalog_seasons=tuple(sorted(catalog)),
        on_disk_seasons=tuple(sorted(disk)),
        fit_seasons=tuple(sorted(fit)),
        catalog_game_count=sum(catalog.values()),
        on_disk_game_count=sum(disk.values()),
        fit_game_count=sum(fit.values()),
        seasons_with_total_value_board=tuple(
            sorted({int(s) for s in seasons_with_total_value_board})
        ),
        seasons_with_raw_score_only=tuple(sorted({int(s) for s in seasons_with_raw_score_only})),
    )

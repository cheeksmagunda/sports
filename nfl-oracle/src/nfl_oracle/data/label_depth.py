"""Classify archive depth by which training-label rung each season supports.

The #185 ladder, applied across the full 2002+ catalog with no year cap:

1. ``high_total_value_board`` when the era exposes draft-context multipliers or
   a reconstructable best-possible set, so a high Total-Value / Highest-value
   board can be rebuilt (``recommendations.high_tv.high_tv_board_from_draft_stats``).
2. ``raw_highest_score_pre_boost`` when only finalized Real value is present.

A season is fit-eligible when ANY rung has labels. Seasons are never dropped
for missing boosts or boards, and no season is dropped for being old.

Corpus G alone can only ever justify rung 2: box scores carry ``value`` but no
draft-context multiplier. Rung 1 is a Corpus C (contest) fact, so the upgrade
happens at report time from parsed contests, keeping ingest honest about what
it actually observed.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

from oracle_core.high_tv import HighPotentialLabelKind, select_label_kind
from oracle_core.schemaorg import item_list, quantitative_value, sports_event, with_context

from nfl_oracle.data.coverage_matrix import CoverageMatrixDocument

LABEL_KIND_HIGH_TV = HighPotentialLabelKind.HIGH_TOTAL_VALUE_BOARD.value
LABEL_KIND_RAW = HighPotentialLabelKind.RAW_HIGHEST_SCORE.value
LABEL_LADDER: tuple[str, ...] = (LABEL_KIND_HIGH_TV, LABEL_KIND_RAW)
NO_LABEL = "no_usable_label"


def game_label_kind(*, value_nonnull: int, has_total_value_board: bool = False) -> str | None:
    """Which ladder rung one ingested game supports, or None when unlabeled."""

    if int(value_nonnull) <= 0:
        return None
    return select_label_kind(has_total_value_board=bool(has_total_value_board)).value


@dataclass(frozen=True)
class SeasonLabelDepth:
    """Label-kind classification for one catalog season."""

    season: int
    label_kind: str | None
    status: str
    game_count: int
    games_with_value: int
    games_with_total_value_board: int
    boxes_total: int
    boxes_with_value: int
    tv_board_game_ids: tuple[int, ...]
    note: str

    @property
    def fit_eligible(self) -> bool:
        """True when any rung of the ladder has labels for this season."""

        return self.label_kind is not None

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["tv_board_game_ids"] = list(self.tv_board_game_ids)
        out["fit_eligible"] = self.fit_eligible
        return out


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def classify_season_label_depth(
    *,
    season: int,
    block: Mapping[str, Any],
    tv_board_game_ids: Iterable[int] = (),
    tv_board_seasons: Iterable[int] = (),
) -> SeasonLabelDepth:
    """Classify one coverage-matrix season block against the label ladder."""

    board_games = {int(g) for g in tv_board_game_ids}
    board_seasons = {int(s) for s in tv_board_seasons}
    games = block.get("games")
    games = games if isinstance(games, Mapping) else {}
    status = str(block.get("status") or "unknown")

    game_count = 0
    games_with_value = 0
    boxes_total = 0
    boxes_with_value = 0
    matched_boards: list[int] = []
    for key, game in games.items():
        if not isinstance(game, Mapping):
            continue
        game_count += 1
        game_id = _int(game.get("game_id") or key)
        boxes = _int(game.get("box_count"))
        valued = _int(game.get("value_nonnull"))
        boxes_total += boxes
        boxes_with_value += valued
        if valued > 0:
            games_with_value += 1
            if game_id in board_games:
                matched_boards.append(game_id)

    season_has_board = bool(matched_boards) or (season in board_seasons and games_with_value > 0)
    if games_with_value <= 0:
        label_kind: str | None = None
        note = (
            "no Real value observed on ingested boxes; not fit-eligible under "
            "either ladder rung yet"
        )
    else:
        label_kind = select_label_kind(has_total_value_board=season_has_board).value
        if season_has_board:
            note = (
                f"high Total-Value board reconstructable for {len(matched_boards) or 'some'} "
                f"contest game(s); Real value on {boxes_with_value}/{boxes_total} boxes"
            )
        else:
            note = (
                "no draft-context multipliers or best-possible set observed; using raw "
                f"pre-boost Real score on {boxes_with_value}/{boxes_total} boxes"
            )
    return SeasonLabelDepth(
        season=int(season),
        label_kind=label_kind,
        status=status,
        game_count=game_count,
        games_with_value=games_with_value,
        games_with_total_value_board=len(matched_boards),
        boxes_total=boxes_total,
        boxes_with_value=boxes_with_value,
        tv_board_game_ids=tuple(sorted(matched_boards)),
        note=note,
    )


def classify_matrix_label_depth(
    matrix: CoverageMatrixDocument,
    *,
    tv_board_game_ids: Iterable[int] = (),
    tv_board_seasons: Iterable[int] = (),
    catalog_seasons: Iterable[int] = (),
) -> tuple[SeasonLabelDepth, ...]:
    """Classify every season in a coverage matrix. No year cap is applied.

    ``catalog_seasons`` adds seed-catalog seasons the matrix has not reached
    yet, so the report spans the full cataloged archive instead of only what
    ingest happens to have written. Those seasons are reported honestly as
    unlabeled rather than assumed usable.
    """

    board_games = tuple(int(g) for g in tv_board_game_ids)
    board_seasons = tuple(int(s) for s in tv_board_seasons)
    out: list[SeasonLabelDepth] = []
    seen: set[int] = set()
    for key, block in matrix.seasons.items():
        if not isinstance(block, Mapping):
            continue
        try:
            season = int(key)
        except (TypeError, ValueError):
            continue
        seen.add(season)
        out.append(
            classify_season_label_depth(
                season=season,
                block=block,
                tv_board_game_ids=board_games,
                tv_board_seasons=board_seasons,
            )
        )
    for raw in catalog_seasons:
        season = int(raw)
        if season in seen:
            continue
        seen.add(season)
        out.append(
            classify_season_label_depth(
                season=season,
                block={"status": "unknown", "games": {}},
                tv_board_game_ids=board_games,
                tv_board_seasons=board_seasons,
            )
        )
    return tuple(sorted(out, key=lambda row: row.season))


def label_depth_report(
    matrix: CoverageMatrixDocument,
    *,
    tv_board_game_ids: Iterable[int] = (),
    tv_board_seasons: Iterable[int] = (),
    catalog_seasons: Iterable[int] = (),
) -> dict[str, Any]:
    """Offline report of which seasons can train on which ladder rung."""

    rows = classify_matrix_label_depth(
        matrix,
        tv_board_game_ids=tv_board_game_ids,
        tv_board_seasons=tv_board_seasons,
        catalog_seasons=catalog_seasons,
    )
    high_tv = [r.season for r in rows if r.label_kind == LABEL_KIND_HIGH_TV]
    raw_only = [r.season for r in rows if r.label_kind == LABEL_KIND_RAW]
    unlabeled = [r.season for r in rows if r.label_kind is None]
    counts = {
        LABEL_KIND_HIGH_TV: len(high_tv),
        LABEL_KIND_RAW: len(raw_only),
        NO_LABEL: len(unlabeled),
    }
    covered = [r.season for r in rows]
    return {
        "policy": "full_available_archive_no_year_cap",
        "year_cap": None,
        "label_ladder": list(LABEL_LADDER),
        "season_count": len(rows),
        "min_season": min(covered) if covered else None,
        "max_season": max(covered) if covered else None,
        "seasons": {str(r.season): r.to_dict() for r in rows},
        "seasons_with_total_value_board": high_tv,
        "seasons_with_raw_score_only": raw_only,
        "seasons_without_labels": unlabeled,
        "fit_eligible_seasons": sorted(high_tv + raw_only),
        "fit_eligible_game_count": sum(r.games_with_value for r in rows),
        "label_kind_counts": counts,
        "observation_only": True,
        "contest_entry": False,
    }


def label_depth_schemaorg(report: Mapping[str, Any]) -> dict[str, Any]:
    """JSON-LD ItemList of per-season label-kind classifications.

    TODO(#189): oracle-core has no Observation / measured-property helper on
    main yet. When the shared Observation contract lands, re-express each
    season entry as an Observation about a SportsEvent season instead of a
    QuantitativeValue inside an ItemList, and drop this note. Do not widen
    ``oracle_core.schemaorg`` from here.
    """

    seasons = report.get("seasons")
    seasons = seasons if isinstance(seasons, Mapping) else {}
    elements = []
    for key in sorted(seasons, key=lambda k: int(k)):
        entry = seasons[key]
        if not isinstance(entry, Mapping):
            continue
        elements.append(
            quantitative_value(
                float(entry.get("games_with_value") or 0),
                name=f"season {key} labeled games",
                additional={
                    "labelKind": entry.get("label_kind"),
                    "fitEligible": entry.get("fit_eligible"),
                    "about": sports_event(identifier=f"nfl-season-{key}", name=f"NFL {key} season"),
                },
            )
        )
    return with_context(
        item_list(
            elements,
            name="NFL archive label-kind depth",
            list_order="ItemListOrderAscending",
            additional={
                "labelLadder": list(LABEL_LADDER),
                "yearCap": None,
                "policy": report.get("policy"),
            },
        )
    )

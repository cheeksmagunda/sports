"""Max-season label-kind depth across the catalog (issue #189).

Offline only: fixtures stand in for the coverage matrix ingest writes and for
parsed Corpus C contests. No Real Sports auth and no live densify is required.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from nfl_oracle.contests.parse import ParsedContest
from nfl_oracle.contests.schema import (
    OBSERVED_SLOT_MULTIPLIERS,
    ContestRecord,
    DraftStatRow,
)
from nfl_oracle.data.coverage_matrix import CoverageMatrixDocument, catalog_matrix_alignment
from nfl_oracle.data.density import summarize_coverage_density
from nfl_oracle.data.label_depth import (
    LABEL_KIND_HIGH_TV,
    LABEL_KIND_RAW,
    NO_LABEL,
    classify_season_label_depth,
    game_label_kind,
    label_depth_report,
    label_depth_schemaorg,
)
from nfl_oracle.ingest.backfill import (
    CoverageCell,
    _label_kind_for_cell,
    _season_label_kind_from_games,
    _summarize_season_block,
)
from nfl_oracle.recommendations.high_tv import (
    TvBoardCoverage,
    nfl_label_depth_report,
    nfl_season_for_day,
    report_nfl_archive_season_depth,
    tv_board_coverage_from_contests,
)


def _game(game_id: int, *, boxes: int, valued: int, label_kind: str | None = None) -> dict:
    cell = {"game_id": game_id, "box_count": boxes, "value_nonnull": valued}
    if label_kind is not None:
        cell["label_kind"] = label_kind
    return cell


def _matrix() -> CoverageMatrixDocument:
    return CoverageMatrixDocument(
        generated_at="2026-09-15T00:00:00+00:00",
        seasons={
            # Oldest cataloged season: value present, no contest board.
            "2002": {"status": "known", "games": {"126323": _game(126323, boxes=40, valued=38)}},
            # Modern season with a reconstructable Total-Value board.
            "2024": {"status": "known", "games": {"18790": _game(18790, boxes=44, valued=44)}},
            # Ingested but Real value all-null.
            "2010": {"status": "known", "games": {"124194": _game(124194, boxes=41, valued=0)}},
            # Tracked but not reached.
            "2013": {"status": "unknown", "games": {}},
        },
        gaps=[],
    )


def test_game_label_kind_follows_the_ladder() -> None:
    assert game_label_kind(value_nonnull=0) is None
    assert game_label_kind(value_nonnull=12) == LABEL_KIND_RAW
    assert game_label_kind(value_nonnull=12, has_total_value_board=True) == LABEL_KIND_HIGH_TV


def test_season_without_real_value_is_not_fit_eligible() -> None:
    depth = classify_season_label_depth(
        season=2010, block=_matrix().seasons["2010"], tv_board_game_ids=()
    )
    assert depth.label_kind is None
    assert depth.fit_eligible is False
    assert "no Real value" in depth.note


def test_old_season_with_value_stays_fit_eligible_on_the_raw_rung() -> None:
    depth = classify_season_label_depth(season=2002, block=_matrix().seasons["2002"])
    assert depth.label_kind == LABEL_KIND_RAW
    assert depth.fit_eligible is True
    assert depth.boxes_with_value == 38
    assert "raw pre-boost" in depth.note


def test_contest_board_upgrades_a_season_to_the_high_tv_rung() -> None:
    depth = classify_season_label_depth(
        season=2024, block=_matrix().seasons["2024"], tv_board_game_ids=(18790,)
    )
    assert depth.label_kind == LABEL_KIND_HIGH_TV
    assert depth.tv_board_game_ids == (18790,)
    assert depth.games_with_total_value_board == 1


def test_report_classifies_every_season_with_no_year_cap() -> None:
    report = label_depth_report(_matrix(), tv_board_game_ids=(18790,))
    assert report["year_cap"] is None
    assert report["policy"] == "full_available_archive_no_year_cap"
    assert report["seasons_with_total_value_board"] == [2024]
    assert report["seasons_with_raw_score_only"] == [2002]
    assert report["seasons_without_labels"] == [2010, 2013]
    assert report["fit_eligible_seasons"] == [2002, 2024]
    assert report["min_season"] == 2002
    assert report["label_kind_counts"] == {
        LABEL_KIND_HIGH_TV: 1,
        LABEL_KIND_RAW: 1,
        NO_LABEL: 2,
    }


def test_report_spans_catalog_seasons_the_matrix_has_not_reached() -> None:
    report = label_depth_report(_matrix(), catalog_seasons=[2002, 2003, 2025])
    assert report["min_season"] == 2002
    assert report["max_season"] == 2025
    assert 2003 in report["seasons_without_labels"]
    assert 2025 in report["seasons_without_labels"]


def test_label_depth_schemaorg_is_json_ld_without_inventing_an_observation() -> None:
    document = label_depth_schemaorg(label_depth_report(_matrix()))
    assert document["@type"] == "ItemList"
    assert document["numberOfItems"] == 4
    first = document["itemListElement"][0]["item"]
    assert first["@type"] == "QuantitativeValue"
    assert first["oracle:about"]["@type"] == "SportsEvent"


# --- ingest / coverage plumbing ---------------------------------------------


def test_backfill_cell_records_only_the_raw_rung_from_corpus_g() -> None:
    cell = CoverageCell(
        season=2002,
        game_id=126323,
        day="2002-09-05",
        status="final",
        box_count=40,
        value_nonnull=38,
        player_count=90,
        play_count=150,
        paths={},
        ingested_at=datetime(2026, 9, 15, tzinfo=UTC).isoformat(),
    )
    # Corpus G box scores carry Real value but no draft-context multiplier.
    assert _label_kind_for_cell(cell) == LABEL_KIND_RAW
    empty = CoverageCell(**{**cell.__dict__, "value_nonnull": 0})
    assert _label_kind_for_cell(empty) is None


def test_season_block_summary_carries_the_label_kind_and_no_year_cap() -> None:
    block = _summarize_season_block(
        "2002", {"games": {"126323": _game(126323, boxes=40, valued=38)}}
    )
    assert block["label_kind"] == LABEL_KIND_RAW
    assert block["year_cap"] is None
    assert block["label_ladder"] == [LABEL_KIND_HIGH_TV, LABEL_KIND_RAW]

    upgraded = _season_label_kind_from_games(
        {
            "1": _game(1, boxes=10, valued=10, label_kind=LABEL_KIND_HIGH_TV),
            "2": _game(2, boxes=10, valued=10),
        }
    )
    assert upgraded == LABEL_KIND_HIGH_TV
    assert _season_label_kind_from_games({"1": _game(1, boxes=10, valued=0)}) is None


def test_coverage_rows_derive_label_kind_from_pre_189_matrices() -> None:
    rows = {row.season: row for row in _matrix().season_rows()}
    assert rows[2002].label_kind == LABEL_KIND_RAW
    assert rows[2010].label_kind is None
    assert rows[2013].label_kind is None

    declared = CoverageMatrixDocument(
        generated_at=None,
        seasons={"2024": {"status": "known", "label_kind": LABEL_KIND_HIGH_TV, "games": {}}},
        gaps=[],
    )
    assert declared.season_rows()[0].label_kind == LABEL_KIND_HIGH_TV


def test_density_and_alignment_expose_the_ladder_split() -> None:
    # Density reads the matrix alone, with no Corpus C scan, so both valued
    # seasons report the raw rung. That is the honest default.
    density = summarize_coverage_density(catalog=None, matrix=_matrix())
    assert density.seasons_with_raw_score_only == [2002, 2024]
    assert density.seasons_without_labels == [2010, 2013]
    assert density.fit_eligible_season_count == 2
    alignment = catalog_matrix_alignment(catalog_seasons={}, matrix=_matrix())
    assert alignment["label_kind_counts"][LABEL_KIND_RAW] == 2
    assert alignment["label_kind_counts"][NO_LABEL] == 2


# --- Corpus C board coverage -------------------------------------------------


def test_nfl_season_for_day_puts_january_games_in_the_prior_season() -> None:
    assert nfl_season_for_day(date(2025, 9, 7)) == 2025
    assert nfl_season_for_day(date(2026, 1, 11)) == 2025
    assert nfl_season_for_day(date(2026, 2, 8)) == 2025


def _parsed_contest(
    *,
    contest_id: int,
    day: date,
    game_id: int | None,
    boosts: tuple[float, ...],
    season: int | None = None,
) -> ParsedContest:
    """A minimal finalized contest with draft_stats and no saved entries.

    Without entries there is no counterfactual best, so the TV rung depends
    purely on whether the era exposed draft-context multipliers.
    """

    record = ContestRecord(
        contest_id=contest_id,
        sport="nfl",
        day=day,
        end_day=day,
        season=season,
        lineup_size=5,
        slot_multipliers=OBSERVED_SLOT_MULTIPLIERS,
        entrants=100,
        is_finalized=True,
        is_locked=True,
        game_id=game_id,
        captured_at=datetime(2026, 9, 15, tzinfo=UTC),
    )
    stats = tuple(
        DraftStatRow(
            contest_id=contest_id,
            player_id=index + 1,
            section="all",
            card_boost=boost,
            value=20.0 - index,
        )
        for index, boost in enumerate(boosts)
    )
    return ParsedContest(
        contest=record,
        entries=(),
        draft_stats=stats,
        missing_routes=("entries",),
        law_verified=False,
    )


def test_tv_board_coverage_only_counts_contests_that_reconstruct_a_board() -> None:
    boosted = _parsed_contest(
        contest_id=870, day=date(2024, 9, 8), game_id=18790, boosts=(0.5, 0.0)
    )
    zero_boost = _parsed_contest(
        contest_id=12, day=date(2003, 1, 4), game_id=126320, boosts=(0.0, 0.0)
    )
    coverage = tv_board_coverage_from_contests([boosted, zero_boost])
    assert coverage.seasons == (2024,)
    assert coverage.game_ids == (18790,)
    assert coverage.contest_ids == (870,)


def test_zero_boost_era_contest_stays_on_the_raw_rung_and_is_not_dropped() -> None:
    # A January 2003 contest belongs to the 2002 season and has no boosts, so
    # it never claims the TV rung, but its season still trains on raw value.
    zero_boost = _parsed_contest(
        contest_id=12, day=date(2003, 1, 4), game_id=126320, boosts=(0.0, 0.0)
    )
    assert tv_board_coverage_from_contests([zero_boost]).seasons == ()
    assert nfl_season_for_day(zero_boost.contest.day) == 2002
    report = label_depth_report(_matrix())
    assert 2002 in report["fit_eligible_seasons"]


def test_declared_contest_season_wins_over_the_day_heuristic() -> None:
    explicit = _parsed_contest(
        contest_id=99, day=date(2026, 1, 11), game_id=None, boosts=(0.4,), season=2024
    )
    assert tv_board_coverage_from_contests([explicit]).seasons == (2024,)


def test_archive_depth_report_splits_the_ladder_without_a_year_cap() -> None:
    root = Path(__file__).resolve().parents[2]
    depth = report_nfl_archive_season_depth(
        project_root=root,
        matrix=_matrix(),
        tv_board_coverage=tv_board_coverage_from_contests([]),
    )
    assert depth.year_cap is None
    assert depth.seasons_with_raw_score_only == (2002, 2024)
    assert depth.seasons_with_total_value_board == ()
    # Catalog seeds still span the full archive.
    assert min(depth.catalog_seasons) == 2002
    assert max(depth.catalog_seasons) >= 2025
    assert depth.to_dict()["label_ladder"] == [LABEL_KIND_HIGH_TV, LABEL_KIND_RAW]


def test_in_repo_label_depth_report_covers_every_cataloged_season() -> None:
    root = Path(__file__).resolve().parents[2]
    report = nfl_label_depth_report(project_root=root)
    # No coverage matrix is committed, so every cataloged season is reported
    # honestly as unlabeled rather than silently dropped.
    assert report["min_season"] == 2002
    assert report["max_season"] >= 2025
    assert report["season_count"] >= 24
    assert report["year_cap"] is None


# --- data.summary auto-applies Corpus C coverage (#192) ---------------------


def test_research_data_summary_keeps_raw_rung_without_corpus_c(tmp_path: Path) -> None:
    from nfl_oracle.data.summary import research_data_summary

    # Empty project root: no corpus_c, no matrix games beyond defaults.
    summary = research_data_summary(
        project_root=tmp_path,
        catalog_path=tmp_path / "missing_catalog.json",
        matrix_path=tmp_path / "missing_matrix.json",
        tv_board_coverage=TvBoardCoverage(),
    )
    assert summary["contest_entry"] is False
    assert summary["tv_board_coverage"] == {"seasons": [], "game_ids": [], "contest_ids": []}
    assert summary["label_depth"]["seasons_with_total_value_board"] == []


def test_research_data_summary_upgrades_raw_to_high_tv_via_coverage_arg(tmp_path: Path) -> None:
    from oracle_core.artifacts import atomic_write_json

    from nfl_oracle.data.summary import research_data_summary

    matrix = _matrix()
    mat_path = tmp_path / "coverage_matrix.json"
    atomic_write_json(
        mat_path, {"generated_at": "2026-09-15T00:00:00Z", "seasons": matrix.seasons, "gaps": []}
    )
    coverage = tv_board_coverage_from_contests(
        [_parsed_contest(contest_id=870, day=date(2024, 9, 8), game_id=18790, boosts=(0.5, 0.0))]
    )
    summary = research_data_summary(
        project_root=tmp_path,
        catalog_path=tmp_path / "missing_catalog.json",
        matrix_path=mat_path,
        tv_board_coverage=coverage,
    )
    assert 2024 in summary["label_depth"]["seasons_with_total_value_board"]
    assert summary["tv_board_coverage"]["seasons"] == [2024]
    assert summary["tv_board_coverage"]["game_ids"] == [18790]

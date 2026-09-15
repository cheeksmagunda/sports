"""High-potential label ladder and weight builders (issue #185)."""

from __future__ import annotations

from types import SimpleNamespace

from oracle_core.high_tv import (
    HighPotentialLabelKind,
    build_high_potential_labels,
    build_high_tv_board,
    game_is_fit_eligible,
    game_value_rank_weights,
    sample_weights_for_labeled_rows,
    select_label_kind,
    summarize_archive_season_depth,
)


def test_label_ladder_prefers_tv_board_then_raw_score() -> None:
    assert select_label_kind(has_total_value_board=True) is (
        HighPotentialLabelKind.HIGH_TOTAL_VALUE_BOARD
    )
    assert select_label_kind(has_total_value_board=False) is (
        HighPotentialLabelKind.RAW_HIGHEST_SCORE
    )


def test_raw_score_season_remains_fit_eligible_without_tv_board() -> None:
    values = {1: 9.0, 2: 1.0}
    assert game_is_fit_eligible(values)
    labels = build_high_potential_labels(values, slate_id=10, has_total_value_board=False, top_k=1)
    assert len(labels) == 1
    assert labels[0].player_id == 1
    assert labels[0].kind is HighPotentialLabelKind.RAW_HIGHEST_SCORE


def test_high_tv_board_records_ladder_kind() -> None:
    board = build_high_tv_board(
        contest_id=7,
        values={3: 5.0, 8: 12.0},
        has_total_value_board=False,
    )
    assert board is not None
    assert board.top_value_player_ids[0] == 8
    assert board.label_kind is HighPotentialLabelKind.RAW_HIGHEST_SCORE


def test_low_frequency_high_value_outranks_high_frequency_chalk_weights() -> None:
    """Top-k value rank up-weights the sleeper, not appearance volume."""

    game_values = {
        101: 16.6,  # sleeper, one observation represented as this game's value
        202: 4.0,  # chalk
        203: 3.5,
        204: 3.0,
        205: 2.5,
        206: 2.0,
    }
    weights = game_value_rank_weights(game_values, top_k=1, high_weight=4.0, base_weight=1.0)
    assert weights[101] == 4.0
    assert weights[202] == 1.0


def test_sample_weights_align_with_rows_and_ignore_dnp() -> None:
    rows = [
        SimpleNamespace(player_id=1, game_id=9, value=10.0, did_not_play=False),
        SimpleNamespace(player_id=2, game_id=9, value=1.0, did_not_play=False),
        SimpleNamespace(player_id=3, game_id=9, value=0.0, did_not_play=True),
    ]
    weights = sample_weights_for_labeled_rows(rows, top_k=1, high_weight=5.0)
    assert weights == [5.0, 1.0, 1.0]


def test_archive_depth_has_no_year_cap_and_tracks_ladder_coverage() -> None:
    depth = summarize_archive_season_depth(
        catalog_seasons={2002: 2, 2024: 4, 2025: 5},
        on_disk_seasons={2024: 4, 2025: 5},
        fit_seasons={2024: 4, 2025: 5},
        seasons_with_total_value_board=[2025],
        seasons_with_raw_score_only=[2024, 2002],
    )
    assert depth.year_cap is None
    assert depth.catalog_seasons[0] == 2002
    payload = depth.to_dict()
    assert payload["policy"] == "full_available_archive_no_year_cap"
    assert payload["label_ladder"][0] == "high_total_value_board"
    assert payload["label_ladder"][1] == "raw_highest_score_pre_boost"


def test_high_tv_board_schemaorg_uses_item_list_and_person() -> None:
    board = build_high_tv_board(
        contest_id=42,
        values={7: 11.0, 3: 9.0},
        has_total_value_board=True,
    )
    assert board is not None
    doc = board.to_schemaorg()
    assert doc["@context"]["@vocab"] == "https://schema.org/"
    assert doc["@type"] == "ItemList"
    assert doc["itemListElement"][0]["item"]["@type"] == "Person"
    assert doc["itemListElement"][0]["item"]["identifier"] == "7"
    assert doc["oracle:labelKind"] == "high_total_value_board"


def test_high_potential_label_schemaorg_uses_quantitative_value() -> None:
    labels = build_high_potential_labels(
        {5: 16.6}, slate_id=99, has_total_value_board=False, top_k=1
    )
    doc = labels[0].to_schemaorg()
    assert doc["@type"] == "Person"
    assert doc["oracle:score"]["@type"] == "QuantitativeValue"
    assert doc["oracle:score"]["value"] == 16.6
    assert doc["oracle:about"]["@type"] == "SportsEvent"

"""HV/TDV leaderboard rows are the only train labels. Box rows are excluded."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from nfl_oracle.recommendations import hv_labels
from nfl_oracle.recommendations.high_tv import sample_weights_for_train_target
from nfl_oracle.recommendations.hv_labels import apply_hv_tdv_labels
from nfl_oracle.recommendations.model import HistoricalPerformance

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "corpus_c_hv"


def _row(*, player_id: int, game_id: int, value: float) -> HistoricalPerformance:
    kickoff = datetime(2025, 9, 15, 17, tzinfo=UTC)
    available = kickoff + timedelta(hours=4)
    return HistoricalPerformance(
        player_id=player_id,
        game_id=game_id,
        position="WR",
        kickoff_at=kickoff,
        available_at=available,
        captured_at=available,
        value=value,
    )


def test_corpus_c_hv_section_overlays_scoped_game_only() -> None:
    rows = [
        _row(player_id=401, game_id=19457, value=1.0),
        _row(player_id=401, game_id=99999, value=9.0),
        _row(player_id=501, game_id=19457, value=3.2),
        _row(player_id=999, game_id=19457, value=2.0),
    ]
    updated, audit = apply_hv_tdv_labels(
        Path("nfl-oracle"),
        rows,
        corpus_c_root=FIXTURES,
        export_root=Path("/tmp/nfl-hv-export-absent"),
        hv_corpus_root=Path("/tmp/nfl-hv-corpus-absent"),
    )
    assert len(updated) == 1
    # Fixture HV value is 5.0. Draft count 20 must not become the label.
    assert updated[0].player_id == 401
    assert updated[0].game_id == 19457
    assert updated[0].value == 5.0
    assert updated[0].label_kind == "hv_tdv_leaderboard"
    assert audit.rows_overlaid == 1
    assert audit.rows_raw == 0
    assert audit.rows_excluded == 3
    assert audit.boards >= 1
    assert audit.operator_lock == "hv_tdv_only"
    assert audit.raw_box_used_as_target is False
    assert audit.fit_seasons == (2025,)
    audit_doc = audit.to_dict()
    assert audit_doc["draft_count_is_label"] is False
    assert audit_doc["winning_drafts_are_label"] is False
    assert audit_doc["winning_drafts_are_reference_bar"] is True
    assert audit_doc["cash_is_objective"] is False
    assert audit_doc["median_is_objective"] is False
    assert audit_doc["lineup_size"] == 5
    assert audit_doc["objective"] == (
        "5-player lineup maximizing capture of highestBoostedValuePlayers"
    )
    assert audit_doc["training_target"] == "hv_tdv_leaderboards"
    assert audit_doc["label_section"] == "highestBoostedValuePlayers"
    assert audit_doc["ladder"] == "oracle_core.high_tv.select_label_kind"


def test_missing_hv_section_is_excluded_even_with_boosts(tmp_path: Path) -> None:
    only_9002 = tmp_path / "corpus_c"
    only_9002.mkdir()
    source = FIXTURES / "9002"
    target = only_9002 / "9002"
    target.mkdir()
    for name in ("meta.json", "stats.json", "draftinfo.json", "payoutinfo.json", "entries.json"):
        (target / name).write_text((source / name).read_text(encoding="utf-8"), encoding="utf-8")
    rows = [_row(player_id=401, game_id=19457, value=1.25)]
    updated, audit = apply_hv_tdv_labels(
        Path("nfl-oracle"),
        rows,
        corpus_c_root=only_9002,
        export_root=tmp_path / "export",
        hv_corpus_root=tmp_path / "hv",
    )
    assert updated == []
    assert audit.rows_overlaid == 0
    assert audit.rows_raw == 0
    assert audit.rows_excluded == 1
    assert audit.boards == 0
    assert audit.raw_box_used_as_target is False
    assert audit.operator_lock == "hv_tdv_only"


def test_exported_hv_board_overlays_and_reconstruction_does_not(tmp_path: Path) -> None:
    export = tmp_path / "export" / "nfl" / "2025" / "2025-09-15" / "contest_42"
    export.mkdir(parents=True)
    (export / "total_value_leaderboard.json").write_text(
        json.dumps(
            {
                "section": "highestBoostedValuePlayers",
                "source": "draft_stats.highestBoostedValuePlayers",
                "players": [{"player_id": 7, "value": 8.5, "drafts": 400}],
            }
        ),
        encoding="utf-8",
    )
    (export / "matchups.json").write_text(
        json.dumps({"game_ids": [55], "contest_game_id": 55}),
        encoding="utf-8",
    )
    recon = tmp_path / "export" / "nfl" / "2025" / "2025-09-15" / "contest_43"
    recon.mkdir()
    (recon / "total_value_leaderboard.json").write_text(
        json.dumps(
            {
                "section": "highestBoostedValuePlayers",
                "source": "nfl_draft_stats_reconstructed",
                "players": [{"player_id": 8, "value": 99.0, "drafts": 1}],
            }
        ),
        encoding="utf-8",
    )
    (recon / "matchups.json").write_text(json.dumps({"game_ids": [55]}), encoding="utf-8")
    rows = [
        _row(player_id=7, game_id=55, value=1.0),
        _row(player_id=8, game_id=55, value=2.0),
    ]
    updated, audit = apply_hv_tdv_labels(
        Path("nfl-oracle"),
        rows,
        corpus_c_root=tmp_path / "empty_c",
        export_root=tmp_path / "export",
        hv_corpus_root=tmp_path / "empty_hv",
    )
    assert [(row.player_id, row.value, row.label_kind) for row in updated] == [
        (7, 8.5, "hv_tdv_leaderboard")
    ]
    assert audit.rows_overlaid == 1
    assert audit.rows_excluded == 1
    assert audit.rows_raw == 0
    assert audit.boards == 1


def test_conflicting_hv_values_are_excluded(tmp_path: Path) -> None:
    corpus = tmp_path / "hv"
    for contest, value in (("a", 4.0), ("b", 6.0)):
        directory = corpus / "nfl" / "2025" / contest
        directory.mkdir(parents=True)
        (directory / "hv_board.json").write_text(
            json.dumps(
                {
                    "section": "highestBoostedValuePlayers",
                    "source": "realsports.draftStats.highestBoostedValuePlayers",
                    "game_id": 77,
                    "players": [{"player_id": 3, "value": value, "drafts": 10}],
                }
            ),
            encoding="utf-8",
        )
    rows = [_row(player_id=3, game_id=77, value=1.5)]
    updated, audit = apply_hv_tdv_labels(
        Path("nfl-oracle"),
        rows,
        corpus_c_root=tmp_path / "c",
        export_root=tmp_path / "e",
        hv_corpus_root=corpus,
    )
    assert updated == []
    assert audit.rows_overlaid == 0
    assert audit.rows_excluded == 1
    assert audit.rows_raw == 0
    assert audit.conflicts == 1
    assert audit.raw_box_used_as_target is False


def test_leaderboard_weight_beats_a_larger_raw_box_in_the_same_game() -> None:
    board = _row(player_id=1, game_id=10, value=5.0).model_copy(
        update={"label_kind": "hv_tdv_leaderboard"}
    )
    raw = _row(player_id=2, game_id=10, value=80.0)
    weights = sample_weights_for_train_target([board, raw], top_k=1, high_weight=4.0)
    assert weights == [4.0, 1.0]


def test_corpus_c_train_calls_the_185_ladder(monkeypatch) -> None:
    calls = {"board": 0, "kind": 0, "labels": 0}
    real_board = hv_labels.high_tv_board_from_draft_stats
    real_kind = hv_labels.select_label_kind
    real_labels = hv_labels.build_high_potential_labels

    def board(parsed, **kwargs):
        calls["board"] += 1
        return real_board(parsed, **kwargs)

    def kind(**kwargs):
        calls["kind"] += 1
        return real_kind(**kwargs)

    def labels(*args, **kwargs):
        calls["labels"] += 1
        assert kwargs.get("has_total_value_board") is True
        return real_labels(*args, **kwargs)

    monkeypatch.setattr(hv_labels, "high_tv_board_from_draft_stats", board)
    monkeypatch.setattr(hv_labels, "select_label_kind", kind)
    monkeypatch.setattr(hv_labels, "build_high_potential_labels", labels)
    updated, _audit = apply_hv_tdv_labels(
        Path("nfl-oracle"),
        [_row(player_id=401, game_id=19457, value=1.0)],
        corpus_c_root=FIXTURES,
        export_root=Path("/tmp/nfl-hv-export-absent"),
        hv_corpus_root=Path("/tmp/nfl-hv-corpus-absent"),
    )
    assert calls["board"] >= 1
    assert calls["kind"] >= 1
    assert calls["labels"] >= 1
    assert updated[0].label_kind == "hv_tdv_leaderboard"
    assert updated[0].value == 5.0


def test_games_without_a_leaderboard_still_upweight_raw_top_value() -> None:
    low = _row(player_id=1, game_id=11, value=1.0)
    high = _row(player_id=2, game_id=11, value=9.0)
    weights = sample_weights_for_train_target([low, high], top_k=1, high_weight=4.0)
    assert weights == [1.0, 4.0]

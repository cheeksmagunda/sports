"""HV/TDV board values replace box labels only when the HV section scopes the game."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
    by_key = {(row.player_id, row.game_id): row.value for row in updated}
    # Fixture HV value is 5.0. Draft count 20 must not become the label.
    assert by_key[(401, 19457)] == 5.0
    assert by_key[(401, 99999)] == 9.0
    # mostDraftedPlayers is not the train target.
    assert by_key[(501, 19457)] == 3.2
    assert by_key[(999, 19457)] == 2.0
    assert audit.rows_overlaid == 1
    assert audit.rows_raw == 3
    assert audit.boards >= 1
    assert audit.to_dict()["draft_count_is_label"] is False


def test_missing_hv_section_keeps_raw_box_value(tmp_path: Path) -> None:
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
    assert updated[0].value == 1.25
    assert audit.rows_overlaid == 0
    assert audit.boards == 0


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
    by_player = {row.player_id: row.value for row in updated}
    assert by_player[7] == 8.5
    assert by_player[8] == 2.0
    assert audit.rows_overlaid == 1
    assert audit.boards == 1


def test_conflicting_hv_values_leave_the_raw_box(tmp_path: Path) -> None:
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
    assert updated[0].value == 1.5
    assert audit.rows_overlaid == 0
    assert audit.conflicts == 1

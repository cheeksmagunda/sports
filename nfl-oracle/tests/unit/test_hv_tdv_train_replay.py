"""HV/TDV train labels and draft-image replay (#597)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from nfl_oracle.recommendations.cli import _parser
from nfl_oracle.recommendations.hv_boards import (
    HvBoard,
    HvBoardPlayer,
    apply_hv_board_labels,
    boards_from_contest_root,
    is_hv_board_document,
)
from nfl_oracle.recommendations.model import HistoricalPerformance, fit_model
from nfl_oracle.replay.hv_board_replay import (
    card_score,
    hindsight_best,
    replay_board,
    replay_roots,
    replay_synthetic,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "corpus_c_hv"
SLOTS = (2.0, 1.8, 1.6, 1.4, 1.2)


def _row(*, player_id: int, game_id: int, value: float, kickoff: datetime) -> HistoricalPerformance:
    available = kickoff + timedelta(hours=2)
    return HistoricalPerformance(
        player_id=player_id,
        game_id=game_id,
        position="WR",
        kickoff_at=kickoff,
        available_at=available,
        captured_at=available + timedelta(hours=1),
        value=value,
    )


def test_draft_image_card_is_realized_times_slot_plus_boost() -> None:
    assert card_score(5.0, 2.0, 0.0) == 10.0
    assert card_score(4.0, 1.2, 3.0) == 16.8


def test_overlay_prefers_hv_section_and_ignores_most_drafted() -> None:
    boards, seen = boards_from_contest_root(FIXTURE)
    assert seen == 2
    assert len(boards) == 1
    assert boards[0].contest_id == 9001
    assert boards[0].game_id == 19457
    kickoff = datetime(2025, 9, 15, 17, tzinfo=UTC)
    rows = [
        _row(player_id=401, game_id=19457, value=1.0, kickoff=kickoff),
        _row(player_id=501, game_id=19457, value=9.0, kickoff=kickoff),
        _row(player_id=999, game_id=19457, value=3.0, kickoff=kickoff),
    ]
    updated, audit = apply_hv_board_labels(rows, boards)
    by_player = {row.player_id: row.value for row in updated}
    assert by_player[401] == 5.0
    assert by_player[501] == 9.0
    assert by_player[999] == 3.0
    assert audit.hv_board_rows_relabeled == 1
    assert audit.raw_box_rows == 2
    assert audit.win_frequency_target_rows == 0
    labeled = next(player for player in boards[0].players if player.player_id == 401)
    assert labeled.drafts == 20
    assert labeled.realized_value == 5.0


def test_reconstructed_export_is_not_an_hv_board() -> None:
    assert (
        is_hv_board_document(
            {"source": "nfl_draft_stats_reconstructed", "section": "highestBoostedValuePlayers"}
        )
        is False
    )
    assert is_hv_board_document(
        {
            "source": "realsports.draftStats.highestBoostedValuePlayers",
            "label": "total_value_leaderboard",
            "section": "highestBoostedValuePlayers",
        }
    )


def test_date_join_when_board_has_no_game_id() -> None:
    board = HvBoard(
        players=(HvBoardPlayer(player_id=7, realized_value=12.5, card_boost=0.5, drafts=2),),
        source="corpus_c.highestBoostedValuePlayers",
        slate_date=datetime(2025, 9, 21, tzinfo=UTC).date(),
    )
    kickoff = datetime(2025, 9, 21, 17, tzinfo=UTC)
    rows = [_row(player_id=7, game_id=42, value=1.0, kickoff=kickoff)]
    updated, audit = apply_hv_board_labels(rows, (board,))
    assert updated[0].value == 12.5
    assert audit.hv_board_rows == 1


def test_hindsight_keeps_high_boost_over_a_slightly_higher_raw_value() -> None:
    players = (
        HvBoardPlayer(player_id=10, realized_value=6.0, card_boost=0.0, drafts=1),
        HvBoardPlayer(player_id=11, realized_value=5.0, card_boost=0.0, drafts=2),
        HvBoardPlayer(player_id=12, realized_value=4.0, card_boost=0.0, drafts=3),
        HvBoardPlayer(player_id=13, realized_value=3.0, card_boost=0.0, drafts=4),
        HvBoardPlayer(player_id=14, realized_value=2.0, card_boost=0.0, drafts=5),
        HvBoardPlayer(player_id=15, realized_value=1.9, card_boost=3.0, drafts=100),
        HvBoardPlayer(player_id=16, realized_value=0.5, card_boost=0.0, drafts=200),
        HvBoardPlayer(player_id=17, realized_value=0.5, card_boost=0.0, drafts=190),
        HvBoardPlayer(player_id=18, realized_value=0.5, card_boost=0.0, drafts=180),
        HvBoardPlayer(player_id=19, realized_value=0.5, card_boost=0.0, drafts=170),
    )
    ceiling = hindsight_best(players, SLOTS)
    assert ceiling is not None
    assert ceiling.total == 39.58
    assert 15 in ceiling.player_ids
    assert 14 not in ceiling.player_ids
    board = HvBoard(players=players, source="corpus_c.highestBoostedValuePlayers", contest_id=1)
    scored = replay_board(board, slots=SLOTS)
    assert scored is not None
    assert scored.hv_rank_total == 34.0
    assert scored.hindsight_total == 39.58
    assert scored.hv_rank_capture is not None
    assert scored.chalk_capture is not None
    assert scored.hv_rank_total > scored.chalk_total
    assert scored.hv_cards[0].slot_multiplier == 2.0
    assert scored.hv_cards[0].realized_value == 6.0
    assert scored.hv_cards[0].card_score == 12.0


def test_fixture_replay_scores_hv_board_and_skips_missing_section() -> None:
    results, summary = replay_roots(contest_root=FIXTURE, export_root=Path("/tmp/nfl-hv-missing"))
    assert summary.n_scored == 1
    assert summary.excluded.get("missing_hv_section") == 1
    assert results[0].contest_id == 9001
    assert results[0].slot_multipliers == SLOTS
    assert results[0].hv_beats_chalk is None
    assert results[0].hv_rank_capture is not None
    assert 0 < results[0].hv_rank_capture <= 1.0
    for card in results[0].hv_cards:
        expected = card_score(card.realized_value, card.slot_multiplier, card.card_boost)
        assert abs(card.card_score - expected) < 1e-6


def test_synthetic_depth_prefers_hv_rank_over_chalk() -> None:
    _rows, summary = replay_synthetic(64, seed=597)
    assert summary.n_scored == 64
    assert summary.n_hv_beats_chalk > summary.n_chalk_beats_hv
    assert summary.mean_hv_rank_capture is not None
    assert summary.mean_chalk_capture is not None
    assert summary.mean_hv_rank_capture > summary.mean_chalk_capture


def test_fit_records_hv_audit_and_never_counts_win_frequency_targets() -> None:
    start = datetime(2024, 9, 1, 17, tzinfo=UTC)
    rows: list[HistoricalPerformance] = []
    for week in range(12):
        kickoff = start + timedelta(days=7 * week)
        for player_id, base in ((1, 3.5), (2, 1.0), (3, 1.2), (4, 0.8)):
            rows.append(
                _row(
                    player_id=player_id,
                    game_id=1000 + week,
                    value=base,
                    kickoff=kickoff,
                )
            )
    model = fit_model(
        rows,
        trained_at=start + timedelta(days=90),
        hv_label_audit={
            "boards_seen": 2,
            "hv_board_rows": 3,
            "hv_board_rows_relabeled": 3,
            "raw_box_rows": 45,
            "win_frequency_target_rows": 99,
        },
    )
    assert model.evaluation["hv_label_policy"] == "prefer_hv_tdv_board_when_present_else_raw_box"
    assert model.evaluation["hv_boards_seen"] == 2
    assert model.evaluation["hv_board_rows_relabeled"] == 3
    assert model.evaluation["hv_win_frequency_target_rows"] == 0
    assert model.evaluation["training_target"] == "high_total_value_full_archive_not_win_chalk"


def test_train_parser_accepts_dry_run() -> None:
    args = _parser().parse_args(["train", "--dry-run"])
    assert args.dry_run is True
    assert args.force is False

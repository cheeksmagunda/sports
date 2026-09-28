"""HV/TDV train labels and draft-image replay (#597)."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from nfl_oracle.recommendations.cli import _parser
from nfl_oracle.recommendations.hv_boards import (
    HV_TDV_LABEL_POLICY,
    HV_TDV_TRAINING_TARGET,
    HvBoard,
    HvBoardPlayer,
    apply_hv_board_labels,
    boards_from_contest_root,
    is_hv_board_document,
    load_and_apply_hv_labels,
    require_hv_tdv_leaderboard_rows,
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
    assert set(by_player) == {401}
    assert by_player[401] == 5.0
    assert audit.hv_board_rows_relabeled == 1
    assert audit.raw_box_rows == 2
    assert audit.win_frequency_target_rows == 0
    labeled = next(player for player in boards[0].players if player.player_id == 401)
    assert labeled.drafts == 20
    assert labeled.realized_value == 5.0
    joined = next(row for row in updated if row.player_id == 401)
    # Slot 1, boost 0: Value column is 5.0 * 2.0. Ridge y stays 5.0.
    assert joined.value == 5.0
    assert joined.value_column == 10.0
    assert "value_column" not in joined.model_dump()
    assert audit.value_column_rows == 1


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
    # Value-column rank keeps the +3.0 card (player 15) that raw realized drops.
    assert scored.hv_rank_total == 39.58
    assert 15 in scored.hv_rank_player_ids
    assert 14 not in scored.hv_rank_player_ids
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
    assert results[0].hv_beats_chalk is True
    assert 406 in results[0].hv_rank_player_ids
    assert 401 not in results[0].hv_rank_player_ids
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
    assert model.evaluation["hv_label_policy"] == HV_TDV_LABEL_POLICY
    assert model.evaluation["hv_boards_seen"] == 2
    assert model.evaluation["hv_board_rows_relabeled"] == 3
    assert model.evaluation["hv_excluded_non_leaderboard_rows"] == 45
    assert model.evaluation["hv_win_frequency_target_rows"] == 0
    assert model.evaluation["training_target"] == HV_TDV_TRAINING_TARGET


def test_missing_leaderboard_is_not_a_raw_box_or_chalk_target(tmp_path: Path) -> None:
    saved = {
        key: os.environ.pop(key, None)
        for key in ("NFL_CORPUS_C_ROOT", "NFL_HV_EXPORT_ROOT", "NFL_HV_BOARD_ROOT")
    }
    kickoff = datetime(2025, 9, 28, 17, tzinfo=UTC)
    rows = [_row(player_id=1, game_id=1, value=9.0, kickoff=kickoff)]
    try:
        labeled, audit = load_and_apply_hv_labels(rows, tmp_path)
    finally:
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value
    assert labeled == []
    assert audit.hv_board_rows == 0
    assert audit.win_frequency_target_rows == 0
    try:
        require_hv_tdv_leaderboard_rows(labeled, audit)
    except ValueError as error:
        assert str(error) == "hv_tdv_leaderboard_target_required"
    else:
        raise AssertionError("expected leaderboard target refusal")


def test_train_parser_accepts_dry_run() -> None:
    args = _parser().parse_args(["train", "--dry-run"])
    assert args.dry_run is True
    assert args.force is False


SCREENSHOTS = Path(__file__).resolve().parents[1] / "fixtures" / "hv_screenshots"


def test_boswell_value_column_beats_gibbs_formula() -> None:
    from nfl_oracle.recommendations.hv_boards import player_value_column

    boswell = HvBoardPlayer(
        player_id=91001,
        name="Chris Boswell",
        realized_value=5.8,
        card_boost=3.0,
        drafts=24,
        most_common_slot=1,
        displayed_value=29.0,
    )
    gibbs_formula = HvBoardPlayer(
        player_id=91012,
        name="Jahmyr Gibbs",
        realized_value=9.4,
        card_boost=0.0,
        drafts=1700,
        most_common_slot=1,
    )
    assert player_value_column(boswell) == 29.0
    assert (
        player_value_column(
            HvBoardPlayer(player_id=91001, realized_value=5.8, card_boost=3.0, most_common_slot=1)
        )
        == 29.0
    )
    assert abs(player_value_column(gibbs_formula) - 18.8) < 1e-9
    aja = HvBoardPlayer(player_id=94001, realized_value=9.6, card_boost=0.0, most_common_slot=1)
    assert player_value_column(aja) == 19.2


def test_sample_weights_follow_value_column_not_realized() -> None:
    from nfl_oracle.recommendations.high_tv import sample_weights_for_history

    kickoff = datetime(2025, 9, 28, 17, tzinfo=UTC)
    # Boswell column 29, five cards at column 20, Gibbs column 18.8 with the
    # highest realized number. Top-5 by the column excludes Gibbs.
    specs = [(1, 5.8, 29.0), (7, 9.4, 18.8)]
    specs[1:1] = [(pid, 4.0, 20.0) for pid in range(2, 7)]
    rows = [
        _row(player_id=pid, game_id=77, value=realized, kickoff=kickoff).model_copy(
            update={"value_column": column}
        )
        for pid, realized, column in specs
    ]
    weights = {
        row.player_id: weight
        for row, weight in zip(rows, sample_weights_for_history(rows), strict=True)
    }
    assert weights[1] == 4.0
    assert weights[5] == 4.0
    assert weights[7] == 1.0
    raw_rows = [row.model_copy(update={"value_column": None}) for row in rows]
    raw = {
        row.player_id: weight
        for row, weight in zip(raw_rows, sample_weights_for_history(raw_rows), strict=True)
    }
    assert raw[7] == 4.0
    assert raw[5] == 1.0


def test_screenshot_boards_prefer_value_column_and_keep_correct_chalk() -> None:
    results, summary = replay_roots(
        contest_root=Path("/tmp/nfl-hv-screenshots-no-corpus"),
        export_root=SCREENSHOTS,
    )
    assert summary.n_scored == 4
    by_key = {row.path.rsplit("/", 2)[-2]: row for row in results}
    boswell = by_key["nfl_boswell"]
    assert 91001 in boswell.hv_rank_player_ids
    assert 91012 not in boswell.hv_rank_player_ids
    assert 91012 in boswell.chalk_player_ids
    assert boswell.hv_beats_chalk is True
    london = by_key["nfl_tnf_gb_atl"]
    assert 92001 in london.hv_rank_player_ids
    assert 92001 in london.chalk_player_ids
    assert london.hv_beats_chalk is True
    aubrey = by_key["nfl_aubrey"]
    assert 93001 in aubrey.hv_rank_player_ids
    assert 93008 not in aubrey.hv_rank_player_ids
    assert 93008 in aubrey.chalk_player_ids
    aja = by_key["wnba_aja"]
    assert aja.hv_rank_player_ids[0] == 94001
    assert 94001 in aja.chalk_player_ids
    assert aja.hv_beats_chalk is True


def test_hv_t40_knobs_drop_gibbs_and_keep_expected_value() -> None:
    from nfl_oracle.recommendations.hv_boards import HV_T40_KNOBS
    from nfl_oracle.recommendations.model import Projection
    from nfl_oracle.recommendations.optimizer import (
        ScoringPolicy,
        optimize,
        optimizer_config_from_env,
    )
    from nfl_oracle.recommendations.picker_knobs import picker_knobs_from_env
    from nfl_oracle.recommendations.schema import Candidate, Contest, EvidenceClock, Game, Slate

    cfg = optimizer_config_from_env(HV_T40_KNOBS)
    assert cfg.profile == "max_value"
    assert cfg.min_distinct_teams == 1
    assert cfg.min_distinct_games == 1
    assert cfg.upside_weight == 0.0
    assert cfg.field_weight == 0.0
    picker = picker_knobs_from_env(HV_T40_KNOBS)
    assert picker.boost_rank_blend == 0.0
    assert picker.position_calibration == 0.0
    assert picker.profile == "identity"
    empty = optimizer_config_from_env({})
    assert empty.upside_weight == 0.0
    assert empty.field_weight == 0.0

    decision = datetime(2026, 9, 28, 18, tzinfo=UTC)
    clock = EvidenceClock(source_available_at=decision, captured_at=decision)
    cards = (
        (101, "Chris Boswell", 5.8, 3.0),
        (102, "Sam Darnold", 5.4, 3.0),
        (103, "Will Anderson Jr.", 7.6, 1.4),
        (104, "Harold Fannin Jr.", 4.6, 3.0),
        (105, "Genesis Smith", 5.4, 3.0),
        (106, "Jahmyr Gibbs", 9.4, 0.0),
    )
    candidates = tuple(
        Candidate(
            player_id=pid,
            game_id=501,
            team_id=10,
            name=name,
            position="K" if pid in {101, 104} else "WR",
            team="PIT",
            opponent="NYJ",
            injury_status="Active",
            card_boost=boost,
            clock=clock,
        )
        for pid, name, _mean, boost in cards
    )
    target = Slate(
        contest=Contest(
            contest_id=597,
            day=decision.date(),
            end_day=decision.date(),
            slot_multipliers=SLOTS,
            is_locked=False,
            is_finalized=False,
            clock=clock,
            evidence_sha256="c" * 64,
        ),
        games=(
            Game(
                game_id=501,
                season=2026,
                kickoff_at=decision + timedelta(hours=4),
                home_team_id=10,
                away_team_id=11,
                home_team="PIT",
                away_team="NYJ",
                status="scheduled",
            ),
        ),
        candidates=candidates,
        captured_at=decision,
        source_hashes=("d" * 64,),
        pool_roster_count=len(candidates),
        pool_search_matched_count=len(candidates),
    )
    projections = tuple(
        Projection(
            player_id=pid,
            mean=mean,
            conditional_mean=mean,
            stddev=0.1,
            availability_probability=1,
            prior_games=4,
            samples=(mean, mean),
            provenance=("screenshot_realized",),
        )
        for pid, _name, mean, _boost in cards
    )
    recommendation = optimize(
        target,
        projections,
        decision_at=decision,
        scoring_policy=ScoringPolicy(),
        config=cfg,
    )
    picked = {pick.player_id for pick in recommendation.picks}
    assert 101 in picked
    assert 106 not in picked
    assert recommendation.construction_profile == "max_value"

"""Contest-display weights and the offline HV/chalk/ceiling map."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from nfl_oracle.recommendations.display_rank_weights import (
    DISPLAY_TOP_K,
    RAW_TOP_K,
    boosts_for_history_rows,
    contest_display_top_ids,
    display_top_k_from_env,
    sample_weights_contest_display,
)
from nfl_oracle.replay.contest_max_map_cli import build_report, collect_boards


def test_missing_boost_map_keeps_raw_value_top_k() -> None:
    rows = [
        SimpleNamespace(player_id=1, game_id=9, value=9.0, did_not_play=False),
        SimpleNamespace(player_id=2, game_id=9, value=3.4, did_not_play=False),
    ]
    assert sample_weights_contest_display(rows, boosts=None, top_k=1, high_weight=4.0) == [
        4.0,
        1.0,
    ]


def test_boost_map_promotes_the_contest_display_player() -> None:
    rows = [
        SimpleNamespace(player_id=1, game_id=9, value=5.0, did_not_play=False),
        SimpleNamespace(player_id=2, game_id=9, value=3.4, did_not_play=False),
    ]
    weights = sample_weights_contest_display(
        rows, boosts={(2, 9): 3.0, (1, 9): 0.0}, top_k=1, high_weight=4.0
    )
    assert weights == [1.0, 4.0]


def test_default_display_window_is_top_10_of_the_slate_not_each_game() -> None:
    """Eight players per game would all be top-10 inside the game. The slate is one board."""

    kickoff = datetime(2024, 9, 8, 17, 0, tzinfo=UTC)
    rows = []
    boosts = {}
    for game_id, start in ((9, 30), (10, 22)):
        for offset in range(8):
            player_id = start - offset
            rows.append(
                SimpleNamespace(
                    player_id=player_id,
                    game_id=game_id,
                    value=float(player_id),
                    did_not_play=False,
                    kickoff_at=kickoff,
                    draft_count=10_000 - player_id,
                )
            )
            boosts[(player_id, game_id)] = 0.0
    weights = sample_weights_contest_display(rows, boosts=boosts, high_weight=4.0)
    assert weights.count(4.0) == DISPLAY_TOP_K
    assert weights.count(1.0) == len(rows) - DISPLAY_TOP_K
    # Highest raw values are also the display order when every boost is 0.
    high = {row.player_id for row, weight in zip(rows, weights, strict=True) if weight == 4.0}
    assert high == set(range(21, 31))
    # Highest draft_count is the lowest player id. It is not in the window.
    chalkiest = min(rows, key=lambda row: row.player_id)
    assert chalkiest.player_id not in high


def test_full_hv_board_stays_in_sample_outside_the_display_top_10() -> None:
    """Draft-count leaders remain rows. Only the display window takes the high weight."""

    kickoff = datetime(2024, 9, 8, 17, 0, tzinfo=UTC)
    rows = []
    boosts = {}
    for player_id in range(1, 13):
        rows.append(
            SimpleNamespace(
                player_id=player_id,
                game_id=9,
                value=5.0 if player_id <= 10 else 8.0,
                did_not_play=False,
                kickoff_at=kickoff,
                draft_count=1 if player_id <= 10 else 1000 - player_id,
            )
        )
        boosts[(player_id, 9)] = 3.0 if player_id <= 10 else 0.0
    weights = sample_weights_contest_display(rows, boosts=boosts, high_weight=4.0)
    assert len(weights) == len(rows)
    assert weights.count(4.0) == DISPLAY_TOP_K
    assert weights[-2:] == [1.0, 1.0]


def test_missing_boost_map_keeps_raw_top_five() -> None:
    rows = [
        SimpleNamespace(player_id=pid, game_id=9, value=float(pid), did_not_play=False)
        for pid in range(1, 8)
    ]
    weights = sample_weights_contest_display(rows, boosts=None, high_weight=4.0)
    assert weights.count(4.0) == RAW_TOP_K
    assert display_top_k_from_env({}) == DISPLAY_TOP_K
    assert display_top_k_from_env({"NFL_TRAIN_DISPLAY_TOP_K": "12"}) == 12
    try:
        display_top_k_from_env({"NFL_TRAIN_DISPLAY_TOP_K": "nope"})
    except ValueError as exc:
        assert str(exc) == "nfl_train_display_top_k_invalid"
    else:
        raise AssertionError("invalid display top-k must fail closed")


def test_history_join_uses_eastern_kickoff_date() -> None:
    # 2026-09-28 02:30 UTC is still 2026-09-27 in New York.
    row = SimpleNamespace(
        player_id=7,
        game_id=11,
        kickoff_at=datetime(2026, 9, 28, 2, 30, tzinfo=UTC),
    )
    matched = boosts_for_history_rows([row], {("2026-09-27", 7): 1.5, ("2026-09-28", 7): 3.0})
    assert matched[(7, 11)] == 1.5


def test_serve_display_top_uses_projected_base_times_boost_not_drafts() -> None:
    projections = [
        SimpleNamespace(player_id=1, conditional_mean=5.0, mean=5.0),
        SimpleNamespace(player_id=2, conditional_mean=3.4, mean=3.4),
    ]
    candidates = [
        SimpleNamespace(player_id=1, card_boost=0.0),
        SimpleNamespace(player_id=2, card_boost=3.0),
    ]
    assert contest_display_top_ids(projections, candidates, n=1) == (2,)


def test_csv_map_summary_marks_draft_count_as_not_a_label(tmp_path) -> None:
    csv_path = tmp_path / "labels.csv"
    csv_path.write_text(
        "contest_id,slate_date,section,platform_player_id,display_name,team_key,"
        "card_boost,drafts,real_score,ingested_at\n"
        "1,2026-09-24,highestBoostedValuePlayers,1,A,AAA,0.0,9000,9.0,2026-09-25\n"
        "1,2026-09-24,highestBoostedValuePlayers,2,B,BBB,3.0,10,3.4,2026-09-25\n"
        "1,2026-09-24,highestBoostedValuePlayers,3,C,CCC,3.0,9,3.3,2026-09-25\n"
        "1,2026-09-24,highestBoostedValuePlayers,4,D,DDD,3.0,8,3.2,2026-09-25\n"
        "1,2026-09-24,highestBoostedValuePlayers,5,E,EEE,3.0,7,3.1,2026-09-25\n"
        "1,2026-09-24,highestBoostedValuePlayers,6,F,FFF,0.0,8000,4.0,2026-09-25\n"
        "1,2026-09-24,popularPlayers,7,G,GGG,0.0,20000,1.0,2026-09-25\n",
        encoding="utf-8",
    )
    boards = collect_boards(sport="wnba", csv_paths=[csv_path], roots=[], positions_csv=None)
    report = build_report(boards, sources=[str(csv_path)])
    assert report["draft_count_is_label"] is False
    assert report["summary"]["boards_scored"] == 1
    board = boards[0]
    assert board["hv_display_capture"] > board["hv_raw_capture"]
    assert 7 in board["chalk_ids"]
    assert board["regime"] == "multi_game"

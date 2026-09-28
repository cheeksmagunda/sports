"""HV display rank vs raw value vs chalk vs the hindsight ceiling."""

from __future__ import annotations

from types import SimpleNamespace

from oracle_core.contest_max import (
    LABEL_WINDOW,
    ContestPlayer,
    boards_from_csv,
    compare_board,
    contest_display_rank_weights,
    display_contest_value,
    label_window_observation,
    summarize_boards,
)
from oracle_core.high_tv import sample_weights_for_labeled_rows


def _player(
    player_id: int,
    value: float,
    boost: float = 0.0,
    drafts: float = 0.0,
    position: str = "",
    team: str = "",
    game_id: str = "",
    *,
    on_hv_board: bool = True,
) -> ContestPlayer:
    return ContestPlayer(
        player_id=player_id,
        value=value,
        card_boost=boost,
        draft_count=drafts,
        position=position,
        team=team,
        game_id=game_id,
        on_hv_board=on_hv_board,
    )


def test_display_value_matches_top_slot_times_base_plus_boost() -> None:
    assert display_contest_value(4.987, 0.4) == 4.987 * 2.4
    assert display_contest_value(5.0, 0.0) == 10.0


def test_display_rank_beats_raw_rank_and_chalk_is_not_the_score() -> None:
    """A 3x modest base belongs in the five; the chalk name does not."""

    players = (
        _player(1, 9.0, 0.0, drafts=9000, position="RB", team="A", game_id="g1"),
        _player(2, 6.8, 2.9, drafts=100, position="WR", team="A", game_id="g1"),
        _player(3, 3.4, 3.0, drafts=50, position="K", team="B", game_id="g1"),
        _player(4, 3.3, 3.0, drafts=40, position="DB", team="B", game_id="g1"),
        _player(5, 3.15, 3.0, drafts=30, position="DB", team="A", game_id="g1"),
        _player(6, 3.96, 1.0, drafts=8000, position="WR", team="B", game_id="g1"),
        _player(7, 3.71, 0.1, drafts=7000, position="WR", team="A", game_id="g1"),
        _player(8, 1.0, 0.0, drafts=20000, position="RB", team="B", game_id="g1"),
    )
    board = compare_board(players, sport="nfl", slate_id="g1", slate_date="2026-09-24")
    assert board is not None
    assert board["regime"] == "one_game"
    assert board["hv_display_capture"] == 1.0
    assert board["hv_raw_capture"] < board["hv_display_capture"]
    assert board["chalk_capture"] < board["hv_raw_capture"]
    assert 4 in board["hv_display_ids"]
    assert 4 not in board["hv_raw_ids"]
    assert 7 in board["hv_raw_ids"]
    assert 7 not in board["hv_display_ids"]
    assert 8 in board["chalk_ids"]
    assert board["draft_count_is_label"] is False
    assert "K:1" in board["position_mix"]
    assert "DEF:2" in board["position_mix"]


def test_zero_boost_display_rank_matches_raw_rank() -> None:
    players = tuple(
        _player(pid, value, 0.0, drafts=1000 - pid, team="A" if pid < 4 else "B", game_id="g")
        for pid, value in enumerate((8, 7, 6, 5, 4, 3, 2), start=1)
    )
    board = compare_board(players, sport="wnba", slate_id="z", slate_date="2025-05-16")
    assert board is not None
    assert board["hv_display_ids"] == board["hv_raw_ids"]
    assert board["hv_display_capture"] == 1.0
    assert board["regime"] == "one_game"


def test_team_count_proxy_labels_multi_game_without_game_ids() -> None:
    players = tuple(
        _player(pid, 10 - pid, team=team)
        for pid, team in enumerate(("A", "B", "C", "D", "E", "F"), start=1)
    )
    board = compare_board(players, sport="wnba", slate_id="sun", slate_date="2025-06-01")
    assert board is not None
    assert board["regime"] == "multi_game"
    assert board["regime_method"] == "team_count"
    assert board["position_mix"] == "position_unknown"


def test_weights_ignore_draft_count_and_follow_display_rank() -> None:
    values = {1: 5.0, 2: 3.4, 3: 1.0}
    boosts = {1: 0.0, 2: 3.0, 3: 0.0}
    weights = contest_display_rank_weights(values, boosts, top_k=1, high_weight=4.0)
    assert weights[2] == 4.0
    assert weights[1] == 1.0
    raw = contest_display_rank_weights(values, None, top_k=1, high_weight=4.0)
    assert raw[1] == 4.0
    assert raw[2] == 1.0


def test_labeled_rows_use_card_boost_when_present() -> None:
    rows = [
        SimpleNamespace(
            player_id=1, game_id=9, value=5.0, did_not_play=False, card_boost=0.0, draft_count=99999
        ),
        SimpleNamespace(
            player_id=2, game_id=9, value=3.4, did_not_play=False, card_boost=3.0, draft_count=1
        ),
    ]
    weights = sample_weights_for_labeled_rows(rows, top_k=1, high_weight=4.0)
    assert weights == [1.0, 4.0]


def test_csv_keeps_hv_membership_and_drops_submitted_lineups() -> None:
    text = "\n".join(
        [
            "day,contest_id,player_id,section,value,draft_count,card_boost,team_id",
            "2026-09-24,2196,1,highestBoostedValuePlayers,5.0,10,3.0,A",
            "2026-09-24,2196,1,popularPlayers,5.0,40,3.0,A",
            "2026-09-24,2196,2,highestBoostedValuePlayers,4.0,1,0.0,A",
            "2026-09-24,2196,3,highestBoostedValuePlayers,3.5,1,0.0,B",
            "2026-09-24,2196,4,highestBoostedValuePlayers,3.0,1,0.0,B",
            "2026-09-24,2196,5,highestBoostedValuePlayers,2.5,1,0.0,A",
            "2026-09-24,2196,9,My draft,30.0,0,3.0,A",
            "2026-09-24,2196,8,popularPlayers,1.0,900,0.0,B",
        ]
    )
    boards = boards_from_csv(text, sport="nfl")
    assert len(boards) == 1
    board = boards[0]
    assert 1 in board["hv_display_ids"]
    assert 9 not in board["ceiling_ids"]
    assert 8 in board["chalk_ids"]
    assert board["pool_size"] == 6


def test_label_window_covers_ceiling_players_outside_the_display_five() -> None:
    """Ranks 6-10 by display can still belong in the hindsight five."""

    # Five boosted defenders outrank one skill player on the top-slot key.
    # The hindsight five still wants that skill player, who sits inside the
    # top-10 window and outside the display five.
    players = (
        _player(1, 4.0, 2.5, drafts=1, position="DB"),
        _player(2, 4.0, 2.5, drafts=1, position="DB"),
        _player(3, 4.0, 2.5, drafts=1, position="DB"),
        _player(4, 4.0, 2.5, drafts=1, position="LB"),
        _player(5, 4.0, 2.5, drafts=1, position="LB"),
        _player(6, 10.0, 0.0, drafts=1, position="QB"),
        _player(7, 9.5, 0.0, drafts=1, position="RB"),
    )
    board = compare_board(players, sport="nfl", slate_id="window", slate_date="2024-09-08")
    assert board is not None
    assert board["label_window"] == LABEL_WINDOW
    assert board["hv_display_capture"] < 1.0
    assert board["hv_display_window_capture"] == 1.0
    assert board["hv_display_window_recall"] == 1.0
    assert set(board["ceiling_ids"]) <= set(board["hv_display_window_ids"])
    assert not set(board["ceiling_ids"]) <= set(board["hv_display_ids"])
    assert board["chalk_window_capture"] <= board["hv_display_window_capture"]
    observation = label_window_observation(
        slate_id="window",
        capture=board["hv_display_window_capture"],
    )
    assert observation["@type"] == "Observation"
    assert observation["value"]["value"] == 1.0
    flags = {item["name"]: item["value"] for item in observation["additionalProperty"]}
    assert flags["draft count is label"] is False
    assert flags["winning drafts are label"] is False
    assert flags["label window"] == LABEL_WINDOW
    assert "draft_count" not in observation["measuredProperty"]["name"]


def test_display_window_profile_separates_hv_top_10_from_chalk() -> None:
    """High draft counts stay on the board and outside the display window."""

    players = [_player(pid, 5.0, 3.0, drafts=1, position="RB") for pid in range(1, 11)]
    players.append(_player(11, 8.0, 0.0, drafts=100, position="RB"))
    players.append(_player(12, 8.0, 0.0, drafts=90, position="WR"))
    board = compare_board(tuple(players), sport="nfl", slate_id="profile", slate_date="2024-09-08")
    assert board is not None
    assert board["hv_section_size"] == 12
    assert list(board["hv_display_window_ids"]) == list(range(1, 11))
    assert 11 in board["chalk_window_ids"]
    assert 11 not in board["hv_display_window_ids"]
    assert board["hv_display_window_mean_value"] == 5.0
    assert board["hv_display_window_mean_boost"] == 3.0
    assert board["chalk_window_mean_value"] == 5.6
    assert board["chalk_window_mean_boost"] == 2.4
    assert board["display_vs_chalk_window_overlap"] == 0.8
    summary = summarize_boards([board])
    assert summary["hv_display_window_mean_boost"] == 3.0
    assert summary["display_vs_chalk_window_overlap"] == 0.8
    assert summary["draft_count_is_label"] is False


def test_summarize_slices_by_sport_and_regime() -> None:
    one = compare_board(
        tuple(_player(i, 10 - i, team="A", game_id="only") for i in range(1, 7)),
        sport="nfl",
        slate_id="a",
    )
    multi = compare_board(
        tuple(_player(i, 10 - i, team=f"T{i}", game_id=f"g{i}") for i in range(1, 7)),
        sport="wnba",
        slate_id="b",
    )
    assert one is not None and multi is not None
    summary = summarize_boards([one, multi])
    assert summary["boards_scored"] == 2
    assert summary["by_regime"]["one_game"]["boards"] == 1
    assert summary["by_regime"]["multi_game"]["boards"] == 1
    assert set(summary["by_sport"]) == {"nfl", "wnba"}
    assert summary["draft_count_is_label"] is False

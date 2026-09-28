"""Contest-display weights and the offline HV/chalk/ceiling map."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from nfl_oracle.recommendations.display_rank_weights import (
    DISPLAY_TOP_K_ENV,
    boosts_for_history_rows,
    contest_display_top_ids,
    resolve_contest_display_top_k,
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


def _twelve_game_rows() -> list[SimpleNamespace]:
    # player 1 is the raw leader. player 12 is the raw trailer.
    return [
        SimpleNamespace(
            player_id=player_id,
            game_id=9,
            value=float(30 - player_id),
            did_not_play=False,
            draft_count=99_999 if player_id == 11 else 1,
            winning_draft=player_id == 11,
        )
        for player_id in range(1, 13)
    ]


def _display_boosts() -> dict[tuple[int, int], float]:
    # Boost 3.0 lifts player 12 above the raw leader on value * (2 + boost).
    return {(player_id, 9): (3.0 if player_id == 12 else 0.0) for player_id in range(1, 13)}


def test_boost_map_defaults_to_display_top_10_and_ignores_drafts() -> None:
    rows = _twelve_game_rows()
    bare = [
        SimpleNamespace(player_id=row.player_id, game_id=row.game_id, value=row.value)
        for row in rows
    ]
    weights = sample_weights_contest_display(rows, boosts=_display_boosts(), high_weight=4.0)
    bare_weights = sample_weights_contest_display(bare, boosts=_display_boosts(), high_weight=4.0)
    assert weights == bare_weights
    assert weights.count(4.0) == 10
    assert weights[11] == 4.0  # player 12, display rank 1
    assert weights[9] == 1.0  # player 10, raw top-10, display rank 11
    assert weights[10] == 1.0  # player 11, huge draft count, outside the display ten


def test_missing_boost_map_stays_at_raw_top_five() -> None:
    weights = sample_weights_contest_display(_twelve_game_rows(), boosts=None, high_weight=4.0)
    assert weights.count(4.0) == 5
    assert weights[:5] == [4.0, 4.0, 4.0, 4.0, 4.0]
    assert weights[5:] == [1.0] * 7


def test_display_top_k_env_needs_a_boost_map(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DISPLAY_TOP_K_ENV, "3")
    boosted = sample_weights_contest_display(
        _twelve_game_rows(), boosts=_display_boosts(), high_weight=4.0
    )
    raw = sample_weights_contest_display(_twelve_game_rows(), boosts=None, high_weight=4.0)
    assert boosted.count(4.0) == 3
    assert boosted[11] == 4.0
    assert raw.count(4.0) == 5
    assert resolve_contest_display_top_k(boosts_present=True, top_k=1) == 1


def test_display_top_k_env_rejects_non_integers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DISPLAY_TOP_K_ENV, "nope")
    with pytest.raises(ValueError, match=DISPLAY_TOP_K_ENV):
        resolve_contest_display_top_k(boosts_present=True)


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

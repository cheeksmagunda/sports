"""HV-rank five, draft-count chalk, and hindsight ceiling use the draft-image law."""

from __future__ import annotations

import json
from pathlib import Path

from nfl_oracle.contests.parse import load_contest
from nfl_oracle.contests.schema import DraftStatRow
from nfl_oracle.contests.store import ContestStore
from nfl_oracle.replay.hv_board_replay import (
    chalk_rank_ids,
    hv_rank_ids,
    replay_hv_board,
    score_five,
)
from nfl_oracle.replay.hv_board_replay_cli import main as replay_main

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "corpus_c_hv"


def _stat(
    player_id: int,
    *,
    section: str,
    value: float,
    drafts: int,
    boost: float,
) -> DraftStatRow:
    return DraftStatRow(
        contest_id=1,
        player_id=player_id,
        section=section,
        card_boost=boost,
        value=value,
        draft_count=drafts,
    )


def test_hv_rank_ignores_draft_count_and_chalk_uses_it() -> None:
    rows = [
        _stat(1, section="highestBoostedValuePlayers", value=10.0, drafts=1, boost=0.0),
        _stat(2, section="highestBoostedValuePlayers", value=9.0, drafts=2, boost=0.0),
        _stat(3, section="highestBoostedValuePlayers", value=8.0, drafts=3, boost=0.0),
        _stat(4, section="highestBoostedValuePlayers", value=7.0, drafts=4, boost=0.0),
        _stat(5, section="highestBoostedValuePlayers", value=6.0, drafts=5, boost=0.0),
        _stat(6, section="mostDraftedPlayers", value=1.0, drafts=500, boost=0.0),
    ]
    assert hv_rank_ids(rows) == (1, 2, 3, 4, 5)
    assert chalk_rank_ids(rows)[0] == 6


def test_score_five_is_value_times_slot_plus_boost() -> None:
    scored = score_five(
        (1, 2, 3, 4, 5),
        values={1: 5.0, 2: 4.0, 3: 3.0, 4: 2.0, 5: 1.0},
        boosts={1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0},
        slot_multipliers=(2.0, 1.8, 1.6, 1.4, 1.2),
        kind="hv_rank_five",
    )
    assert scored is not None
    # 5*2 + 4*1.8 + 3*1.6 + 2*1.4 + 1*1.2 = 10 + 7.2 + 4.8 + 2.8 + 1.2
    assert scored.total == 26.0
    assert [card.player_id for card in scored.cards] == [1, 2, 3, 4, 5]
    assert scored.cards[0].score == 10.0


def test_fixture_9001_hv_five_uses_board_values_not_draft_counts() -> None:
    parsed = load_contest(ContestStore(FIXTURES), 9001)
    assert parsed is not None
    report = replay_hv_board(parsed)
    assert report is not None
    hv = report["hv_five"]
    assert hv["player_ids"] == [401, 402, 403, 404, 405]
    # 5*2 + 4.6*(1.8+0.5) + 4.2*(1.6+1) + 3.8*(1.4+1.5) + 3.4*(1.2+2)
    assert hv["total"] == 53.4
    assert report["chalk_five"]["player_ids"] == [401, 402, 403, 404, 405]
    assert report["hv_minus_chalk"] == 0.0
    assert report["hindsight"]["score"] >= hv["total"]
    assert report["draft_count_is_label"] is False
    for card in hv["cards"]:
        expected = card["value"] * (card["slot_multiplier"] + card["card_boost"])
        assert card["score"] == round(expected, 6)


def test_replay_cli_on_fixtures(capsys) -> None:
    code = replay_main(["--contest-root", str(FIXTURES)])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["boards_scored"] == 1
    assert payload["contest_entry"] is False
    assert payload["mean_hv_total"] == 53.4

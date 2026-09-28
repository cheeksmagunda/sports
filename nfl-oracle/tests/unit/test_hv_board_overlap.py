"""Screenshot HV/TDV boards: law, board capture, and regime isolation."""

import json
from pathlib import Path

from pytest import approx as pytest_approx

from nfl_oracle.replay.hv_board_overlap import (
    BoardRow,
    hv_board_success,
    law_value,
    parse_draft_count,
    parse_slot,
    score_board,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "hv_screenshot_boards"


def _load(name: str) -> tuple[str, tuple[BoardRow, ...]]:
    payload = json.loads((FIXTURES / name).read_text())
    rows = tuple(
        BoardRow(
            player_id=int(raw["player_id"]),
            name=str(raw["name"]),
            position=str(raw["position"]),
            team=str(raw["team"]),
            base=float(raw["base"]),
            boost=float(raw["boost"]),
            most_common_slot=parse_slot(str(raw["slot"])),
            draft_count=parse_draft_count(raw["drafts"]),
            displayed_value=float(raw["value"]),
        )
        for raw in payload["rows"]
    )
    return str(payload["regime"]), rows


def test_displayed_value_matches_slot_plus_boost_law() -> None:
    _regime, rows = _load("2026-09-27.json")
    boswell = next(row for row in rows if row.name == "Chris Boswell")
    smith = next(row for row in rows if row.name == "Genesis Smith")
    assert law_value(boswell) == 29.0
    assert law_value(smith) == 5.4 * (1.2 + 3.0)
    residual = max(abs(law_value(row) - row.displayed_value) for row in rows)
    assert residual < 0.25


def test_success_is_the_hv_board_value_not_a_side_ranking() -> None:
    board = ((1, 10.0), (2, 8.0), (3, 1.0))
    hits, capture = hv_board_success((1, 2), board, n=2)
    assert hits == 2
    assert capture == pytest_approx(1.0)
    missed, partial = hv_board_success((1, 9), board, n=2)
    assert missed == 1
    assert partial == pytest_approx(10.0 / 18.0)
    assert hv_board_success((), ()) == (None, None)


def test_sunday_board_capture_and_sep20_two_kickers() -> None:
    regime, rows = _load("2026-09-20.json")
    scored = score_board(rows, regime=regime)
    assert scored["success_metric"] == "hv_tdv_board_top5"
    assert "chalk_top5" not in scored
    positions = scored["hv_top5_positions"]
    assert isinstance(positions, dict)
    assert positions["kickers"] == 2
    policies = {item["name"]: item for item in scored["policies"]}  # type: ignore[index]
    identity = policies["identity_uncapped"]
    blend = policies["boost_0.75_uncapped"]
    capped = policies["boost_0.75_def1_k1"]
    assert identity["hv_top5_hits"] > blend["hv_top5_hits"]
    assert identity["hv_board_capture"] > blend["hv_board_capture"]
    assert capped["hv_board_capture"] < identity["hv_board_capture"]
    assert capped["kickers"] <= 1


def test_one_night_is_not_filled_from_sunday_boards() -> None:
    sep20_regime, sep20 = _load("2026-09-20.json")
    sep27_regime, sep27 = _load("2026-09-27.json")
    assert {sep20_regime, sep27_regime} == {"sunday_multi"}
    for rows, regime in ((sep20, sep20_regime), (sep27, sep27_regime)):
        scored = score_board(rows, regime=regime)
        assert scored["regime"] == "sunday_multi"
        assert "one_night" not in str(scored["regime"])

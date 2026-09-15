from __future__ import annotations

import importlib
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from nfl_oracle.calendar import week_close as wc

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
EASTERN = ZoneInfo("America/New_York")


def _import(name: str):
    sys.path.insert(0, str(SCRIPTS))
    try:
        module = importlib.import_module(name)
        return importlib.reload(module)
    finally:
        sys.path.remove(str(SCRIPTS))


CSV_HEADER = (
    "season,week,game_id,gameday,gametime,home_team,away_team,"
    "home_score,away_score,result,game_type\n"
)


def _row(
    *,
    season: int = 2026,
    week: int = 1,
    gameday: str,
    gametime: str = "13:00",
    game_id: str = "2026_01_TEST",
    home_score: str = "",
    away_score: str = "",
    result: str = "",
    game_type: str = "REG",
    home: str = "AAA",
    away: str = "BBB",
) -> str:
    return (
        f"{season},{week},{game_id},{gameday},{gametime},{home},{away},"
        f"{home_score},{away_score},{result},{game_type}\n"
    )


def test_parse_week_games_excludes_preseason_and_tolerates_bad_rows() -> None:
    raw = (
        CSV_HEADER
        + _row(gameday="2026-09-10", week=1, home_score="24", away_score="17", result="7")
        + _row(gameday="2026-08-20", week=0, game_type="PRE")
        + "garbage,row\n"
    )
    games = wc.parse_week_games(raw)
    assert len(games) == 1
    assert games[0].gameday == date(2026, 9, 10)
    assert games[0].home_score == 24
    assert games[0].away_score == 17


def test_final_slate_picks_latest_kickoff_not_hardcoded_monday() -> None:
    games = wc.parse_week_games(
        CSV_HEADER
        + _row(gameday="2026-09-10", gametime="20:15", game_id="tnf")
        + _row(gameday="2026-09-14", gametime="13:00", game_id="sun_early")
        + _row(gameday="2026-09-14", gametime="20:20", game_id="snf")
        + _row(gameday="2026-09-15", gametime="20:15", game_id="mnf")
        + _row(gameday="2026-09-17", week=2, gametime="20:15", game_id="w2")
    )
    final = wc.final_slate_for_week(games, season=2026, week=1)
    assert final is not None
    assert final.final_gameday == date(2026, 9, 15)
    assert final.final_game.game_id == "mnf"


def test_final_slate_sunday_flex_week_not_monday() -> None:
    games = wc.parse_week_games(
        CSV_HEADER
        + _row(gameday="2026-09-24", week=3, gametime="20:15", game_id="tnf")
        + _row(gameday="2026-09-28", week=3, gametime="20:20", game_id="snf")
    )
    final = wc.final_slate_for_week(games, season=2026, week=3)
    assert final is not None
    assert final.final_gameday == date(2026, 9, 28)
    assert wc.is_final_slate_day(final, date(2026, 9, 28)) is True
    assert wc.is_final_slate_day(final, date(2026, 9, 29)) is False


def test_resolve_week_final_looks_back_from_midweek() -> None:
    games = wc.parse_week_games(
        CSV_HEADER
        + _row(gameday="2026-09-14", gametime="13:00")
        + _row(gameday="2026-09-15", gametime="20:15", game_id="mnf")
    )
    final = wc.resolve_week_final(games, as_of=date(2026, 9, 17))
    assert final is not None
    assert final.final_gameday == date(2026, 9, 15)


def test_evaluate_gate_ready_when_finalized_and_buffer_elapsed() -> None:
    games = wc.parse_week_games(
        CSV_HEADER
        + _row(
            gameday="2026-09-15",
            gametime="20:15",
            game_id="mnf",
            home_score="27",
            away_score="24",
            result="3",
        )
    )
    # Kickoff 20:15 ET + 3h + 1h = 00:15 ET next calendar day.
    now = datetime(2026, 9, 16, 4, 30, tzinfo=UTC)  # 00:30 ET
    decision = wc.evaluate_gate(games, as_of=date(2026, 9, 15), now=now)
    assert decision.should_run is True
    assert decision.reason == "ready"
    assert decision.finalized is True
    assert decision.buffer_elapsed is True


def test_evaluate_gate_waits_for_finalization_even_after_buffer_floor() -> None:
    games = wc.parse_week_games(
        CSV_HEADER + _row(gameday="2026-09-15", gametime="20:15", game_id="mnf")
    )
    now = datetime(2026, 9, 16, 6, 0, tzinfo=UTC)  # well past floor, no scores
    decision = wc.evaluate_gate(games, as_of=date(2026, 9, 15), now=now)
    assert decision.should_run is False
    assert decision.reason == "final_game_not_finalized"
    assert decision.buffer_elapsed is True


def test_evaluate_gate_waits_for_buffer_when_already_final() -> None:
    games = wc.parse_week_games(
        CSV_HEADER
        + _row(
            gameday="2026-09-15",
            gametime="20:15",
            game_id="mnf",
            home_score="27",
            away_score="24",
            result="3",
        )
    )
    # 22:00 ET same day: only 1h45m after kickoff, before 3h+1h floor.
    now = datetime(2026, 9, 16, 2, 0, tzinfo=UTC)
    decision = wc.evaluate_gate(games, as_of=date(2026, 9, 15), now=now)
    assert decision.should_run is False
    assert decision.reason == "buffer_not_elapsed"
    assert decision.finalized is True


def test_evaluate_gate_not_on_non_final_day() -> None:
    games = wc.parse_week_games(
        CSV_HEADER
        + _row(gameday="2026-09-14", gametime="13:00", home_score="10", away_score="7", result="3")
        + _row(
            gameday="2026-09-15",
            gametime="20:15",
            game_id="mnf",
            home_score="27",
            away_score="24",
            result="3",
        )
    )
    now = datetime(2026, 9, 16, 6, 0, tzinfo=UTC)
    decision = wc.evaluate_gate(games, as_of=date(2026, 9, 14), now=now)
    assert decision.should_run is False
    assert decision.reason == "not_final_slate_day"
    assert decision.is_final_slate_day is False
    assert decision.final_gameday == date(2026, 9, 15)


def test_target_day_is_week_final_for_dayclose_supersede() -> None:
    games = wc.parse_week_games(
        CSV_HEADER
        + _row(gameday="2026-09-14", gametime="13:00")
        + _row(gameday="2026-09-15", gametime="20:15", game_id="mnf")
    )
    assert wc.target_day_is_week_final(games, target_day=date(2026, 9, 15)) is True
    assert wc.target_day_is_week_final(games, target_day=date(2026, 9, 14)) is False


def test_default_as_of_is_today_in_eastern() -> None:
    now = datetime(2026, 9, 16, 2, 0, tzinfo=UTC)  # 2026-09-15 22:00 EDT
    assert wc.default_as_of(now) == date(2026, 9, 15)


def test_main_writes_ready_outputs(tmp_path, monkeypatch) -> None:
    gate = _import("nfl_weekclose_gate")
    monkeypatch.setattr(
        gate,
        "_download",
        lambda urls: (
            CSV_HEADER
            + _row(
                gameday="2026-09-15",
                gametime="20:15",
                game_id="mnf",
                home_score="27",
                away_score="24",
                result="3",
            )
        ),
    )
    output_file = tmp_path / "github_output"
    now = "2026-09-16T04:30:00+00:00"

    exit_code = gate.main(
        ["--as-of", "2026-09-15", "--now", now, "--github-output", str(output_file)]
    )

    assert exit_code == 0
    text = output_file.read_text(encoding="utf-8")
    assert "should_run=true\n" in text
    assert "reason=ready\n" in text
    assert "is_final_slate_day=true\n" in text
    assert "final_game_id=mnf\n" in text
    assert "finalized=true\n" in text

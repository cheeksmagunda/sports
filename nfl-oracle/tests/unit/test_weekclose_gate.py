from __future__ import annotations

import importlib
import sys
from datetime import UTC, date, datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _import(name: str):
    sys.path.insert(0, str(SCRIPTS))
    try:
        module = importlib.import_module(name)
        return importlib.reload(module)
    finally:
        sys.path.remove(str(SCRIPTS))


CSV_HEADER = "season,week,game_id,gameday,home_team,away_team,game_type\n"


def _row(
    *,
    season: int = 2026,
    week: int = 1,
    gameday: str,
    game_type: str = "REG",
    game_id: str = "2026_01_TEST",
) -> str:
    return f"{season},{week},{game_id},{gameday},AAA,BBB,{game_type}\n"


def test_parse_week_games_excludes_preseason_and_tolerates_bad_rows() -> None:
    gate = _import("nfl_weekclose_gate")
    raw = (
        CSV_HEADER
        + _row(gameday="2026-09-10", week=1)
        + _row(gameday="2026-08-20", week=0, game_type="PRE")
        + "garbage,row\n"
    )
    assert gate.parse_week_games(raw) == [(2026, 1, date(2026, 9, 10))]


def test_final_slate_for_week_picks_latest_gameday() -> None:
    gate = _import("nfl_weekclose_gate")
    games = [
        (2026, 1, date(2026, 9, 10)),  # TNF
        (2026, 1, date(2026, 9, 14)),  # Sunday
        (2026, 1, date(2026, 9, 15)),  # MNF final slate
        (2026, 2, date(2026, 9, 17)),
    ]
    final = gate.final_slate_for_week(games, season=2026, week=1)
    assert final is not None
    assert final.final_gameday == date(2026, 9, 15)
    assert final.season == 2026
    assert final.week == 1


def test_resolve_week_final_looks_back_from_midweek() -> None:
    gate = _import("nfl_weekclose_gate")
    games = [
        (2026, 1, date(2026, 9, 10)),
        (2026, 1, date(2026, 9, 14)),
        (2026, 1, date(2026, 9, 15)),
    ]
    # Wednesday after MNF still resolves week 1's final Monday slate.
    final = gate.resolve_week_final(games, as_of=date(2026, 9, 17))
    assert final is not None
    assert final.final_gameday == date(2026, 9, 15)


def test_is_final_slate_day_not_hardcoded_monday() -> None:
    gate = _import("nfl_weekclose_gate")
    # Flex: week ends on Sunday (no Monday game).
    games = [
        (2026, 3, date(2026, 9, 24)),
        (2026, 3, date(2026, 9, 28)),
    ]
    final = gate.final_slate_for_week(games, season=2026, week=3)
    assert gate.is_final_slate_day(final, date(2026, 9, 28)) is True
    assert gate.is_final_slate_day(final, date(2026, 9, 29)) is False


def test_default_as_of_is_today_in_eastern() -> None:
    gate = _import("nfl_weekclose_gate")
    now = datetime(2026, 9, 16, 2, 0, tzinfo=UTC)  # 2026-09-15 22:00 EDT
    assert gate.default_as_of(now) == date(2026, 9, 15)


def test_main_scaffold_never_sets_should_run(tmp_path, monkeypatch) -> None:
    gate = _import("nfl_weekclose_gate")
    monkeypatch.setattr(
        gate,
        "_download",
        lambda urls: CSV_HEADER
        + _row(gameday="2026-09-14", week=1)
        + _row(gameday="2026-09-15", week=1),
    )
    output_file = tmp_path / "github_output"

    exit_code = gate.main(
        ["--as-of", "2026-09-15", "--github-output", str(output_file)]
    )

    assert exit_code == 0
    text = output_file.read_text(encoding="utf-8")
    assert "should_run=false\n" in text
    assert "reason=scaffold_no_live_finalization_check\n" in text
    assert "is_final_slate_day=true\n" in text
    assert "final_gameday=2026-09-15\n" in text
    assert "season=2026\n" in text
    assert "week=1\n" in text


def test_main_reports_non_final_day(tmp_path, monkeypatch) -> None:
    gate = _import("nfl_weekclose_gate")
    monkeypatch.setattr(
        gate,
        "_download",
        lambda urls: CSV_HEADER
        + _row(gameday="2026-09-14", week=1)
        + _row(gameday="2026-09-15", week=1),
    )
    output_file = tmp_path / "github_output"

    exit_code = gate.main(
        ["--as-of", "2026-09-14", "--github-output", str(output_file)]
    )

    assert exit_code == 0
    text = output_file.read_text(encoding="utf-8")
    assert "should_run=false\n" in text
    assert "is_final_slate_day=false\n" in text
    assert "final_gameday=2026-09-15\n" in text

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


def _row(gameday: str, *, game_type: str = "REG") -> str:
    return f"2026,1,2026_01_TEST,{gameday},AAA,BBB,{game_type}\n"


def test_game_days_excludes_preseason_and_tolerates_bad_rows() -> None:
    gate = _import("nfl_dayclose_gate")
    raw = CSV_HEADER + _row("2026-09-10") + _row("2026-08-20", game_type="PRE") + "garbage,row\n"
    assert gate.game_days(raw) == {date(2026, 9, 10)}


def test_has_slate_in_window_covers_the_whole_catchup_range() -> None:
    gate = _import("nfl_dayclose_gate")
    days = {date(2026, 9, 3)}  # 7 days before target_day, inclusive edge
    assert gate.has_slate_in_window(days, target_day=date(2026, 9, 9), window_days=7) is True
    assert gate.has_slate_in_window(days, target_day=date(2026, 9, 9), window_days=6) is False


def test_default_target_day_is_yesterday_in_eastern() -> None:
    gate = _import("nfl_dayclose_gate")
    now = datetime(2026, 9, 10, 2, 0, tzinfo=UTC)  # 2026-09-09 22:00 EDT
    assert gate.default_target_day(now) == date(2026, 9, 8)


def test_main_writes_github_output(tmp_path, monkeypatch) -> None:
    gate = _import("nfl_dayclose_gate")
    monkeypatch.setattr(gate, "_download", lambda urls: CSV_HEADER + _row("2026-09-07"))
    output_file = tmp_path / "github_output"

    exit_code = gate.main(
        ["--day", "2026-09-09", "--window-days", "7", "--github-output", str(output_file)]
    )

    assert exit_code == 0
    assert output_file.read_text(encoding="utf-8") == "has_slate=true\n"


def test_main_reports_no_slate_outside_the_window(tmp_path, monkeypatch) -> None:
    gate = _import("nfl_dayclose_gate")
    monkeypatch.setattr(gate, "_download", lambda urls: CSV_HEADER + _row("2026-08-01"))
    output_file = tmp_path / "github_output"

    exit_code = gate.main(
        ["--day", "2026-09-09", "--window-days", "7", "--github-output", str(output_file)]
    )

    assert exit_code == 0
    assert output_file.read_text(encoding="utf-8") == "has_slate=false\n"


def test_main_rejects_a_non_positive_window() -> None:
    gate = _import("nfl_dayclose_gate")
    assert gate.main(["--window-days", "0"]) == 1

"""Public T-40 runner: zero boost, full roster, no invented five."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from nhl_oracle.contest.pick import select_no_boost_five_from_full_pool
from nhl_oracle.contract.boost_gate import NHL_EXPECTED_TEAM_COUNT
from nhl_oracle.contract.schema import NhlCandidate
from nhl_oracle.scheduler.readiness import evaluate_win_freeze_readiness
from nhl_oracle.scheduler.watchdog import evaluate_t40_watch, games_on_eastern_date

# The scripts directory is not a package. Load the file the workflow runs.
_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "nhl_t40_watchdog.py"
_spec = importlib.util.spec_from_file_location("nhl_t40_watchdog", _SCRIPT)
assert _spec is not None and _spec.loader is not None
_watch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_watch)

DAY = date(2026, 9, 29)
OPENERS = (
    ("2026-09-29T21:00:00Z", "FLA", "CAR"),
    ("2026-09-29T23:00:00Z", "MTL", "TOR"),
    ("2026-09-30T00:00:00Z", "NYR", "BOS"),
    ("2026-09-30T02:00:00Z", "VAN", "EDM"),
    ("2026-09-30T02:30:00Z", "CHI", "VGK"),
    ("2026-09-30T23:30:00Z", "PIT", "PHI"),
)


def _schedule() -> dict[str, object]:
    games = []
    for index, (start, away, home) in enumerate(OPENERS, start=1):
        games.append(
            {
                "id": index,
                "season": 20262027,
                "gameType": 2,
                "gameState": "FUT",
                "startTimeUTC": start,
                "awayTeam": {"abbrev": away},
                "homeTeam": {"abbrev": home},
            }
        )
    games.append(
        {
            "id": 99,
            "season": 20262027,
            "gameType": 1,
            "gameState": "FUT",
            "startTimeUTC": "2026-09-29T17:00:00Z",
            "awayTeam": {"abbrev": "PRE"},
            "homeTeam": {"abbrev": "SEA"},
        }
    )
    return {"gameWeek": [{"games": games}]}


def _summary(rows: int, games_played: int) -> dict[str, object]:
    return {
        "total": rows,
        "data": [{"teamId": index, "gamesPlayed": games_played} for index in range(1, rows + 1)],
    }


def test_opening_night_keeps_five_eastern_games_and_drops_preseason() -> None:
    games = games_on_eastern_date(_schedule(), DAY)
    assert len(games) == 5
    assert games[0].away == "FLA"
    assert games[0].home == "CAR"
    assert games[-1].start_at == datetime(2026, 9, 30, 2, 30, tzinfo=UTC)
    assert {game.away for game in games} | {game.home for game in games} == {
        "FLA",
        "CAR",
        "MTL",
        "TOR",
        "NYR",
        "BOS",
        "VAN",
        "EDM",
        "CHI",
        "VGK",
    }


def test_before_t40_waits_and_keeps_zero_boost_with_empty_summary() -> None:
    now = datetime(2026, 9, 29, 20, 0, tzinfo=UTC)
    report = evaluate_t40_watch(
        day=DAY,
        schedule=_schedule(),
        team_summary={"data": [], "total": 0},
        now=now,
    )
    assert report.status == "waiting"
    assert report.reason == "before_t40_window"
    assert report.t40_open == datetime(2026, 9, 29, 20, 20, tzinfo=UTC)
    assert report.zero_boost_active is True
    assert report.teams_observed == 0
    assert report.freeze_ready is False
    assert report.to_dict()["pick_player_ids"] is None
    assert report.contest_entry is False


def test_inside_t40_without_pool_alerts() -> None:
    now = datetime(2026, 9, 29, 20, 30, tzinfo=UTC)
    report = evaluate_t40_watch(
        day=DAY,
        schedule=_schedule(),
        team_summary=_summary(NHL_EXPECTED_TEAM_COUNT, 0),
        now=now,
    )
    assert report.status == "alert"
    assert report.reason == "inside_t40_without_full_roster_pool"
    assert report.zero_boost_active is True
    assert report.slate_teams == 10


def test_cleared_coverage_is_not_zero_boost_but_still_needs_a_pool() -> None:
    now = datetime(2026, 9, 29, 20, 30, tzinfo=UTC)
    report = evaluate_t40_watch(
        day=DAY,
        schedule=_schedule(),
        team_summary=_summary(NHL_EXPECTED_TEAM_COUNT, 1),
        now=now,
    )
    assert report.zero_boost_active is False
    assert report.status == "alert"
    assert report.freeze_ready is False


def test_no_boost_picker_refuses_a_five_player_stub_and_ignores_card_boost() -> None:
    values = {index: float(10 - index) for index in range(1, 9)}
    try:
        select_no_boost_five_from_full_pool(values, expected_pool_size=5)
    except ValueError as error:
        assert str(error) == "full_roster_pool_required"
    else:
        raise AssertionError("stub pool was accepted")
    pick = select_no_boost_five_from_full_pool(
        values,
        expected_pool_size=8,
        card_boosts={8: 20.0, 1: 0.5},
        team_games_played=None,
        slate_teams=("A", "B"),
        team_card_counts={"A": 4, "B": 4},
    )
    assert pick.player_ids == (1, 2, 3, 4, 5)
    assert pick.lineup_score.boost_gated is True
    assert all(card.effective_card_boost == 0.0 for card in pick.lineup_score.contributions)


def test_picker_refuses_a_slate_team_missing_from_the_pool() -> None:
    values = {index: float(index) for index in range(1, 8)}
    try:
        select_no_boost_five_from_full_pool(
            values,
            expected_pool_size=7,
            slate_teams=("A", "B"),
            team_card_counts={"A": 7},
        )
    except ValueError as error:
        assert "slate_team_missing_from_pool" in str(error)
    else:
        raise AssertionError("missing team was accepted")


def test_readiness_rejects_roster_sized_pool() -> None:
    clock = datetime(2026, 9, 29, 20, 40, tzinfo=UTC)
    candidates = tuple(
        NhlCandidate(
            player_id=index,
            position="C",
            score_value=float(index),
            captured_at="2026-09-29T20:00:00+00:00",
        )
        for index in range(1, 6)
    )
    report = evaluate_win_freeze_readiness(
        candidates=candidates,
        expected_pool_size=5,
        games_scheduled=1,
        games_captured=1,
        projected_values={index: float(index) for index in range(1, 6)},
        now=clock,
        lock_at=clock + timedelta(minutes=20),
    )
    assert report.freeze_ready is False
    assert report.pick_player_ids is None
    assert "full_roster_pool_required" in report.blocked_reasons


def test_watchdog_cli_writes_waiting_report(tmp_path: Path) -> None:
    schedule = tmp_path / "schedule.json"
    summary = tmp_path / "summary.json"
    report = tmp_path / "report.md"
    output = tmp_path / "github.txt"
    schedule.write_text(json.dumps(_schedule()), encoding="utf-8")
    summary.write_text(json.dumps({"data": [], "total": 0}), encoding="utf-8")
    code = _watch.main(
        [
            "--day",
            "2026-09-29",
            "--now",
            "2026-09-29T20:00:00+00:00",
            "--schedule-json",
            str(schedule),
            "--summary-json",
            str(summary),
            "--report",
            str(report),
            "--github-output",
            str(output),
        ]
    )
    assert code == 0
    text = report.read_text(encoding="utf-8")
    assert "status: `waiting`" in text
    assert "pick_player_ids: none" in text
    assert "contest_entry: false" in text
    assert "status=waiting" in output.read_text(encoding="utf-8")


def test_workflow_is_a_read_only_cron() -> None:
    workflow = (
        Path(__file__).resolve().parents[2] / ".github" / "workflows" / "nhl-t40-watchdog.yml"
    )
    text = workflow.read_text(encoding="utf-8")
    assert "cron:" in text
    assert "nhl-oracle/scripts/nhl_t40_watchdog.py" in text
    assert "issues: write" not in text
    assert "contents: read" in text

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from nfl_oracle.calendar.week_close import WeekGame
from nfl_oracle.recommendations.watchdog import evaluate_t40_deadline

DAY = date(2026, 9, 20)


def _games(*, gametime: str = "13:00", late_gametime: str = "16:25") -> list[WeekGame]:
    return [
        WeekGame(
            season=2026,
            week=2,
            game_id="2026_02_EARLY",
            gameday=DAY,
            gametime=gametime,
            home_team="DAL",
            away_team="PHI",
            home_score=None,
            away_score=None,
            result="",
        ),
        WeekGame(
            season=2026,
            week=2,
            game_id="2026_02_LATE",
            gameday=DAY,
            gametime=late_gametime,
            home_team="KC",
            away_team="DEN",
            home_score=None,
            away_score=None,
            result="",
        ),
    ]


def test_watchdog_reports_no_slate_when_the_schedule_has_no_games() -> None:
    report = evaluate_t40_deadline(
        day=DAY,
        games=[],
        frozen=None,
        latest_run=None,
        checked_at=datetime(2026, 9, 20, 16, tzinfo=UTC),
    )

    assert report.status == "no_slate"
    assert report.reason == "no_scheduled_games"


def test_watchdog_stays_pending_before_the_deadline_elapses() -> None:
    report = evaluate_t40_deadline(
        day=DAY,
        games=_games(),
        frozen=None,
        latest_run={"status": "waiting", "detail_code": "waiting_for_t40"},
        checked_at=datetime(2026, 9, 20, 16, 25, tzinfo=UTC),
        grace_minutes=10,
    )

    assert report.status == "pending"
    assert report.reason == "deadline_not_elapsed"
    assert report.freeze_due_at == datetime(2026, 9, 20, 16, 20, tzinfo=UTC)
    assert report.alert_deadline_at == report.freeze_due_at + timedelta(minutes=10)


def test_watchdog_alerts_when_no_freeze_exists_after_the_deadline() -> None:
    report = evaluate_t40_deadline(
        day=DAY,
        games=_games(),
        frozen=None,
        latest_run={"status": "error", "detail_code": "valueerror"},
        checked_at=datetime(2026, 9, 20, 16, 35, tzinfo=UTC),
        grace_minutes=10,
    )

    assert report.status == "alert"
    assert report.reason == "no_freeze_by_deadline"


def test_watchdog_alerts_when_the_freeze_lands_after_the_deadline() -> None:
    report = evaluate_t40_deadline(
        day=DAY,
        games=_games(),
        frozen={"frozen_at": "2026-09-20T16:31:00+00:00"},
        latest_run={"status": "ready", "detail_code": "five_picks_frozen"},
        checked_at=datetime(2026, 9, 20, 16, 40, tzinfo=UTC),
        grace_minutes=10,
    )

    assert report.status == "alert"
    assert report.reason == "freeze_missed_deadline"


def test_watchdog_accepts_an_on_time_freeze() -> None:
    report = evaluate_t40_deadline(
        day=DAY,
        games=_games(),
        frozen={"frozen_at": "2026-09-20T16:28:00+00:00"},
        latest_run={"status": "ready", "detail_code": "five_picks_frozen"},
        checked_at=datetime(2026, 9, 20, 16, 35, tzinfo=UTC),
        grace_minutes=10,
    )

    assert report.status == "ok"
    assert report.reason == "freeze_on_time"


def test_watchdog_surfaces_schedule_rows_that_lack_gametime() -> None:
    report = evaluate_t40_deadline(
        day=DAY,
        games=_games(gametime="", late_gametime=""),
        frozen=None,
        latest_run=None,
        checked_at=datetime(2026, 9, 20, 16, tzinfo=UTC),
    )

    assert report.status == "unresolved"
    assert report.reason == "schedule_missing_gametime"


def test_watchdog_falls_back_to_worker_run_next_freeze_when_gametime_missing() -> None:
    report = evaluate_t40_deadline(
        day=DAY,
        games=_games(gametime="", late_gametime=""),
        frozen=None,
        latest_run={
            "status": "waiting",
            "detail_code": "waiting_for_t40",
            "details": {
                "next_freeze": "2026-09-20T16:20:00+00:00",
                "cutoff_at": "2026-09-20T17:00:00+00:00",
            },
        },
        checked_at=datetime(2026, 9, 20, 16, 35, tzinfo=UTC),
        grace_minutes=10,
    )

    assert report.status == "alert"
    assert report.reason == "no_freeze_by_deadline"
    assert report.freeze_due_at == datetime(2026, 9, 20, 16, 20, tzinfo=UTC)

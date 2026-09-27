"""Offline kickoff time-of-day parsing and the T-40-equivalent offline gate (#267)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nfl_oracle.calendar.schedule import (
    ScheduledGame,
    next_offline_slate_day,
    offline_t40_gate,
    parse_schedules_csv,
)

SAMPLE = """season,week,game_id,gameday,gametime,home_team,away_team,game_type
2026,3,2026_03_AAA_BBB,2026-09-20,13:00,AAA,BBB,REG
2026,3,2026_03_CCC_DDD,2026-09-20,20:20,CCC,DDD,REG
2026,4,2026_04_EEE_FFF,2026-09-27,13:00,EEE,FFF,REG
"""

# nflverse gametime is America/New_York local. 13:00 ET in September (EDT,
# UTC-4) is 17:00 UTC; 20:20 ET is 00:20 UTC the next day.
KICKOFF_1300_ET_UTC = datetime(2026, 9, 20, 17, 0, tzinfo=UTC)
KICKOFF_2020_ET_UTC = datetime(2026, 9, 21, 0, 20, tzinfo=UTC)
KICKOFF_NEXT_WEEK_UTC = datetime(2026, 9, 27, 17, 0, tzinfo=UTC)


def test_parse_schedules_csv_computes_kickoff_at_from_gametime() -> None:
    games = parse_schedules_csv(SAMPLE)
    by_id = {g.game_id: g for g in games}
    assert by_id["2026_03_AAA_BBB"].kickoff_at == KICKOFF_1300_ET_UTC
    assert by_id["2026_03_CCC_DDD"].kickoff_at == KICKOFF_2020_ET_UTC


def test_parse_schedules_csv_kickoff_at_none_when_gametime_missing() -> None:
    no_gametime = """season,week,game_id,gameday,home_team,away_team,game_type
2026,3,2026_03_AAA_BBB,2026-09-20,AAA,BBB,REG
"""
    games = parse_schedules_csv(no_gametime)
    assert games[0].kickoff_at is None


def test_parse_schedules_csv_kickoff_at_none_when_gametime_blank_or_malformed() -> None:
    messy = """season,week,game_id,gameday,gametime,home_team,away_team,game_type
2026,3,blank,2026-09-20,,AAA,BBB,REG
2026,3,malformed,2026-09-20,not-a-time,AAA,BBB,REG
2026,3,nogameday,,13:00,AAA,BBB,REG
"""
    games = parse_schedules_csv(messy)
    assert all(g.kickoff_at is None for g in games)


def test_next_offline_slate_day_picks_nearest_upcoming_kickoff() -> None:
    games = parse_schedules_csv(SAMPLE)
    now = KICKOFF_1300_ET_UTC - timedelta(hours=2)
    assert next_offline_slate_day(games, now=now) is not None
    assert next_offline_slate_day(games, now=now).isoformat() == "2026-09-20"


def test_next_offline_slate_day_none_when_nothing_upcoming() -> None:
    games = parse_schedules_csv(SAMPLE)
    after_everything = KICKOFF_NEXT_WEEK_UTC + timedelta(hours=1)
    assert next_offline_slate_day(games, now=after_everything) is None


def test_offline_t40_gate_not_due_well_before_earliest_upcoming_kickoff() -> None:
    games = parse_schedules_csv(SAMPLE)
    now = KICKOFF_1300_ET_UTC - timedelta(hours=3)
    gate = offline_t40_gate(games, now=now)
    assert gate is not None
    assert gate.day.isoformat() == "2026-09-20"
    assert gate.decision.due is False


def test_offline_t40_gate_due_inside_the_t40_window() -> None:
    games = parse_schedules_csv(SAMPLE)
    now = KICKOFF_1300_ET_UTC - timedelta(minutes=10)
    gate = offline_t40_gate(games, now=now)
    assert gate is not None
    assert gate.decision.due is True


def test_offline_t40_gate_gates_on_the_days_earliest_upcoming_kickoff() -> None:
    """Two games the same day: gate must not fire only once the later one is near."""

    games = parse_schedules_csv(SAMPLE)
    # Between the two same-day kickoffs: the 13:00 game has already started,
    # but the day is still gated on 20:20 being the sole upcoming kickoff.
    now = KICKOFF_1300_ET_UTC + timedelta(minutes=30)
    gate = offline_t40_gate(games, now=now)
    assert gate is not None
    assert gate.decision.due is False
    assert gate.decision.target_at == KICKOFF_2020_ET_UTC


def test_offline_t40_gate_none_when_any_game_that_day_lacks_kickoff() -> None:
    """A day with an unpublished gametime for even one game can't be trusted."""

    mixed = """season,week,game_id,gameday,gametime,home_team,away_team,game_type
2026,3,known,2026-09-20,13:00,AAA,BBB,REG
2026,3,unknown,2026-09-20,,CCC,DDD,REG
"""
    games = parse_schedules_csv(mixed)
    now = KICKOFF_1300_ET_UTC - timedelta(hours=3)
    assert offline_t40_gate(games, now=now) is None


def test_offline_t40_gate_none_when_no_games_at_all() -> None:
    assert offline_t40_gate([], now=datetime.now(UTC)) is None


def test_offline_t40_gate_skips_a_fully_passed_day_to_find_the_next_one() -> None:
    games = parse_schedules_csv(SAMPLE)
    just_after_day_one = KICKOFF_2020_ET_UTC + timedelta(hours=4)
    gate = offline_t40_gate(games, now=just_after_day_one)
    assert gate is not None
    assert gate.day.isoformat() == "2026-09-27"
    assert gate.decision.target_at == KICKOFF_NEXT_WEEK_UTC


def test_scheduled_game_kickoff_at_defaults_to_none() -> None:
    game = ScheduledGame(
        season=2026,
        week=3,
        game_id="x",
        gameday=None,
        home_team="AAA",
        away_team="BBB",
    )
    assert game.kickoff_at is None

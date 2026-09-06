"""NFL calendar scaffolding."""

from nfl_oracle.calendar.schedule import ScheduledGame, parse_schedules_csv, weeks_for_season
from nfl_oracle.calendar.season import SeasonWeek, season_week_for_date

__all__ = [
    "ScheduledGame",
    "SeasonWeek",
    "parse_schedules_csv",
    "season_week_for_date",
    "weeks_for_season",
]

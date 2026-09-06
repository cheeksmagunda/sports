"""NFL calendar scaffolding."""

from nfl_oracle.calendar.schedule import (
    NFLVERSE_SCHEDULE_URL,
    ScheduleDensity,
    ScheduledGame,
    catalog_vs_schedule_density,
    games_in_week,
    load_schedules_csv,
    parse_schedules_csv,
    summarize_schedule_density,
    week_for_gameday,
    weeks_for_season,
)
from nfl_oracle.calendar.season import SeasonWeek, season_label_for_date, season_week_for_date

__all__ = [
    "NFLVERSE_SCHEDULE_URL",
    "ScheduledGame",
    "ScheduleDensity",
    "SeasonWeek",
    "catalog_vs_schedule_density",
    "games_in_week",
    "load_schedules_csv",
    "parse_schedules_csv",
    "season_label_for_date",
    "season_week_for_date",
    "summarize_schedule_density",
    "week_for_gameday",
    "weeks_for_season",
]

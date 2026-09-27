"""NHL season labeling.

The NHL regular season and playoffs span two calendar years (roughly October
through June). This labels a date by the calendar year its season *started*
in, matching nfl_oracle.calendar.season's own start-year convention for
internal consistency across sport applications -- this is an internal label
only, not the "2022-23"-style label the league itself uses publicly.
"""

from __future__ import annotations

from datetime import date


def season_label_for_date(day: date) -> int:
    """Season start-year label: July-December belongs to that year's season;
    January-June belongs to the season that started the previous year.
    """

    if day.month < 7:
        return day.year - 1
    return day.year

from __future__ import annotations

from datetime import date

from nhl_oracle.calendar.season import season_label_for_date


def test_season_label_splits_at_july() -> None:
    assert season_label_for_date(date(2022, 11, 17)) == 2022
    assert season_label_for_date(date(2023, 1, 15)) == 2022
    assert season_label_for_date(date(2023, 6, 30)) == 2022
    assert season_label_for_date(date(2023, 7, 1)) == 2023

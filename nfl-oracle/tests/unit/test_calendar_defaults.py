from __future__ import annotations

import json
from datetime import UTC, date, datetime

from nfl_oracle.calendar.season import (
    default_schedule_season_max,
    eastern_today,
    latest_two_seasons,
)
from nfl_oracle.ingest.backfill import tracked_seasons
from nfl_oracle.valuelaw.candidates import live_day_default
from nfl_oracle.valuelaw.model import fit_all


def test_eastern_today_uses_us_eastern_calendar_date() -> None:
    now = datetime(2026, 9, 16, 2, 0, tzinfo=UTC)
    assert eastern_today(now) == date(2026, 9, 15)
    assert live_day_default(now) == date(2026, 9, 15)


def test_default_schedule_season_max_follows_eastern_today() -> None:
    now = datetime(2026, 1, 12, 12, 0, tzinfo=UTC)
    assert default_schedule_season_max(now) == 2025


def test_tracked_seasons_includes_current_calendar_year() -> None:
    now = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
    seasons = tracked_seasons(now)
    assert seasons[0] == 2002
    assert seasons[-1] == 2026


def test_latest_two_seasons_from_rows() -> None:
    rows = (
        {"season": 2023, "position": "QB"},
        {"season": 2024, "position": "QB"},
        {"season": 2025, "position": "QB"},
    )
    assert latest_two_seasons(rows) == (2024, 2025)


def test_fit_all_resolves_latest_two_seasons(tmp_path) -> None:
    dataset = tmp_path / "box.jsonl"
    lines = []
    for season in (2024, 2025):
        for idx in range(12):
            lines.append(
                {
                    "season": season,
                    "position": "QB",
                    "week": 1,
                    "season_type": "regular",
                    "box_value": float(idx),
                    "stat_1": float(idx),
                }
            )
    dataset.write_text("\n".join(json.dumps(row) for row in lines) + "\n", encoding="utf-8")
    bundle = fit_all(dataset)
    model = bundle.models["QB"]
    assert model.train_season == 2024
    assert model.test_season == 2025

"""wnba_game_logs refresh (D102): row mapping + graceful degradation.

Covers the logic the nightly dayclose refresh relies on without touching
nba_api or the DB.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from wnba_oracle.ingest import minutes_backfill as mb


def _fake_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "PLAYER_ID": [1, 2],
            "PLAYER_NAME": ["A'ja Wilson", "Cecília Zandalasini"],
            "TEAM_ABBREVIATION": ["LVA", "PHO"],  # PHO must normalize to PHX
            "GAME_ID": ["1011", "1011"],
            "GAME_DATE": ["2026-06-20T00:00:00", "2026-06-20"],
            "MATCHUP": ["LVA vs. PHX", "PHX @ LVA"],
            "MIN": [31.5, 24.0],
            "PTS": [20, 10], "REB": [8, 3], "OREB": [1, 0], "DREB": [7, 3],
            "AST": [4, 7], "STL": [2, 1], "BLK": [1, 0], "TOV": [3, 2],
            "FGM": [8, 4], "FGA": [15, 9], "FG3M": [1, 1], "FTM": [3, 1], "FTA": [4, 2],
            "season": ["2026", "2026"],
        }
    )


def test_to_rows_maps_schema_and_normalizes() -> None:
    df = mb._to_rows(_fake_frame())
    rows = {r["player_id"]: r for r in df.iter_rows(named=True)}
    a = rows[1]
    assert a["team"] == "LVA" and a["opponent"] == "PHX" and a["home_away"] == "home"
    assert a["first_initial"] == "a" and a["last_name"] == "wilson"
    assert a["min"] == 31.5 and a["pts"] == 20.0
    z = rows[2]
    assert z["team"] == "PHX"  # PHO alias normalized
    assert z["home_away"] == "away" and z["opponent"] == "LVA"
    assert z["last_name"] == "zandalasini"  # accent folded


def test_refresh_upserts_and_returns_count() -> None:
    with patch.object(mb, "_fetch_season_logs", return_value=_fake_frame()), patch.object(
        mb, "_persist", return_value=2
    ) as persist:
        n = mb.refresh_game_logs(["2026"], pause_seconds=0)
    assert n == 2
    persist.assert_called_once()


def test_refresh_degrades_to_zero_on_fetch_failure() -> None:
    """An nba_api outage must not raise -- dayclose calls this best-effort."""
    with patch.object(mb, "_fetch_season_logs", return_value=None):
        assert mb.refresh_game_logs(["2026", "2025"], pause_seconds=0) == 0

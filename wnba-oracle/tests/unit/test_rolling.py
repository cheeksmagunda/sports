"""Rolling-window tests against a synthetic per-player game log."""

from __future__ import annotations

import polars as pl

from wnba_oracle.features.rolling import build_rolling_features, fantasy_pts_expr


def _make_log(pid: int = 100, n: int = 12) -> pl.DataFrame:
    """n synthetic games. Game dates Apr 1, Apr 4, Apr 7 ... (3 days apart)."""
    from datetime import date, timedelta

    dates = [
        (date(2026, 4, 1) + timedelta(days=3 * i)).strftime("%b %d, %Y").upper() for i in range(n)
    ]
    return pl.DataFrame(
        {
            "Player_ID": [pid] * n,
            "Game_ID": [f"00200000{i}" for i in range(n)],
            "GAME_DATE": dates,
            "MATCHUP": ["LVA @ NYL"] * n,
            "WL": ["W"] * n,
            "MIN": [30, 28, 32, 35, 30, 27, 31, 29, 33, 30, 25, 28],
            "PTS": [20, 18, 22, 25, 19, 17, 21, 20, 23, 18, 12, 16],
            "REB": [8, 7, 9, 10, 6, 8, 7, 9, 8, 6, 4, 5],
            "AST": [5, 4, 6, 7, 5, 4, 6, 5, 7, 4, 3, 4],
            "STL": [2, 1, 2, 3, 1, 1, 2, 2, 1, 1, 0, 1],
            "BLK": [1, 0, 1, 1, 1, 0, 1, 0, 2, 1, 0, 0],
            "TOV": [3, 2, 3, 2, 3, 2, 1, 3, 2, 2, 1, 2],
            "FG3M": [2, 1, 2, 3, 2, 1, 2, 1, 3, 1, 0, 2],
            "FG3A": [6, 5, 7, 8, 6, 4, 6, 5, 8, 4, 2, 5],
            "FGA": [16, 14, 17, 19, 15, 13, 16, 15, 18, 14, 9, 12],
            "FTA": [4, 5, 3, 6, 4, 5, 4, 6, 4, 5, 3, 4],
            "PF": [2, 3, 1, 2, 3, 2, 1, 2, 3, 1, 2, 3],
            "PLUS_MINUS": [8, -2, 12, 15, 6, -4, 10, 3, 14, 1, -8, 5],
        }
    )


def test_rolling_left_closed_strict() -> None:
    """A slate_date filter must be strict-less-than (no leakage of the slate game)."""
    log = _make_log()
    # All games are <= May 5, 2026. as_of = 2026-04-15 should only see Apr 1, 4, 7, 10, 13.
    out = build_rolling_features(log, as_of_date="2026-04-15")
    assert len(out) == 1
    row = out.row(0, named=True)
    # 5 games qualify -> mins_l5 average = (30+28+32+35+30)/5 = 31.0
    assert row["mins_l5"] == 31.0


def test_rolling_l10_subset_columns() -> None:
    log = _make_log()
    out = build_rolling_features(log, as_of_date="2026-09-01")
    row = out.row(0, named=True)
    # L10 spans the most-recent 10 of 12 games
    assert "mins_l10" in row
    assert "fantasy_pts_l10" in row
    assert "ts_pct_l10" in row
    assert 0.0 <= row["ts_pct_l10"] <= 1.5
    assert "fg3_pct_l10" in row


def test_empty_log_returns_empty_frame() -> None:
    out = build_rolling_features(pl.DataFrame(), as_of_date="2026-05-26")
    assert out.is_empty()


def test_fantasy_pts_formula_is_real_sports_proxy() -> None:
    """Documented proxy: pts + 1.2*reb + 1.5*ast + 3*stl + 3*blk - tov.
    Doubles as a regression guard on the formula constants."""
    df = pl.DataFrame({"PTS": [10], "REB": [5], "AST": [4], "STL": [1], "BLK": [1], "TOV": [2]})
    val = df.select(fantasy_pts_expr()).to_series().to_list()[0]
    expected = 10 + 1.2 * 5 + 1.5 * 4 + 3 * 1 + 3 * 1 - 1 * 2
    assert val == expected

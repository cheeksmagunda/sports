"""D74: build_opp_dvp_lookup computes per-opponent mean real_score allowed."""

from __future__ import annotations

import polars as pl

from wnba_oracle.features.serving_features import build_opp_dvp_lookup


def _make_logs(rows: list[dict]) -> pl.DataFrame:
    defaults = {
        "min": 20.0,
        "pts": 10.0,
        "reb": 5.0,
        "oreb": 1.0,
        "dreb": 4.0,
        "ast": 3.0,
        "stl": 1.0,
        "blk": 0.5,
        "tov": 1.0,
        "fgm": 4.0,
        "fga": 10.0,
        "fg3m": 1.0,
        "ftm": 1.0,
        "fta": 2.0,
    }
    full = [{**defaults, **r} for r in rows]
    return pl.DataFrame(full)


def test_dvp_lookup_returns_per_opponent_means() -> None:
    logs = _make_logs(
        [
            {"opponent": "LVA", "pts": 20.0},
            {"opponent": "LVA", "pts": 30.0},
            {"opponent": "SEA", "pts": 10.0},
        ]
    )
    result = build_opp_dvp_lookup(logs)
    assert "LVA" in result
    assert "SEA" in result
    assert abs(result["LVA"] - result["SEA"]) > 0.5


def test_dvp_lookup_excludes_dnp_rows() -> None:
    logs = _make_logs(
        [
            {"opponent": "ATL", "min": 0.0, "pts": 100.0},
            {"opponent": "ATL", "min": 25.0, "pts": 5.0},
        ]
    )
    result = build_opp_dvp_lookup(logs)
    # DNP row (min=0) excluded; only the 25-min row should count
    assert "ATL" in result
    assert result["ATL"] < 50.0


def test_dvp_lookup_empty_on_missing_columns() -> None:
    logs = pl.DataFrame({"opponent": ["ATL"], "pts": [10.0]})
    result = build_opp_dvp_lookup(logs)
    assert result == {}


def test_dvp_lookup_empty_on_empty_input() -> None:
    assert build_opp_dvp_lookup(pl.DataFrame()) == {}

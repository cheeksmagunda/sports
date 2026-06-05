"""Feature+target corpus keystone (D63)."""

from __future__ import annotations

import polars as pl

from wnba_oracle.features.corpus import build_gamelog_corpus
from wnba_oracle.features.game_features import (
    TARGET_COLUMNS,
    add_schedule_features,
    add_targets,
)
from wnba_oracle.predict.scoring import box_to_real_score


def _logs() -> pl.DataFrame:
    # Two players, several games, spanning two seasons (lowercase stored schema).
    rows = []
    dates_2025 = ["2025-05-16", "2025-05-19", "2025-05-20", "2025-05-24", "2025-05-27"]
    for i, d in enumerate(dates_2025):
        rows.append(
            {
                "game_date": d, "player_id": 1, "season": "2025",
                "min": 30.0 + i, "pts": 15.0 + i, "reb": 6.0, "oreb": 2.0, "dreb": 4.0,
                "ast": 4.0, "stl": 1.0, "blk": 1.0, "tov": 2.0,
                "fgm": 6.0, "fga": 12.0, "fg3m": 1.0, "ftm": 2.0, "fta": 3.0,
            }
        )
    for i, d in enumerate(["2026-05-10", "2026-05-13"]):
        rows.append(
            {
                "game_date": d, "player_id": 1, "season": "2026",
                "min": 25.0, "pts": 12.0, "reb": 5.0, "oreb": 1.0, "dreb": 4.0,
                "ast": 3.0, "stl": 1.0, "blk": 0.0, "tov": 1.0,
                "fgm": 5.0, "fga": 10.0, "fg3m": 1.0, "ftm": 1.0, "fta": 2.0,
            }
        )
    return pl.from_dicts(rows)


def test_add_targets_real_score_matches_scoring_formula() -> None:
    df = add_targets(_logs())
    row = df.row(0, named=True)
    box = {k: row[k] for k in ("pts", "reb", "oreb", "dreb", "ast", "stl", "blk",
                               "tov", "fgm", "fga", "fg3m", "ftm", "fta")}
    assert abs(row["real_score"] - box_to_real_score(box)) < 1e-9
    assert row["minutes_played"] == row["min"]
    assert abs(row["pts_per_min"] - row["pts"] / row["min"]) < 1e-9
    for t in TARGET_COLUMNS:
        assert t in df.columns


def test_add_targets_per_min_null_on_dnp() -> None:
    logs = _logs().with_columns(pl.when(pl.col("game_date") == "2025-05-16")
                                .then(0.0).otherwise(pl.col("min")).alias("min"))
    df = add_targets(logs).sort("game_date")
    dnp = df.filter(pl.col("game_date") == "2025-05-16").row(0, named=True)
    assert dnp["minutes_played"] == 0.0
    assert dnp["pts_per_min"] is None  # rate undefined when no minutes


def test_schedule_features_reset_across_seasons() -> None:
    df = add_schedule_features(_logs()).sort(["player_id", "game_date"])
    s2026 = df.filter(pl.col("season") == "2026").sort("game_date")
    first = s2026.row(0, named=True)
    # First game of a new season: counter resets to 1, no B2B carried over.
    assert first["season_game_number"] == 1
    assert first["is_back_to_back"] == 0
    second = s2026.row(1, named=True)
    assert second["season_game_number"] == 2
    assert second["days_rest"] == 3.0  # 2026-05-10 -> 2026-05-13


def test_build_gamelog_corpus_is_causal_and_has_targets() -> None:
    corpus = build_gamelog_corpus(_logs())
    # Player 1's first game has no prior games -> dropped (inner join on features).
    # The 2025-05-19 row's mins_l5 must equal the 2025-05-16 minutes only (30.0),
    # i.e. strictly prior games, never including its own game.
    r = corpus.filter(pl.col("game_date") == "2025-05-19").row(0, named=True)
    assert abs(r["mins_l5"] - 30.0) < 1e-9
    assert r["minutes_played"] == 31.0  # this game's own minutes (target)
    assert r["position"] == "F"
    for t in TARGET_COLUMNS:
        assert t in corpus.columns
    # Earliest game (no history) is absent.
    assert corpus.filter(pl.col("game_date") == "2025-05-16").is_empty()

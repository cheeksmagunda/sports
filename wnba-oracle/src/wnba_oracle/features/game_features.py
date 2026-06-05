"""Per-player-game targets + schedule features: the train/serve parity anchor.

Analogous to mlb-oracle ``features/expected_pa.py``. This is the single source of
truth for the per-game quantities both the offline corpus builder
(``features/corpus.py``) and the live serve path compute, so train and serve
agree value-for-value.

Three things live here:

1. ``to_nba_api_schema`` -- rename the stored (lowercase, ISO-date) game-log
   columns to the nba_api names that ``rolling.build_rolling_features`` consumes,
   so the same rolling code runs on both the stored corpus and the live nba_api
   fetch.
2. ``add_targets`` -- the head targets for each played game: ``minutes_played``,
   the four per-minute rates, and ``real_score`` (the locked
   ``predict.scoring.box_to_real_score`` formula, vectorized).
3. ``add_schedule_features`` -- ``days_rest``, ``is_back_to_back``,
   ``season_game_number`` from each player's game-date sequence.
"""

from __future__ import annotations

import polars as pl

from wnba_oracle.predict.scoring import REAL_SCORE_INTERCEPT, REAL_SCORE_WEIGHTS

# Stored game-log (lowercase) -> nba_api column names that
# rolling.build_rolling_features expects. Columns absent upstream
# (FG3A / PLUS_MINUS / PF) stay absent; rolling.py degrades those derived
# features to 0.0 via its `if "COL" in ...` guards.
_STORED_TO_NBA_API: dict[str, str] = {
    "player_id": "Player_ID",
    "game_date": "GAME_DATE",
    "min": "MIN",
    "pts": "PTS",
    "reb": "REB",
    "oreb": "OREB",
    "dreb": "DREB",
    "ast": "AST",
    "stl": "STL",
    "blk": "BLK",
    "tov": "TOV",
    "fgm": "FGM",
    "fga": "FGA",
    "fg3m": "FG3M",
    "ftm": "FTM",
    "fta": "FTA",
}

# The per-game head targets produced by add_targets (keep in sync with
# configs/models.yaml::heads and features/spec.py::HEAD_SPECS targets).
TARGET_COLUMNS: tuple[str, ...] = (
    "minutes_played",
    "pts_per_min",
    "reb_per_min",
    "ast_per_min",
    "stl_blk_per_min",
    "real_score",
)


def to_nba_api_schema(game_logs: pl.DataFrame) -> pl.DataFrame:
    """Rename stored lowercase game-log columns to nba_api names for rolling.py."""
    rename = {k: v for k, v in _STORED_TO_NBA_API.items() if k in game_logs.columns}
    return game_logs.rename(rename)


def real_score_expr() -> pl.Expr:
    """Vectorized ``box_to_real_score`` over the stored (lowercase) schema.

    Mirrors ``predict.scoring.box_to_real_score`` value-for-value (same weights,
    same intercept, floored at 0), so the corpus target equals the live rate
    estimator's notion of real_score.
    """
    total = pl.lit(REAL_SCORE_INTERCEPT, dtype=pl.Float64)
    for stat, w in REAL_SCORE_WEIGHTS.items():
        total = total + pl.col(stat).cast(pl.Float64).fill_null(0.0) * w
    return pl.max_horizontal(total, pl.lit(0.0, dtype=pl.Float64)).alias("real_score")


def add_targets(game_logs: pl.DataFrame) -> pl.DataFrame:
    """Add the per-game head targets (stored lowercase schema).

    ``minutes_played`` and ``real_score`` are defined for every played game. The
    per-minute rates are null when ``min <= 0`` (DNP) so the per-minute heads
    drop those rows; availability (did they play at all) is modeled separately by
    the participation prior, not by these rate heads.
    """
    m = pl.col("min").cast(pl.Float64)
    played = m > 0

    def per_min(num: pl.Expr) -> pl.Expr:
        return pl.when(played).then(num.cast(pl.Float64) / m).otherwise(None)

    return game_logs.with_columns(
        [
            m.alias("minutes_played"),
            per_min(pl.col("pts")).alias("pts_per_min"),
            per_min(pl.col("reb")).alias("reb_per_min"),
            per_min(pl.col("ast")).alias("ast_per_min"),
            per_min(pl.col("stl").cast(pl.Float64) + pl.col("blk").cast(pl.Float64)).alias(
                "stl_blk_per_min"
            ),
            real_score_expr(),
        ]
    )


def add_schedule_features(
    df: pl.DataFrame,
    *,
    date_col: str = "game_date",
    season_col: str = "season",
    player_col: str = "player_id",
) -> pl.DataFrame:
    """Add ``days_rest``, ``is_back_to_back``, ``season_game_number``.

    Computed from each player's game-date sequence within a season (B2B and the
    game counter reset across seasons). ``days_rest`` for a player's first game of
    a season is filled with a large neutral value (99) so it never reads as a B2B.
    """
    gd = pl.col(date_col).str.to_date("%Y-%m-%d", strict=False)
    out = df.with_columns(gd.alias("_gd")).sort([player_col, "_gd"])
    prev = pl.col("_gd").shift(1).over([player_col, season_col])
    out = out.with_columns(
        [
            (pl.col("_gd") - prev).dt.total_days().alias("_days_rest_raw"),
            pl.col("_gd").cum_count().over([player_col, season_col]).alias("season_game_number"),
        ]
    )
    out = out.with_columns(
        [
            pl.col("_days_rest_raw").fill_null(99).cast(pl.Float64).alias("days_rest"),
            (pl.col("_days_rest_raw").fill_null(99) <= 1).cast(pl.Int8).alias("is_back_to_back"),
            pl.col("season_game_number").cast(pl.Int64),
        ]
    )
    return out.drop(["_gd", "_days_rest_raw"])

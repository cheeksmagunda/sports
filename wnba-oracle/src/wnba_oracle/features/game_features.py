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

from typing import Final

import polars as pl

from wnba_oracle.predict.scoring import REAL_SCORE_INTERCEPT, REAL_SCORE_WEIGHTS

# Real Sports full team name -> game-log-corpus abbreviation. Explicit
# entries win; anything unmapped falls back to name[:3].upper() (verified
# against fixtures to match the Real Sports key for current franchises).
WNBA_TEAM_NAME_TO_KEY: Final[dict[str, str]] = {
    "Las Vegas Aces": "LVA",
    "New York Liberty": "NYL",
    "Phoenix Mercury": "PHO",
    "Chicago Sky": "CHI",
    "Toronto Tempo": "TOR",
    "Minnesota Lynx": "MIN",
    "Atlanta Dream": "ATL",
    "Indiana Fever": "IND",
    "Connecticut Sun": "CON",
    "Dallas Wings": "DAL",
    "Los Angeles Sparks": "LAS",
    "Seattle Storm": "SEA",
    "Washington Mystics": "WAS",
    "Golden State Valkyries": "GSV",
    "Portland Fire": "POR",
}


def team_key_from_full_name(name: str) -> str:
    if name in WNBA_TEAM_NAME_TO_KEY:
        return WNBA_TEAM_NAME_TO_KEY[name]
    return name[:3].upper()


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
# train/models.yaml::heads and features/spec.py::HEAD_SPECS targets).
# real_score_per_min is the validated rate term (predict/minutes.py): the
# serve-time recompose is E[real_score] = E[minutes] x E[real_score_per_min].
TARGET_COLUMNS: tuple[str, ...] = (
    "minutes_played",
    "real_score_per_min",
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


def _real_score_unaliased() -> pl.Expr:
    """Vectorized ``box_to_real_score`` (no alias), for reuse in derived columns."""
    total = pl.lit(REAL_SCORE_INTERCEPT, dtype=pl.Float64)
    for stat, w in REAL_SCORE_WEIGHTS.items():
        total = total + pl.col(stat).cast(pl.Float64).fill_null(0.0) * w
    return pl.max_horizontal(total, pl.lit(0.0, dtype=pl.Float64))


def real_score_expr() -> pl.Expr:
    """Vectorized ``box_to_real_score`` over the stored (lowercase) schema.

    Mirrors ``predict.scoring.box_to_real_score`` value-for-value (same weights,
    same intercept, floored at 0), so the corpus target equals the live rate
    estimator's notion of real_score.
    """
    return _real_score_unaliased().alias("real_score")


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

    rs = _real_score_unaliased()
    return game_logs.with_columns(
        [
            m.alias("minutes_played"),
            pl.when(played).then(rs / m).otherwise(None).alias("real_score_per_min"),
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


def compute_season_game_number(
    game_logs: pl.DataFrame,
    *,
    date_col: str = "game_date",
    season_col: str = "season",
    player_col: str = "player_id",
) -> pl.DataFrame:
    """Return the true chronological season game number for each game-log row."""
    if game_logs.is_empty():
        return pl.DataFrame()

    out = (
        game_logs.select([player_col, season_col, date_col])
        .unique()
        .sort([player_col, season_col, date_col])
    )
    out = out.with_columns(
        pl.col(date_col).cum_count().over([player_col, season_col]).alias("season_game_number")
    )
    return out.with_columns(pl.col("season_game_number").cast(pl.Int64))


def compute_opp_dvp_map(game_logs: pl.DataFrame) -> dict[str, float]:
    """Per-opponent mean real_score allowed (season-wide), from game_logs.

    Filters to games where the player logged >= 5 min to exclude DNP/garbage.
    Shared by the offline corpus enrichment (features/corpus.py) and the
    live serve-time lookup (features/serving_features.py) so the two DvP
    computations can't drift apart.
    """
    if game_logs.is_empty():
        return {}
    needed = [*REAL_SCORE_WEIGHTS, "opponent", "min"]
    if not all(c in game_logs.columns for c in needed):
        return {}
    score_expr = pl.lit(float(REAL_SCORE_INTERCEPT))
    for stat, w in REAL_SCORE_WEIGHTS.items():
        score_expr = score_expr + pl.lit(w) * pl.col(stat).fill_null(0.0)
    grouped = (
        game_logs.filter(pl.col("min").fill_null(0.0) >= 5.0)
        .with_columns(score_expr.alias("_est_rs"))
        .group_by("opponent")
        .agg(pl.col("_est_rs").mean().alias("mean_allowed"))
        .filter(pl.col("opponent").is_not_null() & (pl.col("opponent") != ""))
    )
    return {row["opponent"]: float(row["mean_allowed"]) for row in grouped.to_dicts()}


def compute_team_pace_map(game_logs: pl.DataFrame) -> dict[str, float]:
    """Per-team mean possessions per 40 minutes (WNBA pace), from game_logs.

    Computes pace from box-score possession estimate: POSS ≈ FGA - OREB + TOV + 0.44*FTA.
    Aggregates per (game_date, team) then computes pace = 40 * total_poss / (total_min / 5).
    Returns mean pace per team over all games, with league-mean shrinkage toward early-
    season fallback (3-game pseudo-count to stabilize estimates from sparse data).

    Shared by the offline corpus enrichment (features/corpus.py) and the
    live serve-time lookup (features/serving_features.py) so the two pace
    computations can't drift apart. Called with filtered game_logs (e.g. games
    strictly before a date) by the caller to achieve point-in-time causality.
    """
    if game_logs.is_empty():
        return {}
    needed = ["game_date", "team", "fga", "oreb", "tov", "fta", "min"]
    if not all(c in game_logs.columns for c in needed):
        return {}

    # Compute possessions per player-game using box-score estimate.
    # POSS ≈ FGA - OREB + TOV + 0.44*FTA (standard NBA/WNBA formula).
    df = game_logs.with_columns(
        (
            pl.col("fga")
            - pl.col("oreb").fill_null(0.0)
            + pl.col("tov").fill_null(0.0)
            + 0.44 * pl.col("fta").fill_null(0.0)
        ).alias("_poss")
    )

    # Aggregate to (game_date, team) level: sum possessions and minutes.
    # WNBA regulation game is 40 minutes (5 players on court).
    game_level = (
        df.group_by(["game_date", "team"])
        .agg(
            [
                pl.col("_poss").sum().alias("_poss_sum"),
                pl.col("min").sum().alias("_min_sum"),
            ]
        )
        .filter(pl.col("_min_sum") > 0.0)
        .with_columns((40.0 * pl.col("_poss_sum") / (pl.col("_min_sum") / 5.0)).alias("_game_pace"))
    )

    if game_level.is_empty():
        return {}

    # Compute team pace as mean over games, with league-mean shrinkage.
    team_paces = (
        game_level.group_by("team")
        .agg(
            [
                pl.col("_game_pace").mean().alias("team_pace"),
                pl.col("_game_pace").count().alias("n_games"),
            ]
        )
        .filter(pl.col("team").is_not_null() & (pl.col("team") != ""))
    )

    if team_paces.is_empty():
        return {}

    league_mean = float(team_paces.get_column("team_pace").mean())
    k = 3.0  # Pseudo-count for shrinkage (3 games equivalent)

    result: dict[str, float] = {}
    for row in team_paces.to_dicts():
        team = str(row["team"]).upper()
        pace = float(row["team_pace"])
        n_games = int(row["n_games"])
        # Shrink toward league mean: pace_shrunk = (n_games * pace + k * league_mean) / (n_games + k)
        shrunk_pace = (n_games * pace + k * league_mean) / (n_games + k)
        result[team] = shrunk_pace

    return result

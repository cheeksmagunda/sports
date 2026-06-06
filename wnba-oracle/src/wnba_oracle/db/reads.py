"""Canonical Postgres read helpers for training, backtest, and analysis scripts.

Every function returns a polars DataFrame (or a dict for aggregated lookups).
Call .to_pandas() at the call site when the consumer needs pandas. All accept
an optional engine parameter for custom connections; default to get_engine()
which reads DATABASE_URL.
"""
from __future__ import annotations

import polars as pl
import sqlalchemy as sa
from sqlalchemy import text

from wnba_oracle.db.engine import get_engine


def read_training_corpus(engine: sa.Engine | None = None) -> pl.DataFrame:
    """Training corpus assembled from slate_labels (replaces training_corpus.parquet)."""
    eng = engine or get_engine()
    q = text(
        "SELECT slate_date, platform_player_id AS player_id, display_name, "
        "team_key AS team, card_boost, real_score, 'F' AS position "
        "FROM slate_labels WHERE real_score IS NOT NULL ORDER BY slate_date"
    )
    with eng.connect() as conn:
        rows = conn.execute(q).fetchall()
    if not rows:
        return pl.DataFrame(schema={
            "slate_date": pl.Utf8, "player_id": pl.Int64, "display_name": pl.Utf8,
            "team": pl.Utf8, "card_boost": pl.Float64, "real_score": pl.Float64,
            "position": pl.Utf8,
        })
    return pl.from_dicts([dict(r._mapping) for r in rows])


def read_slate_labels(engine: sa.Engine | None = None) -> pl.DataFrame:
    """All slate_labels rows (replaces data/historical/slate_labels/**/data.parquet)."""
    eng = engine or get_engine()
    q = text(
        "SELECT contest_id, slate_date, section, platform_player_id, display_name, "
        "team_key, card_boost, drafts, real_score "
        "FROM slate_labels ORDER BY slate_date, platform_player_id"
    )
    with eng.connect() as conn:
        rows = conn.execute(q).fetchall()
    if not rows:
        return pl.DataFrame(schema={
            "contest_id": pl.Int64, "slate_date": pl.Utf8,
            "section": pl.Utf8, "platform_player_id": pl.Int64,
            "display_name": pl.Utf8, "team_key": pl.Utf8,
            "card_boost": pl.Float64, "drafts": pl.Int64,
            "real_score": pl.Float64,
        })
    return pl.from_dicts([dict(r._mapping) for r in rows])


def read_leaderboards(engine: sa.Engine | None = None) -> pl.DataFrame:
    """Contest leaderboards (replaces data/historical/leaderboards/**/data.parquet).

    Returns lineup as a JSON string column named lineup_json for backward
    compatibility with scripts that call json.loads(row["lineup_json"]).
    """
    eng = engine or get_engine()
    q = text(
        "SELECT contest_id, slate_date, entry_id, rank, paged_rank, "
        "user_id, score, lineup::text AS lineup_json, num_brawlers "
        "FROM contest_leaderboards ORDER BY slate_date, rank"
    )
    with eng.connect() as conn:
        rows = conn.execute(q).fetchall()
    if not rows:
        return pl.DataFrame(schema={
            "contest_id": pl.Int64, "slate_date": pl.Utf8,
            "entry_id": pl.Int64, "rank": pl.Int64,
            "paged_rank": pl.Int64, "user_id": pl.Utf8,
            "score": pl.Float64, "lineup_json": pl.Utf8,
            "num_brawlers": pl.Int64,
        })
    return pl.from_dicts([dict(r._mapping) for r in rows])


def read_game_logs(engine: sa.Engine | None = None) -> pl.DataFrame:
    """WNBA per-game box scores (replaces wnba_game_logs.parquet)."""
    eng = engine or get_engine()
    q = text(
        "SELECT game_date, player_id, player_name, first_initial, last_name, "
        "team, opponent, home_away, game_id, min, season, "
        "pts, reb, oreb, dreb, ast, stl, blk, tov, "
        "fgm, fga, fg3m, ftm, fta "
        "FROM wnba_game_logs ORDER BY game_date, player_id"
    )
    with eng.connect() as conn:
        rows = conn.execute(q).fetchall()
    if not rows:
        return pl.DataFrame(schema={
            "game_date": pl.Utf8, "player_id": pl.Int64,
            "player_name": pl.Utf8, "first_initial": pl.Utf8,
            "last_name": pl.Utf8, "team": pl.Utf8,
            "opponent": pl.Utf8, "home_away": pl.Utf8,
            "game_id": pl.Utf8,
            "min": pl.Float64, "season": pl.Utf8,
            "pts": pl.Float64, "reb": pl.Float64,
            "oreb": pl.Float64, "dreb": pl.Float64,
            "ast": pl.Float64, "stl": pl.Float64,
            "blk": pl.Float64, "tov": pl.Float64,
            "fgm": pl.Float64, "fga": pl.Float64,
            "fg3m": pl.Float64, "ftm": pl.Float64,
            "fta": pl.Float64,
        })
    return pl.from_dicts([dict(r._mapping) for r in rows])


def read_player_history(engine: sa.Engine | None = None) -> dict[int, float]:
    """Per-player mean real_score from slate_labels (replaces job2._load_player_history)."""
    eng = engine or get_engine()
    q = text(
        "SELECT platform_player_id, AVG(real_score) AS mean_real_score "
        "FROM slate_labels WHERE real_score IS NOT NULL "
        "GROUP BY platform_player_id"
    )
    with eng.connect() as conn:
        rows = conn.execute(q).fetchall()
    return {int(r._mapping["platform_player_id"]): float(r._mapping["mean_real_score"]) for r in rows}

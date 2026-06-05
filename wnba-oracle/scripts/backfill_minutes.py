"""Backfill WNBA per-game minutes + box lines from stats.wnba.com (nba_api).

This is the data foundation for the minutes/role model (D54): the corpus has
realized real_score + card_boost but NO minutes, and minutes is the one signal
orthogonal to the boost. One PlayerGameLogs call per season returns the entire
league's per-game box scores with precise MIN, dated, with team abbreviations
that match the corpus team_key.

Writes to Postgres (wnba_game_logs table):
  game_date (YYYY-MM-DD), player_id, player_name, first_initial, last_name,
  team, min, pts, reb, ast, stl, blk, tov, season

Run: uv run python scripts/backfill_minutes.py
"""
from __future__ import annotations

import sys
import time
import unicodedata
from pathlib import Path

import polars as pl
from nba_api.stats.endpoints import playergamelogs
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wnba_oracle.db.engine import get_engine  # noqa: E402

SEASONS = ["2024", "2025", "2026"]
COLS = ["PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION", "GAME_DATE",
        "MIN", "PTS", "REB", "OREB", "DREB", "AST", "STL", "BLK", "TOV",
        "FGM", "FGA", "FG3M", "FTM", "FTA"]

UPSERT_SQL = text(
    """
    INSERT INTO wnba_game_logs (
        game_date, player_id, player_name, first_initial, last_name,
        team, min, season, pts, reb, oreb, dreb, ast, stl, blk, tov,
        fgm, fga, fg3m, ftm, fta, ingested_at
    ) VALUES (
        :game_date, :player_id, :player_name, :first_initial, :last_name,
        :team, :min, :season, :pts, :reb, :oreb, :dreb, :ast, :stl, :blk, :tov,
        :fgm, :fga, :fg3m, :ftm, :fta, now()
    )
    ON CONFLICT (game_date, player_id) DO UPDATE SET
        player_name = EXCLUDED.player_name,
        first_initial = EXCLUDED.first_initial,
        last_name = EXCLUDED.last_name,
        team = EXCLUDED.team,
        min = EXCLUDED.min,
        pts = EXCLUDED.pts, reb = EXCLUDED.reb, oreb = EXCLUDED.oreb,
        dreb = EXCLUDED.dreb, ast = EXCLUDED.ast, stl = EXCLUDED.stl,
        blk = EXCLUDED.blk, tov = EXCLUDED.tov,
        fgm = EXCLUDED.fgm, fga = EXCLUDED.fga, fg3m = EXCLUDED.fg3m,
        ftm = EXCLUDED.ftm, fta = EXCLUDED.fta,
        ingested_at = now();
    """
)

STAT_COLS = ("pts", "reb", "oreb", "dreb", "ast", "stl", "blk", "tov",
             "fgm", "fga", "fg3m", "ftm", "fta")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return s.strip().lower()


def _persist_to_postgres(df: pl.DataFrame) -> int:
    engine = get_engine()
    n = 0
    with engine.begin() as conn:
        for row in df.iter_rows(named=True):
            conn.execute(UPSERT_SQL, row)
            n += 1
    return n


def main() -> None:
    frames = []
    for season in SEASONS:
        try:
            df = playergamelogs.PlayerGameLogs(
                season_nullable=season, league_id_nullable="10"
            ).get_data_frames()[0]
        except Exception as e:
            print(f"season {season}: ERROR {type(e).__name__} {str(e)[:80]} (skipping)")
            continue
        if df.empty:
            print(f"season {season}: no rows")
            continue
        df = df[[c for c in COLS if c in df.columns]].copy()
        df["season"] = season
        frames.append(df)
        print(f"season {season}: {len(df)} player-games, "
              f"{df['GAME_DATE'].min()[:10]} .. {df['GAME_DATE'].max()[:10]}")
        time.sleep(0.6)
    if not frames:
        raise SystemExit("no game logs fetched")

    import pandas as pd
    raw = pd.concat(frames, ignore_index=True)
    cols = {
        "game_date": [str(d)[:10] for d in raw["GAME_DATE"]],
        "player_id": raw["PLAYER_ID"].astype(int),
        "player_name": raw["PLAYER_NAME"].astype(str),
        "first_initial": [(_norm(n)[:1] if n else "") for n in raw["PLAYER_NAME"]],
        "last_name": [_norm(str(n).split()[-1]) if str(n).strip() else "" for n in raw["PLAYER_NAME"]],
        "team": raw["TEAM_ABBREVIATION"].astype(str),
        "min": raw["MIN"].astype(float),
        "season": raw["season"].astype(str),
    }
    for stat in ("PTS", "REB", "OREB", "DREB", "AST", "STL", "BLK", "TOV", "FGM", "FGA", "FG3M", "FTM", "FTA"):
        cols[stat.lower()] = raw[stat].astype(float) if stat in raw else 0.0
    out = pl.DataFrame(cols)
    n = _persist_to_postgres(out)
    print(f"\nupserted {n} rows to Postgres wnba_game_logs, "
          f"{out['player_id'].n_unique()} players, "
          f"teams={sorted(out['team'].unique().to_list())}")


if __name__ == "__main__":
    main()

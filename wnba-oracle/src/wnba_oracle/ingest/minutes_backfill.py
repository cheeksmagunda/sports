"""Refresh wnba_game_logs from stats.wnba.com (nba_api).

wnba_game_logs is BOTH the head-training corpus AND the live Tier-0 head-feature
source. Before D102 its only writer was the manual scripts/backfill_minutes.py,
so the rolling windows silently went stale whenever the operator stopped running
it -- the root cause of the D99 C. Leite staleness (head_features frozen at an
old snapshot; a debuting player got no head_features at all). This module holds
the reusable fetch+parse+upsert so the nightly dayclose cron can keep the
current season fresh, and the backfill script can reload all seasons.
"""

from __future__ import annotations

import time
import unicodedata

import polars as pl
from sqlalchemy import text

from wnba_oracle.common.logging import get_logger
from wnba_oracle.db.engine import get_engine

log = get_logger("oracle.ingest.minutes_backfill")

COLS = [
    "PLAYER_ID",
    "PLAYER_NAME",
    "TEAM_ABBREVIATION",
    "GAME_ID",
    "GAME_DATE",
    "MATCHUP",
    "MIN",
    "PTS",
    "REB",
    "OREB",
    "DREB",
    "AST",
    "STL",
    "BLK",
    "TOV",
    "FGM",
    "FGA",
    "FG3M",
    "FTM",
    "FTA",
]

# Phoenix changed abbreviation from PHO (2024) to PHX (2025+). Same franchise;
# unify so cross-season joins work.
TEAM_ALIASES = {"PHO": "PHX"}


def _normalize_team(t: str | None) -> str:
    if not t or str(t).lower() == "nan":
        return ""
    s = str(t).strip().upper()
    return TEAM_ALIASES.get(s, s)


def _parse_matchup(matchup: str | None) -> tuple[str, str]:
    """nba_api MATCHUP is ``TEAM vs. OPP`` (home) or ``TEAM @ OPP`` (away)."""
    if not matchup:
        return "", ""
    s = str(matchup)
    if " vs. " in s:
        return _normalize_team(s.split(" vs. ", 1)[1]), "home"
    if " @ " in s:
        return _normalize_team(s.split(" @ ", 1)[1]), "away"
    return "", ""


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return s.strip().lower()


UPSERT_SQL = text(
    """
    INSERT INTO wnba_game_logs (
        game_date, player_id, player_name, first_initial, last_name,
        team, opponent, home_away, game_id, min, season,
        pts, reb, oreb, dreb, ast, stl, blk, tov,
        fgm, fga, fg3m, ftm, fta, ingested_at
    ) VALUES (
        :game_date, :player_id, :player_name, :first_initial, :last_name,
        :team, :opponent, :home_away, :game_id, :min, :season,
        :pts, :reb, :oreb, :dreb, :ast, :stl, :blk, :tov,
        :fgm, :fga, :fg3m, :ftm, :fta, now()
    )
    ON CONFLICT (game_date, player_id) DO UPDATE SET
        player_name = EXCLUDED.player_name,
        first_initial = EXCLUDED.first_initial,
        last_name = EXCLUDED.last_name,
        team = EXCLUDED.team,
        opponent = EXCLUDED.opponent,
        home_away = EXCLUDED.home_away,
        game_id = EXCLUDED.game_id,
        min = EXCLUDED.min,
        pts = EXCLUDED.pts, reb = EXCLUDED.reb, oreb = EXCLUDED.oreb,
        dreb = EXCLUDED.dreb, ast = EXCLUDED.ast, stl = EXCLUDED.stl,
        blk = EXCLUDED.blk, tov = EXCLUDED.tov,
        fgm = EXCLUDED.fgm, fga = EXCLUDED.fga, fg3m = EXCLUDED.fg3m,
        ftm = EXCLUDED.ftm, fta = EXCLUDED.fta,
        ingested_at = now();
    """
)


def _fetch_season_logs(season: str):
    """One PlayerGameLogs call for a WNBA season (league_id 10). Returns a
    pandas DataFrame, or None on any nba_api failure (caller degrades)."""
    from nba_api.stats.endpoints import playergamelogs

    try:
        df = playergamelogs.PlayerGameLogs(
            season_nullable=season, league_id_nullable="10"
        ).get_data_frames()[0]
    except Exception as exc:
        log.warning("game_logs_fetch_failed", season=season, error=str(exc)[:120])
        return None
    return df


def _to_rows(raw) -> pl.DataFrame:
    """Map an nba_api PlayerGameLogs frame (with a `season` column) to the
    wnba_game_logs row schema."""
    parsed = (
        [_parse_matchup(m) for m in raw["MATCHUP"]] if "MATCHUP" in raw else [("", "")] * len(raw)
    )
    game_ids = (
        [str(g) if g is not None and str(g).lower() != "nan" else "" for g in raw["GAME_ID"]]
        if "GAME_ID" in raw
        else [""] * len(raw)
    )
    cols = {
        "game_date": [str(d)[:10] for d in raw["GAME_DATE"]],
        "player_id": raw["PLAYER_ID"].astype(int),
        "player_name": raw["PLAYER_NAME"].astype(str),
        "first_initial": [(_norm(n)[:1] if n else "") for n in raw["PLAYER_NAME"]],
        "last_name": [
            _norm(str(n).split()[-1]) if str(n).strip() else "" for n in raw["PLAYER_NAME"]
        ],
        "team": [_normalize_team(t) for t in raw["TEAM_ABBREVIATION"]],
        "opponent": [op for op, _ in parsed],
        "home_away": [ha for _, ha in parsed],
        "game_id": game_ids,
        "min": raw["MIN"].astype(float),
        "season": raw["season"].astype(str),
    }
    for stat in (
        "PTS",
        "REB",
        "OREB",
        "DREB",
        "AST",
        "STL",
        "BLK",
        "TOV",
        "FGM",
        "FGA",
        "FG3M",
        "FTM",
        "FTA",
    ):
        cols[stat.lower()] = raw[stat].astype(float) if stat in raw else 0.0
    return pl.DataFrame(cols)


def _persist(df: pl.DataFrame) -> int:
    engine = get_engine()
    n = 0
    with engine.begin() as conn:
        for row in df.iter_rows(named=True):
            conn.execute(UPSERT_SQL, row)
            n += 1
    return n


def refresh_game_logs(seasons: list[str], *, pause_seconds: float = 0.6) -> int:
    """Fetch + upsert wnba_game_logs for the given seasons. Returns rows written.

    Per-season failures are logged and skipped (partial refresh beats none).
    The UPSERT is idempotent on (game_date, player_id), so re-running is safe.
    """
    import pandas as pd

    frames = []
    for season in seasons:
        df = _fetch_season_logs(season)
        if df is None or df.empty:
            continue
        df = df[[c for c in COLS if c in df.columns]].copy()
        df["season"] = season
        frames.append(df)
        log.info("game_logs_season_fetched", season=season, rows=len(df))
        time.sleep(pause_seconds)
    if not frames:
        log.warning("game_logs_refresh_empty", seasons=seasons)
        return 0
    raw = pd.concat(frames, ignore_index=True)
    n = _persist(_to_rows(raw))
    log.info("game_logs_refreshed", rows=n, seasons=seasons)
    return n

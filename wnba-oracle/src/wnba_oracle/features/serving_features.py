"""Build head feature rows for a slate at serve time (D69 / Phase 2b).

Mirrors the offline corpus pipeline (features/corpus.build_gamelog_corpus): same
rolling features (rolling.build_rolling_features) and same schedule features
(days_rest, is_back_to_back, season_game_number), but evaluated AS-OF the slate
date for a player whose next game has not yet been played. Output is a lookup
keyed by (first_initial, last_name, team) -- the same key scheme that
ingest.minutes_features uses to match Real Sports pool players to nba_api
game logs.

The dict written into features_json under `head_features` is consumed by
job2 when ``WNBA_SERVE_PRIMARY=heads`` (LightGBM Tier-0) and by the EB path
for pace terms. Job 1 also fuses slate enrichment (card_boost, vegas_*,
is_home, starter flags) into that dict so those signals enter the design
matrix rather than living only at the features_json top level (#523).
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

import polars as pl

from wnba_oracle.common.logging import get_logger
from wnba_oracle.features.game_features import (
    compute_opp_dvp_map,
    compute_team_pace_map,
    to_nba_api_schema,
)
from wnba_oracle.features.rolling import build_rolling_features

log = get_logger("oracle.features.serving")

FeatureLookupKey = tuple[str, str, str] | int

# Slate enrichment keys that belong in the own-model design matrix
# (``_BASE_FEATURES`` / EB serve path). Previously top-level only.
SLATE_ENRICHMENT_HEAD_KEYS: tuple[str, ...] = (
    "card_boost",
    "primary_ranking",
    "vegas_total",
    "vegas_spread",
    "is_home",
    "is_starter",
    "starter_slot",
    "is_confirmed_starter",
)


def fuse_slate_enrichment_into_head_features(
    head: Mapping[str, Any] | None,
    *,
    card_boost: float,
    primary_ranking: float,
    vegas_total: float,
    vegas_spread: float,
    is_home: float,
    is_starter: int,
    starter_slot: int,
    rotowire_confirmed: int,
) -> dict[str, float]:
    """Merge live slate enrichment into a head_features row (#523).

    Always returns a dict (creates one when rolling features missed) so
    boost / Vegas / home / starter enter the model path even on cold-start
    identity misses. ``is_confirmed_starter`` matches the train corpus name
    in ``_BASE_FEATURES`` (confirmed starter, not merely expected).
    """

    out: dict[str, float] = {}
    if isinstance(head, Mapping):
        for key, value in head.items():
            if value is None:
                out[str(key)] = 0.0
                continue
            try:
                out[str(key)] = float(value)
            except (TypeError, ValueError):
                out[str(key)] = 0.0
    out["card_boost"] = float(card_boost)
    out["primary_ranking"] = float(primary_ranking)
    out["vegas_total"] = float(vegas_total)
    out["vegas_spread"] = float(vegas_spread)
    out["is_home"] = float(is_home)
    out["is_starter"] = float(is_starter)
    out["starter_slot"] = float(starter_slot)
    out["is_confirmed_starter"] = float(
        1.0 if int(rotowire_confirmed) and int(is_starter) else 0.0
    )
    return out


def _norm(s: str | None) -> str:
    return (
        unicodedata.normalize("NFKD", str(s or ""))
        .encode("ascii", "ignore")
        .decode()
        .lower()
        .strip()
    )


def _key(name: str | None, team: str | None) -> tuple[str, str, str] | None:
    n = _norm(name)
    if not n:
        return None
    parts = n.split()
    last = parts[-1] if parts else ""
    if not last:
        return None
    return (n[:1], last, str(team or "").upper())


def _parse_iso(d: str | None) -> date | None:
    if not d:
        return None
    try:
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _schedule_for_player(
    games: pl.DataFrame | None, slate_date: date, season: int
) -> tuple[float, int, int]:
    """Compute (days_rest, is_back_to_back, season_game_number) AS-OF slate_date.

    `games` is the player's game log (lowercase stored schema). Only games in
    `season` strictly before `slate_date` count. days_rest defaults to 99 (same
    neutral value features/game_features.add_schedule_features uses for a
    season's first game) so a player with no prior games never reads as B2B.
    """
    if games is None or games.is_empty():
        return 99.0, 0, 1
    # season may be stored as int or string; coerce both sides to string for the compare.
    season_str = str(season)
    season_prior = games.filter(
        (pl.col("season").cast(pl.String) == season_str)
        & (pl.col("game_date") < slate_date.isoformat())
    )
    n_prior = season_prior.height
    if n_prior == 0:
        return 99.0, 0, 1
    last_iso = season_prior.get_column("game_date").max()
    last = _parse_iso(str(last_iso) if last_iso is not None else None)
    if last is None:
        return 99.0, 0, n_prior + 1
    delta = (slate_date - last).days
    return float(max(delta, 0)), int(delta <= 1), n_prior + 1


def build_head_feature_lookup(
    game_logs: pl.DataFrame,
    *,
    slate_date: str,
    required_columns: tuple[str, ...] | None = None,
) -> dict[tuple[str, str, str] | int, dict[str, float]]:
    """Build {(initial, last, team): {col: value}} for every player with prior games.

    Steps mirror features/corpus.build_gamelog_corpus:
      1. Rename to nba_api schema and run build_rolling_features as-of slate_date.
      2. Per-player schedule features (days_rest, is_back_to_back, season_game_number)
         computed against the stored frame.
      3. Filter to players with at least an L5 minutes window (same guardrail the
         corpus uses).

    `required_columns` lets the caller drop any feature the trained artifact's
    heads do not consume (smaller features_json, fewer bytes per slate).
    """
    if game_logs.is_empty():
        return {}

    sd = _parse_iso(slate_date)
    if sd is None:
        log.warning("serving_features_bad_slate_date", slate_date=slate_date)
        return {}
    season = sd.year

    adapted = to_nba_api_schema(game_logs)
    rolling = build_rolling_features(adapted, as_of_date=slate_date)
    if rolling.is_empty():
        return {}

    rolling = rolling.filter(pl.col("mins_l5").is_not_null())
    if rolling.is_empty():
        return {}

    # Per-player identity for the key + group lookup.
    ident = (
        game_logs.select(["player_id", "player_name", "team"])
        .unique(subset=["player_id"], keep="last")
        .to_dicts()
    )
    ident_by_pid: dict[int, dict] = {}
    for row in ident:
        pid = row.get("player_id")
        if pid is None:
            continue
        ident_by_pid[int(pid)] = row

    # Group game logs by player_id once so per-player schedule computation is O(n).
    # polars group_by iter yields (key_tuple, frame); the key is a 1-tuple for one column.
    games_by_pid: dict[int, pl.DataFrame] = {}
    for key, grp in game_logs.group_by("player_id"):
        pid_val = key[0] if isinstance(key, tuple) else key
        if pid_val is None:
            continue
        games_by_pid[int(pid_val)] = grp

    out: dict[FeatureLookupKey, dict[str, float]] = {}
    rolling_dicts = rolling.to_dicts()
    for row in rolling_dicts:
        pid_raw = row.get("player_id")
        if pid_raw is None:
            continue
        pid = int(pid_raw)
        who = ident_by_pid.get(pid)
        if not who:
            continue
        name = str(who.get("player_name", "") or "")
        team = str(who.get("team", "") or "")
        jkey = _key(name, team)
        if jkey is None:
            continue

        # Skip identity column so it does not leak into features_json.
        feats = {k: v for k, v in row.items() if k != "player_id"}

        days_rest, is_b2b, gn = _schedule_for_player(games_by_pid.get(pid), sd, season)
        feats["days_rest"] = days_rest
        feats["is_back_to_back"] = is_b2b
        feats["season_game_number"] = gn

        # Coerce nulls/None to 0.0 so LightGBM does not see NaN for required cols.
        coerced: dict[str, float] = {}
        for k, v in feats.items():
            if v is None:
                coerced[k] = 0.0
                continue
            try:
                coerced[k] = float(v)
            except (TypeError, ValueError):
                coerced[k] = 0.0

        if required_columns is not None:
            coerced = {k: coerced.get(k, 0.0) for k in required_columns}

        out[jkey] = coerced
        # D107 (#29): also index by nba_api player_id so Resolver-based lookups
        # (via nbaId trust + override CSV) can find head features by player_id
        # instead of fragile name-string matching. Resolver returns int player_id.
        out[pid] = coerced
        # Team-agnostic fallback (mirrors ingest.minutes_features.lookup behaviour).
        fallback = (jkey[0], jkey[1], "")
        if fallback not in out:
            out[fallback] = coerced

    log.info(
        "serving_head_features_built",
        slate_date=slate_date,
        n_players=len(out),
    )
    return out


def lookup(
    feats: dict[FeatureLookupKey, dict[str, float]],
    *,
    display_name: str,
    team: str,
) -> dict[str, float] | None:
    """Match a Real Sports pool player to their head feature row. Matches
    minutes_features.lookup so train and serve agree on the join key.
    """
    key = _key(display_name, team)
    if key is None:
        return None
    return feats.get(key) or feats.get((key[0], key[1], ""))


def build_opp_dvp_lookup(game_logs: pl.DataFrame) -> dict[str, float]:
    """Compute per-opponent defensive strength: mean real_score allowed per game.

    D74 (R8 first-pass): uses the locked Real Sports scoring formula on
    historical game_logs to build a team -> mean_real_score_allowed map.
    Written into opp_dvp_guard/forward/center features in job1 (same value
    per position; position-specific DvP needs a position column in game_logs
    which the current schema lacks). Better than zero because model attention
    on a constant (0) is effectively disabled; any signal helps.
    """
    return compute_opp_dvp_map(game_logs)


def build_team_pace_lookup(game_logs: pl.DataFrame) -> dict[str, float]:
    """Compute per-team possessions per 40 minutes (pace) from game_logs.

    D108 (pace causality fix): uses game_logs as-of the serve date to compute
    point-in-time team pace (only games strictly before the slate date).
    When job1 calls this, game_logs only contains already-played games, so
    the computation is causal by construction. Same shared function used by
    the corpus so train/serve pace computations never drift apart.
    """
    return compute_team_pace_map(game_logs)

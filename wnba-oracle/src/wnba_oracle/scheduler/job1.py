"""Job 1: morning scrape + Real Sports re-auth + odds + RotoWire lineups.

Output: job1_enrichment rows in Postgres, one per (slate_date, player_id).
Idempotent: re-running on the same day UPSERTs and overwrites.

Pipeline:
1. Headless re-auth via Playwright (uses scraper/storage_state.json).
2. Real Sports pool fetch (/home/wnba/next + a..z search overlay).
3. The Odds API basketball_wnba pull.
4. RotoWire lineups scrape.
5. Persist enrichment to Postgres.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
from dataclasses import dataclass

import httpx
from sqlalchemy import text

from wnba_oracle.common.logging import configure_logging, get_logger
from wnba_oracle.common.settings import get_settings
from wnba_oracle.db.engine import get_engine
from wnba_oracle.features.serving_features import (
    build_head_feature_lookup,
)
from wnba_oracle.features.serving_features import (
    lookup as head_feature_lookup,
)
from wnba_oracle.ingest.minutes_features import build_minutes_features, lookup
from wnba_oracle.ingest.odds import fetch_odds_for_slate
from wnba_oracle.ingest.realsports import (
    PlatformAuthRequired,
    capture_live_headers,
    fetch_pool_for_date,
    headers_or_capture,
)
from wnba_oracle.ingest.rotowire import LineupEntry, fetch_lineups

log = get_logger("oracle.job1")


@dataclass(frozen=True)
class Job1Result:
    slate_date: str
    n_pool: int
    n_odds: int
    n_lineups: int
    persisted_rows: int


JOB1_UPSERT = text(
    """
    INSERT INTO job1_enrichment (
        slate_date, player_id, real_sports_player_id, name, team, opponent,
        position, card_boost, features_json, captured_at
    ) VALUES (
        :slate_date, :player_id, :real_sports_player_id, :name, :team, :opponent,
        :position, :card_boost, :features_json, now()
    )
    ON CONFLICT (slate_date, player_id) DO UPDATE SET
        real_sports_player_id = EXCLUDED.real_sports_player_id,
        name = EXCLUDED.name,
        team = EXCLUDED.team,
        opponent = EXCLUDED.opponent,
        position = EXCLUDED.position,
        card_boost = EXCLUDED.card_boost,
        features_json = EXCLUDED.features_json,
        captured_at = now();
    """
)


def _device_uuid() -> str:
    return os.environ.get("WNBA_DEVICE_UUID", "wnba-oracle-prod-01-device")


def _device_name() -> str:
    return os.environ.get("WNBA_DEVICE_NAME", "wnba-oracle-prod-01")


# RotoWire status strings that mean "do not draft" — matches the same
# token set used by features/build.py's injury cascade so the two paths
# agree on what "OUT" means even when the cascade itself isn't on the
# prod path yet.
_OUT_STATUS_TOKENS = {"OUT", "IL", "INJ", "INACTIVE", "NA"}


def _normalize_name(name: str) -> str:
    """Case-fold + strip suffixes for RotoWire <-> Real Sports name matching.

    Real Sports often returns "A'ja Wilson"; RotoWire returns "A'ja Wilson"
    too but occasionally with a Jr./Sr./III suffix. Normalize for a stable
    join key.
    """
    if not name:
        return ""
    parts = [p for p in name.strip().split() if p]
    suffixes = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}
    parts = [p for p in parts if p.lower().rstrip(".") not in suffixes]
    return " ".join(parts).lower()


def _index_rotowire(entries: list[LineupEntry]) -> dict[tuple[str, str], LineupEntry]:
    """Build a (team_upper, normalized_name) -> LineupEntry lookup so
    Real Sports pool rows can be enriched in O(1)."""
    index: dict[tuple[str, str], LineupEntry] = {}
    for e in entries:
        key = (e.team.upper(), _normalize_name(e.player_name))
        index[key] = e
    return index


def is_out_status(status: str | None) -> bool:
    """True iff RotoWire's status token marks the player as a confirmed
    non-draft. Used by both job1 (when persisting features_json) and job2
    (when filtering the optimizer pool)."""
    if not status:
        return False
    upper = status.strip().upper()
    return any(tok in upper for tok in _OUT_STATUS_TOKENS)


async def _do_pool_fetch(slate_date: str) -> list:
    headers = await headers_or_capture(_device_uuid(), _device_name())

    async def _refresh():
        return await capture_live_headers(_device_uuid(), _device_name())

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            pool = await fetch_pool_for_date(
                slate_date, headers, client, refresh_headers=_refresh
            )
        except PlatformAuthRequired:
            # One more chance: force-refresh and retry once.
            headers = await capture_live_headers(_device_uuid(), _device_name())
            pool = await fetch_pool_for_date(
                slate_date, headers, client, refresh_headers=_refresh
            )
    return pool


def run(slate_date: str | None = None, *, dry_run: bool = False) -> Job1Result:
    settings = get_settings()
    sd = slate_date or dt.date.today().isoformat()
    log.info("job1_start", slate_date=sd, dry_run=dry_run)

    pool = asyncio.run(_do_pool_fetch(sd))
    log.info("job1_pool", n=len(pool))

    try:
        odds = fetch_odds_for_slate()
    except Exception as exc:
        log.warning("job1_odds_failed", reason=str(exc))
        odds = []

    try:
        lineups = fetch_lineups()
    except Exception as exc:
        log.warning("job1_lineups_failed", reason=str(exc))
        lineups = []

    # Build opponent / team map from odds + per-game roster join. For now
    # the platform pool gives team but not opponent; use the odds map.
    # Game-script-relevant Vegas signals (total, abs(spread)) are written
    # into features_json so Job 2 + the game-script multiplier can read them
    # without re-querying The Odds API.
    from wnba_oracle.features.build import team_key_from_full_name

    team_to_opp: dict[str, str] = {}
    team_to_vegas: dict[str, dict[str, float]] = {}
    for g in odds:
        h_key = team_key_from_full_name(g.home_team)
        a_key = team_key_from_full_name(g.away_team)
        team_to_opp[h_key] = a_key
        team_to_opp[a_key] = h_key
        total = float(g.total_point) if g.total_point is not None else 0.0
        home_spread = float(g.spread_home_point) if g.spread_home_point is not None else 0.0
        away_spread = float(g.spread_away_point) if g.spread_away_point is not None else 0.0
        team_to_vegas[h_key] = {"vegas_total": total, "vegas_spread": home_spread, "is_home": 1.0}
        team_to_vegas[a_key] = {"vegas_total": total, "vegas_spread": away_spread, "is_home": 0.0}

    # Build the RotoWire injury index once so the per-player loop stays
    # O(n) and joins by (team, normalized_name). RotoWire is the
    # authoritative injury signal — when present its status overrides
    # whatever Real Sports has (Real Sports sometimes lags by hours).
    rotowire_idx = _index_rotowire(lineups)
    n_rotowire_matched = 0
    n_rotowire_out = 0

    # Minutes/role features (D55): the minutes edge orthogonal to card_boost.
    # One league-wide stats.wnba.com pull, reconstruct real_score per game via
    # the locked formula, emit as-of recency minutes + per-minute rate. Current
    # season for role, prior season to stabilise the rate. Degrades to {} on
    # any nba_api failure -> job2 falls back to the boost predictor.
    year = int(sd[:4])
    try:
        minutes_feats = build_minutes_features(
            as_of_date=sd, seasons=[str(year), str(year - 1)]
        )
    except Exception as exc:
        log.warning("job1_minutes_failed", reason=str(exc)[:120])
        minutes_feats = {}
    n_minutes_matched = 0

    # D69 / Phase 2b: build the full causal head feature row per player from
    # the canonical wnba_game_logs corpus (same source the heads trained on).
    # Persisted into features_json["head_features"] so job2 can run the D63
    # trained heads via PickerArtifact.predict_real_score. Degrades to {} on
    # any DB / build failure -> job2 falls through to the existing
    # blended_real_score ladder, preserving the current behaviour byte for byte.
    head_feats: dict = {}
    try:
        from wnba_oracle.db.reads import read_game_logs

        game_logs = read_game_logs()
        head_feats = build_head_feature_lookup(game_logs, slate_date=sd)
    except Exception as exc:
        log.warning("job1_head_features_failed", reason=str(exc)[:120])
        head_feats = {}
    n_head_features_matched = 0

    rows = []
    for p in pool:
        vegas = team_to_vegas.get(p.team, {})
        rw_entry = rotowire_idx.get((p.team.upper(), _normalize_name(p.display_name)))
        # Prefer RotoWire's injury status when we have a confirmed match;
        # otherwise carry through the Real Sports value.
        if rw_entry is not None:
            n_rotowire_matched += 1
            rw_status = rw_entry.injury_status or ""
            injury_status = rw_status or p.injury_status
            is_starter = 1 <= rw_entry.starter_slot <= 5
            starter_slot = rw_entry.starter_slot
            confirmed = bool(rw_entry.confirmed)
        else:
            injury_status = p.injury_status
            is_starter = False
            starter_slot = 0
            confirmed = False
        is_out = is_out_status(injury_status)
        if is_out:
            n_rotowire_out += 1
        features = {
            "primary_ranking": p.primary_ranking,
            "injury_status": injury_status,
            "is_out": int(is_out),
            "is_starter": int(is_starter),
            "starter_slot": int(starter_slot),
            "rotowire_confirmed": int(confirmed),
            "vegas_total": vegas.get("vegas_total", 0.0),
            "vegas_spread": vegas.get("vegas_spread", 0.0),
            "is_home": int(vegas.get("is_home", 0.0)),
        }
        mf = lookup(minutes_feats, display_name=p.display_name, team=p.team)
        if mf is not None:
            n_minutes_matched += 1
            features["recent_minutes"] = round(mf.recent_minutes, 2)
            features["per_min_rate"] = round(mf.per_min_rate, 5)
            features["minutes_vol"] = round(mf.minutes_vol, 2)
            features["n_min_games"] = mf.n_games
        # D69 / Phase 2b: full head feature row (one nested dict under
        # `head_features`). job2 reads this and runs the D63 quantile heads.
        hf = head_feature_lookup(head_feats, display_name=p.display_name, team=p.team)
        if hf is not None:
            features["head_features"] = hf
            n_head_features_matched += 1
        rows.append(
            {
                "slate_date": sd,
                "player_id": int(p.platform_id) if p.platform_id.isdigit() else 0,
                "real_sports_player_id": p.platform_id,
                "name": p.display_name,
                "team": p.team,
                "opponent": team_to_opp.get(p.team, ""),
                "position": p.position,
                "card_boost": float(p.multiplier_bonus),
                "features_json": json.dumps(features),
            }
        )

    log.info(
        "job1_rotowire_merged",
        n_pool=len(pool),
        n_rotowire=len(lineups),
        n_matched=n_rotowire_matched,
        n_out=n_rotowire_out,
        n_minutes_matched=n_minutes_matched,
        n_head_features_matched=n_head_features_matched,
    )

    persisted = 0
    if not dry_run and settings.database_url:
        try:
            eng = get_engine()
        except RuntimeError as exc:
            log.error("job1_no_db", reason=str(exc))
            return Job1Result(sd, len(pool), len(odds), len(lineups), 0)
        with eng.begin() as conn:
            for row in rows:
                conn.execute(JOB1_UPSERT, row)
                persisted += 1

    log.info(
        "job1_done",
        slate_date=sd,
        n_pool=len(pool),
        n_odds=len(odds),
        n_lineups=len(lineups),
        persisted=persisted,
    )
    return Job1Result(sd, len(pool), len(odds), len(lineups), persisted)


def main() -> int:
    configure_logging("INFO")
    settings = get_settings()
    sd = dt.date.today().isoformat()
    try:
        run(sd, dry_run=settings.job1_dry_run)
    except Exception as exc:
        log.exception("job1_failed", error=str(exc))
        return 1
    return 0

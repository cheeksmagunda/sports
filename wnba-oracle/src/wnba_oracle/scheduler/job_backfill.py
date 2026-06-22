"""Backfill job1_enrichment head_features for all historical slates.

For slates already in job1_enrichment (2026-05-26 onward): update existing
rows to ensure head_features is populated where it currently is NULL.

For slates only in slate_labels (2025-05-16 through 2026-05-25): synthesize
new job1_enrichment rows from the contest_leaderboards lineup JSON
(which has player names, teams, positions, boosts) and compute head_features
from wnba_game_logs.

Cannot backfill: Vegas totals (Odds API has no historical endpoint),
RotoWire starter/injury status (live scrape only), player props.
These fields default to zero/null, same as the early-2026 pre-odds era.
"""

from __future__ import annotations

import json
import unicodedata

import psycopg
from sqlalchemy import text

from wnba_oracle.common.logging import configure_logging, get_logger
from wnba_oracle.common.settings import get_settings
from wnba_oracle.db.engine import get_engine
from wnba_oracle.db.reads import read_game_logs
from wnba_oracle.features.serving_features import (
    build_head_feature_lookup,
    build_opp_dvp_lookup,
)
from wnba_oracle.features.serving_features import (
    lookup as hf_lookup,
)

log = get_logger("oracle.job_backfill")


def _normalize_name(name: str) -> str:
    if not name:
        return ""
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower().strip()
    parts = n.split()
    suffixes = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}
    parts = [p for p in parts if p.lower().rstrip(".") not in suffixes]
    return " ".join(parts)


UPSERT_SQL = text("""
INSERT INTO job1_enrichment (
    slate_date, player_id, real_sports_player_id, name, team, opponent,
    position, card_boost, features_json, captured_at
) VALUES (
    :slate_date, :player_id, :real_sports_player_id, :name, :team, :opponent,
    :position, :card_boost, CAST(:features_json AS JSONB), now()
)
ON CONFLICT (slate_date, player_id) DO UPDATE SET
    features_json = CASE
        WHEN job1_enrichment.features_json->>'head_features' IS NOT NULL
            AND job1_enrichment.features_json->'head_features' != 'null'::jsonb
        THEN job1_enrichment.features_json
        ELSE EXCLUDED.features_json
    END,
    captured_at = CASE
        WHEN job1_enrichment.features_json->>'head_features' IS NOT NULL
            AND job1_enrichment.features_json->'head_features' != 'null'::jsonb
        THEN job1_enrichment.captured_at
        ELSE now()
    END;
""")

UPDATE_HEAD_SQL = text("""
UPDATE job1_enrichment
SET features_json = features_json || jsonb_build_object('head_features', CAST(:hf AS JSONB)),
    captured_at = now()
WHERE slate_date = :slate_date AND player_id = :player_id
  AND (features_json->>'head_features' IS NULL
       OR features_json->'head_features' = 'null'::jsonb);
""")


def _get_all_slate_dates(conn: psycopg.Connection) -> list:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT slate_date FROM slate_labels
            WHERE real_score IS NOT NULL ORDER BY slate_date
        """)
        return [r[0] for r in cur.fetchall()]


def _get_existing_enrichment_dates(conn: psycopg.Connection) -> set:
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT slate_date::varchar FROM job1_enrichment")
        return {r[0] for r in cur.fetchall()}


def _get_name_to_team_map(conn: psycopg.Connection) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT name, team, opponent FROM job1_enrichment ORDER BY slate_date DESC")
        mapping = {}
        for name, team, opponent in cur.fetchall():
            key = _normalize_name(name)
            if key and key not in mapping:
                mapping[key] = {"team": team, "opponent": opponent}
    return mapping


def _get_label_players(conn: psycopg.Connection, slate_date) -> list:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT display_name, team_key, card_boost, platform_player_id
            FROM slate_labels
            WHERE slate_date = %s AND section = 'highestBoostedValuePlayers'
        """, (slate_date,))
        return cur.fetchall()


def _get_leaderboard_players(conn: psycopg.Connection, slate_date) -> list:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT lineup FROM contest_leaderboards WHERE slate_date = %s",
            (slate_date,)
        )
        rows = cur.fetchall()
    seen = {}
    for (lineup,) in rows:
        if isinstance(lineup, str):
            try:
                lineup = json.loads(lineup)
            except Exception:
                continue
        if not isinstance(lineup, list):
            continue
        for p in lineup:
            pid = p.get("playerId") or p.get("id")
            if not pid:
                continue
            pid = int(pid)
            if pid not in seen:
                seen[pid] = {
                    "player_id": pid,
                    "display_name": p.get("displayName", ""),
                    "multiplier_bonus": round((p.get("multiplier", 1.0) - 1.0), 2),
                }
    return list(seen.values())


def _inject_opp_dvp(hf: dict, opp: str, opp_dvp: dict) -> dict:
    dvp = opp_dvp.get(opp, 0.0)
    hf = dict(hf)
    hf["opp_dvp_guard"] = dvp
    hf["opp_dvp_forward"] = dvp
    hf["opp_dvp_center"] = dvp
    return hf


def _process_existing_slate(engine, slate_date, head_feats: dict, opp_dvp: dict) -> int:
    with engine.connect() as db:
        result = db.execute(text("""
            SELECT player_id, name, team, opponent FROM job1_enrichment
            WHERE slate_date = :sd
              AND (features_json->>'head_features' IS NULL
                   OR features_json->'head_features' = 'null'::jsonb)
        """), {"sd": slate_date})
        rows = result.fetchall()

    updated = 0
    with engine.begin() as db:
        for r in rows:
            hf = hf_lookup(head_feats, display_name=r.name, team=r.team)
            if hf is None:
                continue
            hf = _inject_opp_dvp(hf, r.opponent or "", opp_dvp)
            db.execute(UPDATE_HEAD_SQL, {
                "hf": json.dumps(hf),
                "slate_date": slate_date,
                "player_id": r.player_id,
            })
            updated += 1
    return updated


def _process_historical_slate(
    engine,
    psyconn: psycopg.Connection,
    slate_date,
    head_feats: dict,
    opp_dvp: dict,
    name_to_team: dict,
) -> int:
    label_players = _get_label_players(psyconn, slate_date)
    lb_players = _get_leaderboard_players(psyconn, slate_date)

    label_by_norm = {}
    all_players = {}

    for display_name, team_key, card_boost, platform_player_id in label_players:
        pid = int(platform_player_id)
        norm = _normalize_name(display_name)
        label_by_norm[norm] = {"team": team_key, "player_id": pid}
        all_players[pid] = {
            "player_id": pid,
            "name": display_name,
            "team": team_key,
            "opponent": "",
            "position": "G",
            "boost": float(card_boost),
        }

    for p in lb_players:
        pid = p["player_id"]
        if pid in all_players:
            continue
        name = p["display_name"]
        norm = _normalize_name(name)
        team = ""
        if norm in label_by_norm:
            team = label_by_norm[norm]["team"]
        elif norm in name_to_team:
            team = name_to_team[norm]["team"]
        else:
            last = norm.split()[-1] if norm.split() else ""
            for key, val in name_to_team.items():
                if last and len(last) > 3 and key.endswith(last):
                    team = val["team"]
                    break
        all_players[pid] = {
            "player_id": pid,
            "name": name,
            "team": team,
            "opponent": "",
            "position": "G",
            "boost": float(p["multiplier_bonus"]),
        }

    inserted = 0
    with engine.begin() as db:
        for pid, p in all_players.items():
            hf = hf_lookup(head_feats, display_name=p["name"], team=p["team"])
            if hf is not None:
                hf = _inject_opp_dvp(hf, p["opponent"], opp_dvp)
            features: dict = {
                "is_out": 0,
                "is_starter": 0,
                "starter_slot": 0,
                "rotowire_confirmed": 0,
                "vegas_total": 0.0,
                "vegas_spread": 0.0,
                "is_home": 0,
                "_backfilled": True,
            }
            if hf is not None:
                features["head_features"] = hf
            db.execute(UPSERT_SQL, {
                "slate_date": slate_date,
                "player_id": pid,
                "real_sports_player_id": str(pid),
                "name": p["name"],
                "team": p["team"] or "",
                "opponent": p["opponent"] or "",
                "position": p["position"] or "G",
                "card_boost": p["boost"],
                "features_json": json.dumps(features),
            })
            inserted += 1
    return inserted


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    log.info("backfill_start")

    log.info("backfill_loading_game_logs")
    game_logs = read_game_logs()
    log.info("backfill_game_logs_loaded", n_rows=len(game_logs))

    engine = get_engine()
    opp_dvp = build_opp_dvp_lookup(game_logs)
    log.info("backfill_opp_dvp_built", n_teams=len(opp_dvp))

    psyconn = psycopg.connect(settings.database_url)

    all_dates = _get_all_slate_dates(psyconn)
    existing = _get_existing_enrichment_dates(psyconn)
    name_to_team = _get_name_to_team_map(psyconn)

    log.info(
        "backfill_slate_summary",
        total=len(all_dates),
        with_existing_enrichment=len(existing),
        name_map_size=len(name_to_team),
    )

    total_inserted = 0
    total_updated = 0

    for i, slate_date in enumerate(all_dates):
        try:
            head_feats = build_head_feature_lookup(game_logs, slate_date=slate_date)
        except Exception as exc:
            log.warning("backfill_head_feats_failed", slate_date=slate_date, reason=str(exc)[:120])
            continue

        n_feats = len(head_feats) // 2

        if slate_date in existing:
            try:
                n = _process_existing_slate(engine, slate_date, head_feats, opp_dvp)
                total_updated += n
                if n > 0:
                    log.info("backfill_updated", slate_date=slate_date, n=n, n_feats=n_feats)
            except Exception as exc:
                log.warning("backfill_update_failed", slate_date=slate_date, reason=str(exc)[:120])
        else:
            try:
                n = _process_historical_slate(
                    engine, psyconn, slate_date, head_feats, opp_dvp, name_to_team
                )
                total_inserted += n
                if n > 0:
                    log.info("backfill_inserted", slate_date=slate_date, n=n, n_feats=n_feats)
            except Exception as exc:
                log.warning("backfill_insert_failed", slate_date=slate_date, reason=str(exc)[:120])

        if (i + 1) % 20 == 0:
            log.info("backfill_progress", done=i + 1, total=len(all_dates))

    psyconn.close()
    log.info("backfill_done", inserted=total_inserted, updated=total_updated)
    return 0

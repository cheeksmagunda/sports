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
import json
import os
from dataclasses import dataclass
from typing import Any

import httpx

from wnba_oracle.common.clock import slate_date as current_slate_date
from wnba_oracle.common.logging import configure_logging, get_logger
from wnba_oracle.common.settings import get_settings
from wnba_oracle.db.engine import get_engine
from wnba_oracle.features.serving_features import (
    build_head_feature_lookup,
    build_opp_dvp_lookup,
)
from wnba_oracle.features.serving_features import lookup as head_feature_lookup
from wnba_oracle.ingest.identity import build_resolver
from wnba_oracle.ingest.minutes_features import (
    build_minutes_features,
    fetch_wnba_team_stats,
    lookup,
)
from wnba_oracle.ingest.odds import (
    build_props_lookup,
    fetch_odds_for_slate,
    fetch_player_props,
)
from wnba_oracle.ingest.realsports import (
    PlatformAuthRequired,
    capture_live_headers,
    fetch_game_start_by_player,
    fetch_pool_for_date,
    fetch_slate_game_times,
    headers_or_capture,
)
from wnba_oracle.ingest.rotowire import fetch_lineups

log = get_logger("oracle.job1")

# RotoWire name-matching/identity and enrichment persistence live in sibling
# job1_* modules so this module can focus on the scrape + build orchestration.
# Re-imported here because tests and scripts reference them via
# ``job1._name``, and because the pipeline below resolves them through this
# module's globals, which keeps monkeypatching on job1 effective.
from wnba_oracle.scheduler.job1_persist import (  # noqa: E402
    GAME_START_READ,
    JOB1_DELETE_SLATE,
    JOB1_UPSERT,
    LITE_PATCH,
    LITE_READ,
    SLATE_META_UPSERT,
    _persist_slate_meta,
    _replace_enrichment,
    parse_game_time,
)
from wnba_oracle.scheduler.job1_rotowire import (  # noqa: E402
    RotowireIndex,
    _index_rotowire,
    _name_keys,
    _normalize_name,
    is_out_status,
    rotowire_patch,
)

__all__ = [
    "GAME_START_READ",
    "JOB1_DELETE_SLATE",
    "JOB1_UPSERT",
    "LITE_PATCH",
    "LITE_READ",
    "SLATE_META_UPSERT",
    "RotowireIndex",
    "_index_rotowire",
    "_name_keys",
    "_normalize_name",
    "_persist_slate_meta",
    "_replace_enrichment",
    "is_out_status",
    "parse_game_time",
    "rotowire_patch",
]


@dataclass(frozen=True)
class Job1Result:
    slate_date: str
    n_pool: int
    n_odds: int
    n_lineups: int
    persisted_rows: int
    # D84: non-empty when the persisted pool failed the sanity gate. main()
    # exits nonzero on it so Railway marks the cron run failed.
    degraded_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class _EnrichmentContext:
    team_to_opp: dict[str, str]
    team_to_vegas: dict[str, dict[str, float]]
    rotowire: RotowireIndex
    minutes: dict
    head_features: dict
    resolver: Any
    team_stats: dict
    opponent_dvp: dict[str, float]
    props: dict


@dataclass
class _MergeStats:
    rotowire_matched: int = 0
    rotowire_out: int = 0
    minutes_matched: int = 0
    head_features_matched: int = 0
    props_matched: int = 0


def _device_uuid() -> str:
    return os.environ.get("WNBA_DEVICE_UUID", "wnba-oracle-prod-01-device")


def _device_name() -> str:
    return os.environ.get("WNBA_DEVICE_NAME", "wnba-oracle-prod-01")


def pool_sanity(rows: list[dict], *, min_pool: int, min_teams: int) -> list[str]:
    """D84: failure reasons for a degraded pool, empty when healthy.

    The effective row floor scales with slate size (3 rows per distinct
    team) without needing the game count, floored at `min_pool` so a
    one-team capture can never pass by shrinking its own expectation.
    """
    n_rows = len(rows)
    teams = {str(r.get("team", "") or "").strip() for r in rows}
    teams.discard("")
    n_teams = len(teams)
    reasons: list[str] = []
    row_floor = max(min_pool, 3 * n_teams)
    if n_rows < row_floor:
        reasons.append(f"n_pool={n_rows} below floor {row_floor}")
    if n_teams < min_teams:
        reasons.append(f"n_teams={n_teams} below floor {min_teams}")
    return reasons


def _build_enrichment_rows(
    slate_date: str,
    pool: list,
    context: _EnrichmentContext,
) -> tuple[list[dict], _MergeStats, list[str]]:
    """Merge provider signals into the durable Job 1 row shape."""
    rows: list[dict] = []
    stats = _MergeStats()
    head_feature_misses: list[str] = []

    for player in pool:
        vegas = context.team_to_vegas.get(player.team, {})
        rotowire_entry = context.rotowire.get(player.team, player.display_name)
        if rotowire_entry is not None:
            stats.rotowire_matched += 1
            rotowire_status = rotowire_entry.injury_status or ""
            injury_status = rotowire_status or player.injury_status
            is_starter = 1 <= rotowire_entry.starter_slot <= 5
            starter_slot = rotowire_entry.starter_slot
            confirmed = bool(rotowire_entry.confirmed)
        else:
            injury_status = player.injury_status
            is_starter = False
            starter_slot = 0
            confirmed = False

        is_out = is_out_status(injury_status)
        if is_out:
            stats.rotowire_out += 1
        features = {
            "primary_ranking": player.primary_ranking,
            "injury_status": injury_status,
            "is_out": int(is_out),
            "is_starter": int(is_starter),
            "starter_slot": int(starter_slot),
            "rotowire_confirmed": int(confirmed),
            "vegas_total": vegas.get("vegas_total", 0.0),
            "vegas_spread": vegas.get("vegas_spread", 0.0),
            "is_home": int(vegas.get("is_home", 0.0)),
        }
        minutes = lookup(
            context.minutes,
            display_name=player.display_name,
            team=player.team,
        )
        if minutes is not None:
            stats.minutes_matched += 1
            features["recent_minutes"] = round(minutes.recent_minutes, 2)
            features["per_min_rate"] = round(minutes.per_min_rate, 5)
            features["minutes_vol"] = round(minutes.minutes_vol, 2)
            features["n_min_games"] = minutes.n_games

        head_feature = None
        resolved_player_id: int | None = None
        if context.resolver:
            try:
                resolved_player_id = context.resolver.resolve(
                    player.platform_id,
                    display_name=player.display_name,
                    first_name=player.first_name,
                    last_name=player.last_name,
                    team=player.team,
                )
                if resolved_player_id is not None and isinstance(context.head_features, dict):
                    head_feature = context.head_features.get(resolved_player_id)
            except Exception as exc:
                log.debug(
                    "job1_resolver_lookup_failed",
                    player=player.display_name,
                    reason=str(exc)[:60],
                )
        if head_feature is None:
            head_feature = head_feature_lookup(
                context.head_features,
                display_name=player.display_name,
                team=player.team,
            )
        if head_feature is not None:
            head_feature = dict(head_feature)
            team_abbreviation = player.team.upper()
            opponent_abbreviation = context.team_to_opp.get(team_abbreviation, "").upper()
            team_metrics = context.team_stats.get(team_abbreviation, {})
            opponent_metrics = context.team_stats.get(opponent_abbreviation, {})
            head_feature["team_pace"] = team_metrics.get("pace", head_feature.get("team_pace", 0.0))
            head_feature["opp_pace"] = opponent_metrics.get(
                "pace", head_feature.get("opp_pace", 0.0)
            )
            head_feature["team_off_rtg"] = team_metrics.get(
                "off_rtg", head_feature.get("team_off_rtg", 0.0)
            )
            head_feature["team_def_rtg"] = team_metrics.get(
                "def_rtg", head_feature.get("team_def_rtg", 0.0)
            )
            head_feature["opp_off_rtg"] = opponent_metrics.get(
                "off_rtg", head_feature.get("opp_off_rtg", 0.0)
            )
            head_feature["opp_def_rtg"] = opponent_metrics.get(
                "def_rtg", head_feature.get("opp_def_rtg", 0.0)
            )
            if head_feature["team_pace"] and head_feature["opp_pace"]:
                head_feature["game_pace_implied"] = (
                    head_feature["team_pace"] + head_feature["opp_pace"]
                ) / 2.0
            defensive_value = context.opponent_dvp.get(opponent_abbreviation, 0.0)
            head_feature["opp_dvp_guard"] = defensive_value
            head_feature["opp_dvp_forward"] = defensive_value
            head_feature["opp_dvp_center"] = defensive_value
            features["head_features"] = head_feature
            stats.head_features_matched += 1
        elif resolved_player_id is not None:
            head_feature_misses.append(
                f"{player.display_name} ({player.team}) [no_features, pid={resolved_player_id}]"
            )
        else:
            head_feature_misses.append(f"{player.display_name} ({player.team}) [unresolved]")

        normalized_name = player.display_name.lower().strip()
        for market in ("player_points", "player_rebounds", "player_assists"):
            prop_data = context.props.get((normalized_name, market))
            if prop_data:
                short_name = market.replace("player_", "prop_")
                features[f"{short_name}_line"] = prop_data["line"]
                features[f"{short_name}_over_prob"] = prop_data["implied_over_prob"]
                features[f"{short_name}_under_prob"] = prop_data["implied_under_prob"]
                stats.props_matched += 1
                break
        if player.game_start_utc:
            features["game_start_utc"] = player.game_start_utc
        rows.append(
            {
                "slate_date": slate_date,
                "player_id": int(player.platform_id) if player.platform_id.isdigit() else 0,
                "real_sports_player_id": player.platform_id,
                "name": player.display_name,
                "team": player.team,
                "opponent": context.team_to_opp.get(player.team, ""),
                "position": player.position,
                "card_boost": float(player.multiplier_bonus),
                "features_json": json.dumps(features),
            }
        )

    return rows, stats, head_feature_misses


async def _do_pool_fetch(slate_date: str) -> tuple[list, list[str]]:
    headers = await headers_or_capture(_device_uuid(), _device_name())

    async def _refresh():
        return await capture_live_headers(_device_uuid(), _device_name())

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            pool = await fetch_pool_for_date(slate_date, headers, client, refresh_headers=_refresh)
        except PlatformAuthRequired:
            # One more chance: force-refresh and retry once.
            headers = await capture_live_headers(_device_uuid(), _device_name())
            pool = await fetch_pool_for_date(slate_date, headers, client, refresh_headers=_refresh)
        # D83: per-game tip times feed the late-refreeze lock gate. Strictly
        # best-effort; a slate_meta miss degrades the gate to its deadline
        # fallback, never the pool fetch.
        try:
            game_times = await fetch_slate_game_times(headers, client, refresh_headers=_refresh)
        except Exception as exc:
            log.warning("job1_game_times_failed", reason=str(exc)[:120])
            game_times = []
    return pool, game_times


def run(slate_date: str | None = None, *, dry_run: bool = False) -> Job1Result:
    settings = get_settings()
    sd = slate_date or current_slate_date().isoformat()
    log.info("job1_start", slate_date=sd, dry_run=dry_run)

    pool, game_times = asyncio.run(_do_pool_fetch(sd))
    log.info("job1_pool", n=len(pool))

    # D83: persist the slate's first tip (contest-lock proxy) so the job2
    # late re-freeze can refuse to append after lock. The platform exposes
    # no lock timestamp, so the earliest game dateTime stands in for it.
    if not dry_run:
        try:
            _persist_slate_meta(sd, game_times)
        except Exception as exc:
            log.warning("job1_slate_meta_failed", reason=str(exc)[:120])

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

    # D74/D80: player_points props from The Odds API per-event endpoint, scoped
    # to tonight's slate window. Sportsbook props encode injury news, role, and
    # matchup priced by sharper analysts; job2 reads features_json["prop_points_*"]
    # for the D78 multiplier. ~1 credit per game; degrades to empty on any failure.
    try:
        raw_props = fetch_player_props(slate_date=sd)
        props_lookup = build_props_lookup(raw_props)
    except Exception as exc:
        log.warning("job1_props_failed", reason=str(exc)[:120])
        props_lookup = {}
    # Build opponent / team map from odds + per-game roster join. For now
    # the platform pool gives team but not opponent; use the odds map.
    # Game-script-relevant Vegas signals (total, abs(spread)) are written
    # into features_json so Job 2 + the game-script multiplier can read them
    # without re-querying The Odds API.
    from wnba_oracle.features.game_features import team_key_from_full_name

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

    # Minutes/role features (D55): the minutes edge orthogonal to card_boost.
    # One league-wide stats.wnba.com pull, reconstruct real_score per game via
    # the locked formula, emit as-of recency minutes + per-minute rate. Current
    # season for role, prior season to stabilise the rate. Degrades to {} on
    # any nba_api failure -> job2 falls back to the boost predictor.
    year = int(sd[:4])
    try:
        minutes_feats = build_minutes_features(as_of_date=sd, seasons=[str(year), str(year - 1)])
    except Exception as exc:
        log.warning("job1_minutes_failed", reason=str(exc)[:120])
        minutes_feats = {}
    # D69 / Phase 2b: build the full causal head feature row per player from
    # the canonical wnba_game_logs corpus (same source the heads trained on).
    # Persisted into features_json["head_features"] so job2 can run the D63
    # trained heads via PickerArtifact.predict_real_score. Degrades to {} on
    # any DB / build failure -> job2 falls through to the existing
    # blended_real_score ladder, preserving the current behaviour byte for byte.
    head_feats: dict = {}
    game_logs_for_dvp = None
    try:
        from wnba_oracle.db.reads import read_game_logs

        game_logs_for_dvp = read_game_logs()
        head_feats = build_head_feature_lookup(game_logs_for_dvp, slate_date=sd)
    except Exception as exc:
        log.warning("job1_head_features_failed", reason=str(exc)[:120])
        head_feats = {}
    # D107 (#29): initialize Resolver to route identity lookups through nbaId
    # trust + override CSV instead of fragile name-string matching. Used per-player
    # to get the nba_api player_id, which is then looked up in head_feats.
    try:
        resolver = build_resolver()
    except Exception as exc:
        log.warning("job1_resolver_failed", reason=str(exc)[:120])
        resolver = None

    # D74 (R8 first-pass): WNBA team pace + defensive ratings from nba_api.
    # Injected into head_features per player so the trained heads see non-zero
    # values (they were trained with real team_pace from the corpus; serving
    # with zero is a calibration leak). Degrades to {} on any nba_api failure.
    try:
        team_stats = fetch_wnba_team_stats(season=str(year))
    except Exception as exc:
        log.warning("job1_team_stats_failed", reason=str(exc)[:120])
        team_stats = {}

    # D74: per-opponent defensive rating from historical game_logs.
    # Mean real_score allowed per opponent team across all recorded games.
    # Used for opp_dvp_guard/forward/center (same value per position until
    # game_logs gains a position column). Degrades to {} if game_logs failed.
    try:
        opp_dvp_map = (
            build_opp_dvp_lookup(game_logs_for_dvp) if game_logs_for_dvp is not None else {}
        )
    except Exception as exc:
        log.warning("job1_opp_dvp_failed", reason=str(exc)[:120])
        opp_dvp_map = {}

    rows, merge_stats, head_feature_misses = _build_enrichment_rows(
        sd,
        pool,
        _EnrichmentContext(
            team_to_opp=team_to_opp,
            team_to_vegas=team_to_vegas,
            rotowire=rotowire_idx,
            minutes=minutes_feats,
            head_features=head_feats,
            resolver=resolver,
            team_stats=team_stats,
            opponent_dvp=opp_dvp_map,
            props=props_lookup,
        ),
    )
    log.info(
        "job1_rotowire_merged",
        n_pool=len(pool),
        n_rotowire=len(lineups),
        n_matched=merge_stats.rotowire_matched,
        n_out=merge_stats.rotowire_out,
        n_minutes_matched=merge_stats.minutes_matched,
        n_head_features_matched=merge_stats.head_features_matched,
        n_team_stats=len(team_stats),
        n_opp_dvp=len(opp_dvp_map),
        n_props_matched=merge_stats.props_matched,
    )
    # D102 (#29): surface head-feature resolution misses. A high miss rate on a
    # full pool means the (initial, last, team) identity join is failing for a
    # cohort of players (the D99 staleness shape), who then serve no recency
    # signal. Warn with a capped sample of names so it is diagnosable per slate.
    if head_feature_misses and len(pool) > 0:
        miss_rate = len(head_feature_misses) / len(pool)
        if miss_rate >= 0.25:
            log.warning(
                "job1_head_feature_miss_rate_high",
                n_misses=len(head_feature_misses),
                n_pool=len(pool),
                miss_rate=round(miss_rate, 2),
                sample=head_feature_misses[:15],
            )

    degraded = pool_sanity(rows, min_pool=settings.job1_min_pool, min_teams=settings.job1_min_teams)
    persisted = 0
    if not degraded and not dry_run and settings.database_url:
        try:
            eng = get_engine()
        except RuntimeError as exc:
            log.error("job1_no_db", reason=str(exc))
            return Job1Result(sd, len(pool), len(odds), len(lineups), 0)
        with eng.begin() as conn:
            persisted = _replace_enrichment(conn, sd, rows)

    # D84 sanity gate. A rejected capture is logged and persisted as a
    # watchdog event, but is never promoted into the optimizer's active pool.
    # This keeps the last complete capture intact and its old captured_at
    # visible to the freshness monitor.
    if degraded:
        log.error(
            "job1_pool_degraded",
            slate_date=sd,
            reasons=degraded,
            n_rows=len(rows),
            persisted=persisted,
        )
        if not dry_run and settings.database_url:
            try:
                from wnba_oracle.scheduler.watchdog import (
                    SEVERITY_CRITICAL,
                    WatchdogEvent,
                    persist_events,
                )

                persist_events(
                    [
                        WatchdogEvent(
                            slate_date=sd,
                            trigger="job1_pool_degraded",
                            severity=SEVERITY_CRITICAL,
                            payload={"reasons": degraded, "n_rows": len(rows)},
                        )
                    ]
                )
            except Exception as exc:
                log.warning("job1_degraded_event_failed", reason=str(exc)[:120])

    log.info(
        "job1_done",
        slate_date=sd,
        n_pool=len(pool),
        n_odds=len(odds),
        n_lineups=len(lineups),
        persisted=persisted,
    )
    return Job1Result(sd, len(pool), len(odds), len(lineups), persisted, tuple(degraded))


def run_lite(slate_date: str | None = None) -> Job1Result:
    """Credit-free confirmed-lineup refresh.

    Re-scrapes RotoWire (free) and JSONB-merges only the RotoWire-authoritative
    fields onto the EXISTING enrichment rows -- no Odds/props/minutes/head
    re-fetch, so it costs zero Odds API credits and can fire many times across
    the day. This lets afternoon slates (which freeze at T-40, hours before the
    22:35 full job1-late) pick up confirmed starters before they lock. A no-op
    if the slate has no enrichment yet (the 13:00 full run must seed it first).
    """
    settings = get_settings()
    sd = slate_date or current_slate_date().isoformat()
    log.info("job1_lite_start", slate_date=sd)
    try:
        lineups = fetch_lineups()
    except Exception as exc:
        log.warning("job1_lite_lineups_failed", reason=str(exc))
        lineups = []
    if not lineups or not settings.database_url:
        log.warning("job1_lite_noop", slate_date=sd, n_lineups=len(lineups))
        return Job1Result(sd, 0, 0, len(lineups), 0)
    idx = _index_rotowire(lineups)
    try:
        eng = get_engine()
    except RuntimeError as exc:
        log.error("job1_lite_no_db", reason=str(exc))
        return Job1Result(sd, 0, 0, len(lineups), 0)
    n_existing = n_updated = n_confirmed = 0
    with eng.begin() as conn:
        existing = conn.execute(LITE_READ, {"sd": sd}).fetchall()
        n_existing = len(existing)
        for row_id, name, team in existing:
            rw = idx.get(team or "", name or "")
            if rw is None:
                continue
            conn.execute(LITE_PATCH, {"id": row_id, "patch": json.dumps(rotowire_patch(rw))})
            n_updated += 1
            n_confirmed += int(bool(rw.confirmed))
    log.info(
        "job1_lite_done",
        slate_date=sd,
        n_existing=n_existing,
        n_updated=n_updated,
        n_confirmed=n_confirmed,
        n_lineups=len(lineups),
    )
    return Job1Result(sd, n_existing, 0, len(lineups), n_updated)


def run_game_starts(slate_date: str | None = None) -> int:
    """Backfill features_json["game_start_utc"] onto tonight's enrichment.

    Credit-free (Real Sports only, no Odds API): one /home call plus one
    roster call per game. Exists because a slate spans several tip times
    and the pool rows a pre-D109 job1 persisted carry no game start, so
    POOL_EXCLUDE_STARTED_GAMES has nothing to filter on. Returns the number
    of rows patched.
    """
    sd = slate_date or current_slate_date().isoformat()
    log.info("job1_game_starts_start", slate_date=sd)

    async def _fetch() -> dict[str, str]:
        headers = await headers_or_capture(_device_uuid(), _device_name())

        async def _refresh():
            return await capture_live_headers(_device_uuid(), _device_name())

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                return await fetch_game_start_by_player(
                    sd, headers, client, refresh_headers=_refresh
                )
            except PlatformAuthRequired:
                headers = await capture_live_headers(_device_uuid(), _device_name())
                return await fetch_game_start_by_player(
                    sd, headers, client, refresh_headers=_refresh
                )

    start_by_pid = {pid: t for pid, t in asyncio.run(_fetch()).items() if t}
    if not start_by_pid:
        log.warning("job1_game_starts_empty", slate_date=sd)
        return 0
    eng = get_engine()
    n_patched = 0
    with eng.begin() as conn:
        for row_id, rs_pid in conn.execute(GAME_START_READ, {"sd": sd}).fetchall():
            start = start_by_pid.get(str(rs_pid or ""))
            if not start:
                continue
            conn.execute(LITE_PATCH, {"id": row_id, "patch": json.dumps({"game_start_utc": start})})
            n_patched += 1
    log.info(
        "job1_game_starts_done",
        slate_date=sd,
        n_players=len(start_by_pid),
        n_patched=n_patched,
        n_distinct_starts=len(set(start_by_pid.values())),
    )
    return n_patched


def main() -> int:
    configure_logging("INFO")
    settings = get_settings()
    sd = current_slate_date().isoformat()
    try:
        result = run(sd, dry_run=settings.job1_dry_run)
    except Exception as exc:
        log.exception("job1_failed", error=str(exc))
        return 1
    if result.degraded_reasons:
        # Nonzero exit so Railway surfaces the cron run as failed.
        return 1
    return 0


def main_lite() -> int:
    configure_logging("INFO")
    try:
        run_lite(current_slate_date().isoformat())
    except Exception as exc:
        log.exception("job1_lite_failed", error=str(exc))
        return 1
    return 0

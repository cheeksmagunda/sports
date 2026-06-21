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
    build_opp_dvp_lookup,
)
from wnba_oracle.features.serving_features import (
    lookup as head_feature_lookup,
)
from wnba_oracle.ingest.minutes_features import (
    build_minutes_features,
    fetch_wnba_team_stats,
    lookup,
)
from wnba_oracle.ingest.odds import build_props_lookup, fetch_odds_for_slate, fetch_player_props
from wnba_oracle.ingest.realsports import (
    PlatformAuthRequired,
    capture_live_headers,
    fetch_pool_for_date,
    fetch_slate_game_times,
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
    # D84: non-empty when the persisted pool failed the sanity gate. main()
    # exits nonzero on it so Railway marks the cron run failed.
    degraded_reasons: tuple[str, ...] = ()


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


SLATE_META_UPSERT = text(
    """
    INSERT INTO slate_meta (
        slate_date, first_tip_utc, contest_lock_utc, source, payload_json, updated_at
    ) VALUES (
        :slate_date, :first_tip_utc, :contest_lock_utc, :source,
        CAST(:payload_json AS JSONB), now()
    )
    ON CONFLICT (slate_date) DO UPDATE SET
        first_tip_utc = EXCLUDED.first_tip_utc,
        contest_lock_utc = EXCLUDED.contest_lock_utc,
        source = EXCLUDED.source,
        payload_json = EXCLUDED.payload_json,
        updated_at = now();
    """
)


def parse_game_time(raw: str) -> dt.datetime | None:
    """Parse a Real Sports game `dateTime` ("2026-05-27T23:00:00.000Z")
    into an aware UTC datetime. None on anything unparseable."""
    if not raw:
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return parsed.astimezone(dt.UTC)


def _persist_slate_meta(slate_date: str, game_times: list[str]) -> None:
    """UPSERT the slate's timing facts (D83).

    first_tip_utc is the earliest game time, the contest-lock proxy.
    contest_lock_utc stays NULL until the platform exposes a real lock
    timestamp (probe 2026-06-10: the contest payload only carries a live
    `isLocked` boolean). A row with NULL first_tip_utc still gets written
    so the gate can tell "job1 looked and found nothing" from "job1 never
    ran" when debugging.
    """
    parsed = sorted(t for t in (parse_game_time(g) for g in game_times) if t is not None)
    first_tip = parsed[0] if parsed else None
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(
            SLATE_META_UPSERT,
            {
                "slate_date": slate_date,
                "first_tip_utc": first_tip,
                "contest_lock_utc": None,
                "source": "realsports_home_next",
                "payload_json": json.dumps({"game_times": game_times}),
            },
        )
    log.info(
        "job1_slate_meta",
        slate_date=slate_date,
        first_tip_utc=first_tip.isoformat() if first_tip else None,
        n_games=len(game_times),
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


def _name_keys(name: str) -> tuple[str, str]:
    """Return (full_norm, initial_norm) join keys for a player name.

    full_norm    = the case/suffix-normalized full name ('cecilia zandalasini').
    initial_norm = first-initial + last name ('c zandalasini').

    Both 'C. Zandalasini' (RotoWire often abbreviates the visiting team's first
    names) and 'Cecilia Zandalasini' (Real Sports' full names) collapse to the
    same initial_norm, so the initial key bridges the two sources when the full
    names differ. The exact key is still tried first to avoid first-initial +
    last-name collisions between two different players on the same team.
    """
    norm = _normalize_name(name)
    parts = norm.split()
    if len(parts) >= 2:
        initial = parts[0].rstrip(".")[:1]
        return norm, f"{initial} {parts[-1]}"
    return norm, norm


@dataclass(frozen=True)
class RotowireIndex:
    """(team, name) -> LineupEntry lookup with an abbreviated-name fallback."""

    exact: dict[tuple[str, str], LineupEntry]
    by_initial: dict[tuple[str, str], LineupEntry]

    def get(self, team: str, name: str) -> LineupEntry | None:
        team_u = team.upper()
        full_norm, initial_norm = _name_keys(name)
        hit = self.exact.get((team_u, full_norm))
        if hit is not None:
            return hit
        return self.by_initial.get((team_u, initial_norm))

    def __contains__(self, key: tuple[str, str]) -> bool:
        # Back-compat for `(team, normalized_name) in idx` callers/tests.
        return key in self.exact


def _index_rotowire(entries: list[LineupEntry]) -> RotowireIndex:
    """Build a RotowireIndex so Real Sports pool rows enrich in O(1).

    Keys each entry under both the exact normalized full name and the
    first-initial + last-name fallback so abbreviated RotoWire names still
    match Real Sports' full names (D100 fix)."""
    exact: dict[tuple[str, str], LineupEntry] = {}
    by_initial: dict[tuple[str, str], LineupEntry] = {}
    for e in entries:
        team = e.team.upper()
        full_norm, initial_norm = _name_keys(e.player_name)
        exact[(team, full_norm)] = e
        # First write wins on the initial key so a later collision (two players,
        # same team + initial + last name) can't clobber the first; the exact
        # key still disambiguates when the full name is present.
        by_initial.setdefault((team, initial_norm), e)
    return RotowireIndex(exact=exact, by_initial=by_initial)


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


def is_out_status(status: str | None) -> bool:
    """True iff RotoWire's status token marks the player as a confirmed
    non-draft. Used by both job1 (when persisting features_json) and job2
    (when filtering the optimizer pool)."""
    if not status:
        return False
    upper = status.strip().upper()
    return any(tok in upper for tok in _OUT_STATUS_TOKENS)


async def _do_pool_fetch(slate_date: str) -> tuple[list, list[str]]:
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
        # D83: per-game tip times feed the late-refreeze lock gate. Strictly
        # best-effort; a slate_meta miss degrades the gate to its deadline
        # fallback, never the pool fetch.
        try:
            game_times = await fetch_slate_game_times(
                headers, client, refresh_headers=_refresh
            )
        except Exception as exc:
            log.warning("job1_game_times_failed", reason=str(exc)[:120])
            game_times = []
    return pool, game_times


def run(slate_date: str | None = None, *, dry_run: bool = False) -> Job1Result:
    settings = get_settings()
    sd = slate_date or dt.date.today().isoformat()
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
    n_props_matched = 0

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
    game_logs_for_dvp = None
    try:
        from wnba_oracle.db.reads import read_game_logs

        game_logs_for_dvp = read_game_logs()
        head_feats = build_head_feature_lookup(game_logs_for_dvp, slate_date=sd)
    except Exception as exc:
        log.warning("job1_head_features_failed", reason=str(exc)[:120])
        head_feats = {}
    n_head_features_matched = 0

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
        opp_dvp_map = build_opp_dvp_lookup(game_logs_for_dvp) if game_logs_for_dvp is not None else {}
    except Exception as exc:
        log.warning("job1_opp_dvp_failed", reason=str(exc)[:120])
        opp_dvp_map = {}

    rows = []
    for p in pool:
        vegas = team_to_vegas.get(p.team, {})
        rw_entry = rotowire_idx.get(p.team, p.display_name)
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
            # Copy before mutating so the shared lookup dict is not modified.
            hf = dict(hf)
            # D74 (R8 first-pass): inject tonight's matchup context that the
            # rolling-feature builder cannot know (team_pace, opp_pace,
            # opponent defensive rating, DvP). The trained heads were calibrated
            # on real values for team_pace (nba_api via the gamelog corpus);
            # serving with zero is a calibration leak — override with live values.
            team_abbr = p.team.upper()
            opp_abbr = team_to_opp.get(team_abbr, "").upper()
            ts = team_stats.get(team_abbr, {})
            os_ = team_stats.get(opp_abbr, {})
            hf["team_pace"] = ts.get("pace", hf.get("team_pace", 0.0))
            hf["opp_pace"] = os_.get("pace", hf.get("opp_pace", 0.0))
            hf["team_off_rtg"] = ts.get("off_rtg", hf.get("team_off_rtg", 0.0))
            hf["team_def_rtg"] = ts.get("def_rtg", hf.get("team_def_rtg", 0.0))
            hf["opp_off_rtg"] = os_.get("off_rtg", hf.get("opp_off_rtg", 0.0))
            hf["opp_def_rtg"] = os_.get("def_rtg", hf.get("opp_def_rtg", 0.0))
            if hf["team_pace"] and hf["opp_pace"]:
                hf["game_pace_implied"] = (hf["team_pace"] + hf["opp_pace"]) / 2.0
            dvp = opp_dvp_map.get(opp_abbr, 0.0)
            hf["opp_dvp_guard"] = dvp
            hf["opp_dvp_forward"] = dvp
            hf["opp_dvp_center"] = dvp
            features["head_features"] = hf
            n_head_features_matched += 1
        # D74: player prop lines as projection cross-check signals.
        # Stored under features_json keys for future training; job2 can read
        # these as a calibration signal (if prop_pts_line > p50 projection,
        # the market thinks we are under-projecting). Not yet used in the
        # optimizer objective — stored for corpus enrichment only.
        norm_name = p.display_name.lower().strip()
        for market in ("player_points", "player_rebounds", "player_assists"):
            prop_data = props_lookup.get((norm_name, market))
            if prop_data:
                short = market.replace("player_", "prop_")
                features[f"{short}_line"] = prop_data["line"]
                features[f"{short}_over_prob"] = prop_data["implied_over_prob"]
                features[f"{short}_under_prob"] = prop_data["implied_under_prob"]
                n_props_matched += 1
                break  # count once per player
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
        n_team_stats=len(team_stats),
        n_opp_dvp=len(opp_dvp_map),
        n_props_matched=n_props_matched,
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

    # D84 sanity gate, AFTER persist on purpose: a degraded capture still
    # lands in job1_enrichment for forensics, but the run is marked failed
    # so it can never silently masquerade as a healthy fire (the 2026-06-08
    # morning fire persisted 1 row / 1 team and looked "present").
    degraded = pool_sanity(
        rows, min_pool=settings.job1_min_pool, min_teams=settings.job1_min_teams
    )
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
    return Job1Result(
        sd, len(pool), len(odds), len(lineups), persisted, tuple(degraded)
    )


def main() -> int:
    configure_logging("INFO")
    settings = get_settings()
    sd = dt.date.today().isoformat()
    try:
        result = run(sd, dry_run=settings.job1_dry_run)
    except Exception as exc:
        log.exception("job1_failed", error=str(exc))
        return 1
    if result.degraded_reasons:
        # Nonzero exit so Railway surfaces the cron run as failed.
        return 1
    return 0

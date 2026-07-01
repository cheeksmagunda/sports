"""The Odds API client for `basketball_wnba`.

Free-tier budget: 500 credits/month. Cache once per slate per market group
(spread + total + h2h are one request; player props are separate). Degrade to
most-recent-cached on quota burn; never auto-upgrade.

Markets we consume:
- `spreads` (point spread + price)
- `totals` (over / under + price)
- `h2h` (moneyline)
- (later) `player_points`, `player_rebounds`, `player_assists`

Bookmaker filter defaults to a 3-bookmaker majority (draftkings, fanduel,
betmgm) to dampen single-book noise; the picker reads `vegas_total`,
`vegas_spread`, `home_moneyline`, `away_moneyline` as medians across these.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

import httpx
import polars as pl

from wnba_oracle.common.logging import get_logger
from wnba_oracle.common.settings import get_settings
from wnba_oracle.ingest.cache import cache_get, cache_put

log = get_logger("oracle.ingest.odds")

BASE = "https://api.the-odds-api.com/v4"
SPORT_KEY = "basketball_wnba"
DEFAULT_BOOKMAKERS = ("draftkings", "fanduel", "betmgm")
DEFAULT_REGIONS = "us"
DEFAULT_MARKETS = "h2h,spreads,totals"


@dataclass(frozen=True)
class GameOdds:
    home_team: str
    away_team: str
    commence_time: str
    h2h_home: float | None
    h2h_away: float | None
    spread_home_point: float | None
    spread_home_price: float | None
    spread_away_point: float | None
    spread_away_price: float | None
    total_point: float | None
    total_over_price: float | None
    total_under_price: float | None


def fetch_odds_for_slate(
    *,
    use_cache: bool = True,
    cache_ttl_s: float = 6 * 3600.0,
    markets: str = DEFAULT_MARKETS,
    bookmakers: tuple[str, ...] = DEFAULT_BOOKMAKERS,
    regions: str = DEFAULT_REGIONS,
) -> list[GameOdds]:
    """One Odds API call (1-2 credits). Returns aggregated odds per upcoming
    WNBA game with a median-across-bookmakers reduction.
    """
    settings = get_settings()
    if not settings.odds_api_key:
        raise RuntimeError("ODDS_API_KEY not set; refusing to call The Odds API")

    url = f"{BASE}/sports/{SPORT_KEY}/odds"
    params: dict[str, Any] = {
        "apiKey": settings.odds_api_key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "decimal",
        "bookmakers": ",".join(bookmakers),
    }
    cache_key = f"odds::{SPORT_KEY}::{markets}::{','.join(bookmakers)}"
    if use_cache:
        cached = cache_get(cache_key, params, ttl_s=cache_ttl_s)
        if cached is not None:
            log.info("odds_fetch_cache_hit")
            return [GameOdds(**row) for row in cached["rows"]]

    log.info("odds_fetch", url=url, markets=markets)
    with httpx.Client(timeout=20.0) as client:
        # Cache key intentionally excludes apiKey so the key rotation does
        # not invalidate cache. apiKey only travels with the live params.
        r = client.get(url, params=params)
        r.raise_for_status()
        # Credits remaining header surfaces budget; log it.
        remaining = r.headers.get("x-requests-remaining")
        used = r.headers.get("x-requests-used")
        log.info("odds_quota", remaining=remaining, used=used)
        data = r.json() or []

    out: list[GameOdds] = []
    for game in data:
        out.append(_reduce_game(game))
    if use_cache:
        cache_put(
            cache_key,
            params,
            {"rows": [g.__dict__ for g in out], "x_requests_remaining": remaining},
        )
    return out


def _reduce_game(game: dict[str, Any]) -> GameOdds:
    home = game.get("home_team", "")
    away = game.get("away_team", "")
    commence = game.get("commence_time", "")

    def _median_nonnull(xs: list[float]) -> float | None:
        xs = [x for x in xs if x is not None]
        if not xs:
            return None
        s = sorted(xs)
        n = len(s)
        if n % 2 == 1:
            return s[n // 2]
        return 0.5 * (s[n // 2 - 1] + s[n // 2])

    h2h_h, h2h_a = [], []
    sp_hp, sp_hpr, sp_ap, sp_apr = [], [], [], []
    tot_pt, tot_op, tot_up = [], [], []
    for bk in game.get("bookmakers", []):
        for mk in bk.get("markets", []):
            outcomes = mk.get("outcomes", [])
            key = mk.get("key")
            if key == "h2h":
                for o in outcomes:
                    name = o.get("name")
                    price = o.get("price")
                    if name == home:
                        h2h_h.append(price)
                    elif name == away:
                        h2h_a.append(price)
            elif key == "spreads":
                for o in outcomes:
                    name = o.get("name")
                    point = o.get("point")
                    price = o.get("price")
                    if name == home:
                        sp_hp.append(point)
                        sp_hpr.append(price)
                    elif name == away:
                        sp_ap.append(point)
                        sp_apr.append(price)
            elif key == "totals":
                for o in outcomes:
                    name = o.get("name")
                    point = o.get("point")
                    price = o.get("price")
                    tot_pt.append(point)
                    if name == "Over":
                        tot_op.append(price)
                    elif name == "Under":
                        tot_up.append(price)

    return GameOdds(
        home_team=home,
        away_team=away,
        commence_time=commence,
        h2h_home=_median_nonnull(h2h_h),
        h2h_away=_median_nonnull(h2h_a),
        spread_home_point=_median_nonnull(sp_hp),
        spread_home_price=_median_nonnull(sp_hpr),
        spread_away_point=_median_nonnull(sp_ap),
        spread_away_price=_median_nonnull(sp_apr),
        total_point=_median_nonnull(tot_pt),
        total_over_price=_median_nonnull(tot_op),
        total_under_price=_median_nonnull(tot_up),
    )


def odds_to_polars(odds: list[GameOdds]) -> pl.DataFrame:
    return pl.from_dicts([g.__dict__ for g in odds]) if odds else pl.DataFrame()


@dataclass(frozen=True)
class PlayerProp:
    player_name: str
    market: str  # "player_points", "player_rebounds", "player_assists"
    line: float
    over_price: float | None
    under_price: float | None

    @property
    def implied_over_prob(self) -> float | None:
        if self.over_price is None:
            return None
        if self.over_price >= 1.0:
            return 1.0 / self.over_price
        return None

    @property
    def implied_under_prob(self) -> float | None:
        if self.under_price is None:
            return None
        if self.under_price >= 1.0:
            return 1.0 / self.under_price
        return None


def fetch_wnba_events(*, timeout_s: float = 20.0) -> list[dict[str, Any]]:
    """List upcoming WNBA events (id + team names + commence_time).

    The events endpoint is free (0 credits) and is the only way to obtain the
    per-event ids that the player-prop odds endpoint requires (D80). Raises on
    HTTP error so the caller can degrade to an empty prop list.
    """
    settings = get_settings()
    if not settings.odds_api_key:
        return []
    url = f"{BASE}/sports/{SPORT_KEY}/events"
    params: dict[str, Any] = {"apiKey": settings.odds_api_key}
    with httpx.Client(timeout=timeout_s) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        return r.json() or []


def _event_in_slate_window(commence_time: str, slate_date: str) -> bool:
    """True iff an event's UTC commence_time falls in `slate_date`'s ET evening.

    WNBA games for an ET slate date D tip from ~noon ET (16:00 UTC on D) through
    late night (up to ~04:00 ET / 08:00 UTC on D+1). Filtering to this window
    keeps prop fetches to the night's slate: fewer credits and no merging of a
    player's line across different game days. Unparseable inputs are kept.
    """
    try:
        ct = dt.datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
        d = dt.date.fromisoformat(slate_date)
    except (ValueError, AttributeError):
        return True
    start = dt.datetime(d.year, d.month, d.day, 16, 0, tzinfo=dt.UTC)
    end = start + dt.timedelta(hours=16)
    return start <= ct < end


def _parse_event_props(event: dict[str, Any], *, markets: tuple[str, ...]) -> list[PlayerProp]:
    """Parse a single per-event odds response into PlayerProp rows.

    Pure function (no network) so the parse is unit-testable against a fixture.
    Emits one PlayerProp per over/under outcome; the caller merges by
    (player_name, market, line) in ``build_props_lookup``.
    """
    out: list[PlayerProp] = []
    for bk in event.get("bookmakers", []):
        for mk in bk.get("markets", []):
            market_key = mk.get("key", "")
            if market_key not in markets:
                continue
            for outcome in mk.get("outcomes", []):
                # Player-prop outcomes carry the player in `description`; `name`
                # is the side ("Over" / "Under").
                name = outcome.get("description") or outcome.get("name", "")
                point = outcome.get("point")
                price = outcome.get("price")
                side = (outcome.get("name") or "").lower()
                if not name or point is None:
                    continue
                if side == "over":
                    out.append(
                        PlayerProp(
                            player_name=str(name),
                            market=market_key,
                            line=float(point),
                            over_price=float(price) if price else None,
                            under_price=None,
                        )
                    )
                elif side == "under":
                    out.append(
                        PlayerProp(
                            player_name=str(name),
                            market=market_key,
                            line=float(point),
                            over_price=None,
                            under_price=float(price) if price else None,
                        )
                    )
    return out


def fetch_player_props(
    *,
    slate_date: str | None = None,
    use_cache: bool = True,
    cache_ttl_s: float = 3 * 3600.0,
    markets: str = "player_points",
    bookmakers: tuple[str, ...] = DEFAULT_BOOKMAKERS,
    regions: str = DEFAULT_REGIONS,
) -> list[PlayerProp]:
    """Fetch WNBA player prop O/Us from The Odds API.

    Player props encode injury news, role, matchup, and minutes — priced by
    sharper analysts than any heuristic. Used as a projection multiplier in
    job2 (D78) and stored in job1 features_json.

    D80: player props are ONLY available on the per-event endpoint
    (`/events/{id}/odds`); the aggregate `/odds` endpoint returns HTTP 422 for
    `player_*` markets. We therefore list events (free) then query each event.
    Cost is 1 credit per market per event, so the default is `player_points`
    only — the single market job2's `_prop_signal_multiplier` reads — to stay
    well inside the 500-credit/month free tier (~3 events x 2 daily runs).
    Cache TTL is 3h (props move closer to tip than game odds).

    Returns an empty list and logs a warning on any failure (API key missing,
    quota burn, no markets available). Never blocks job1.
    """
    settings = get_settings()
    if not settings.odds_api_key:
        log.warning("fetch_player_props_no_key")
        return []

    market_tuple = tuple(m.strip() for m in markets.split(",") if m.strip())
    cache_key = f"props::{SPORT_KEY}::{markets}::{','.join(bookmakers)}::{slate_date or 'all'}"
    cache_params = {"markets": markets, "bookmakers": ",".join(bookmakers), "regions": regions}
    if use_cache:
        cached = cache_get(cache_key, cache_params, ttl_s=cache_ttl_s)
        if cached is not None:
            log.info("player_props_cache_hit")
            return [PlayerProp(**r) for r in cached["rows"]]

    log.info("player_props_fetch", markets=markets, slate_date=slate_date)
    try:
        events = fetch_wnba_events()
    except Exception as exc:
        log.warning("player_props_events_failed", reason=str(exc)[:120])
        return []

    # Restrict to the slate's event window so we spend ~1 credit per game tonight
    # (not for the whole multi-day schedule) and never merge a player's line
    # across different game days.
    if slate_date:
        events = [
            e for e in events if _event_in_slate_window(e.get("commence_time", ""), slate_date)
        ]

    out: list[PlayerProp] = []
    n_events_ok = 0
    remaining: str | None = None
    with httpx.Client(timeout=20.0) as client:
        for ev in events:
            eid = ev.get("id")
            if not eid:
                continue
            url = f"{BASE}/sports/{SPORT_KEY}/events/{eid}/odds"
            params: dict[str, Any] = {
                "apiKey": settings.odds_api_key,
                "regions": regions,
                "markets": markets,
                "oddsFormat": "decimal",
                "bookmakers": ",".join(bookmakers),
            }
            try:
                r = client.get(url, params=params)
                remaining = r.headers.get("x-requests-remaining", remaining)
                r.raise_for_status()
                ev_json = r.json() or {}
            except Exception as exc:
                # One event's failure must not lose the others' props.
                log.warning(
                    "player_props_event_failed", event_id=str(eid)[:12], reason=str(exc)[:120]
                )
                continue
            out.extend(_parse_event_props(ev_json, markets=market_tuple))
            n_events_ok += 1

    log.info("player_props_quota", remaining=remaining)
    # Cache only when at least one event responded, so a transient total
    # failure does not poison the cache with an empty list for 3h.
    if use_cache and n_events_ok > 0:
        cache_put(cache_key, cache_params, {"rows": [p.__dict__ for p in out]})
    log.info(
        "player_props_fetched", n=len(out), n_events_ok=n_events_ok, n_events_total=len(events)
    )
    return out


def build_props_lookup(props: list[PlayerProp]) -> dict[tuple[str, str], dict[str, float]]:
    """Build {(normalized_name, market): {line, over_prob, under_prob}} lookup.

    Aggregates over/under sides into a single entry per (player, market, line)
    by taking the most common line per player per market (simple majority).
    """
    from collections import defaultdict

    # Group by (norm_name, market) -> list of (line, over_price, under_price)
    groups: dict[tuple[str, str], list[PlayerProp]] = defaultdict(list)
    for p in props:
        norm = p.player_name.lower().strip()
        groups[(norm, p.market)].append(p)

    out: dict[tuple[str, str], dict[str, float]] = {}
    for (norm_name, market), entries in groups.items():
        # Pick the modal line across bookmakers
        from collections import Counter

        line_counts = Counter(e.line for e in entries)
        modal_line = line_counts.most_common(1)[0][0]
        relevant = [e for e in entries if e.line == modal_line]
        over_prices = [e.over_price for e in relevant if e.over_price]
        under_prices = [e.under_price for e in relevant if e.under_price]

        def _med(xs: list[float]) -> float | None:
            if not xs:
                return None
            xs = sorted(xs)
            n = len(xs)
            return xs[n // 2] if n % 2 == 1 else (xs[n // 2 - 1] + xs[n // 2]) / 2

        op = _med(over_prices)
        up = _med(under_prices)
        out[(norm_name, market)] = {
            "line": modal_line,
            "over_price": op or 0.0,
            "under_price": up or 0.0,
            "implied_over_prob": 1.0 / op if op and op > 0 else 0.0,
            "implied_under_prob": 1.0 / up if up and up > 0 else 0.0,
        }
    return out

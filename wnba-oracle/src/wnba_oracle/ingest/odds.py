"""The Odds API client for `basketball_wnba`.

Free-tier budget: 500 credits/month. Cache once per slate per market group
(spread + total + h2h are one request; player props are separate). See
DECISIONS D10 and Part 0.3 item 7. Degrade to most-recent-cached on
quota burn; never auto-upgrade.

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
    market: str   # "player_points", "player_rebounds", "player_assists"
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


def fetch_player_props(
    *,
    use_cache: bool = True,
    cache_ttl_s: float = 3 * 3600.0,
    markets: str = "player_points,player_rebounds,player_assists",
    bookmakers: tuple[str, ...] = DEFAULT_BOOKMAKERS,
    regions: str = DEFAULT_REGIONS,
) -> list[PlayerProp]:
    """Fetch WNBA player prop O/Us from The Odds API.

    D74: player props encode injury news, role, matchup, and minutes —
    priced by sharper analysts than any heuristic. Used as additional
    feature signal in job1 features_json. Budget: 1-2 credits per call.
    Cache TTL is 3h (shorter than game odds because props move closer to tip).

    Returns an empty list and logs a warning on any failure (API key missing,
    quota burn, no markets available). Never blocks job1.
    """
    settings = get_settings()
    if not settings.odds_api_key:
        log.warning("fetch_player_props_no_key")
        return []

    url = f"{BASE}/sports/{SPORT_KEY}/odds"
    params: dict[str, Any] = {
        "apiKey": settings.odds_api_key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "decimal",
        "bookmakers": ",".join(bookmakers),
    }
    cache_key = f"props::{SPORT_KEY}::{markets}::{','.join(bookmakers)}"
    if use_cache:
        cached = cache_get(cache_key, params, ttl_s=cache_ttl_s)
        if cached is not None:
            log.info("player_props_cache_hit")
            return [PlayerProp(**r) for r in cached["rows"]]

    log.info("player_props_fetch", url=url, markets=markets)
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get(url, params=params)
            remaining = r.headers.get("x-requests-remaining")
            log.info("player_props_quota", remaining=remaining)
            r.raise_for_status()
            data = r.json() or []
    except Exception as exc:
        log.warning("player_props_fetch_failed", reason=str(exc)[:120])
        return []

    out: list[PlayerProp] = []
    for game in data:
        for bk in game.get("bookmakers", []):
            for mk in bk.get("markets", []):
                market_key = mk.get("key", "")
                if not market_key.startswith("player_"):
                    continue
                for outcome in mk.get("outcomes", []):
                    name = outcome.get("description") or outcome.get("name", "")
                    point = outcome.get("point")
                    price = outcome.get("price")
                    side = (outcome.get("name") or "").lower()
                    if not name or point is None:
                        continue
                    # Collect over and under in two passes; use a simple per-name dict.
                    # This approach emits one prop per outcome (over/under separately);
                    # the caller merges by player_name + market + line.
                    if side == "over":
                        out.append(PlayerProp(
                            player_name=str(name),
                            market=market_key,
                            line=float(point),
                            over_price=float(price) if price else None,
                            under_price=None,
                        ))
                    elif side == "under":
                        out.append(PlayerProp(
                            player_name=str(name),
                            market=market_key,
                            line=float(point),
                            over_price=None,
                            under_price=float(price) if price else None,
                        ))

    if use_cache:
        cache_put(cache_key, params, {"rows": [p.__dict__ for p in out]})
    log.info("player_props_fetched", n=len(out))
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

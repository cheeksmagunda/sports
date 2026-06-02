"""Per-player minutes features from stats.wnba.com game logs (D55).

The minutes/role edge (D54): real_score = minutes x rate, and minutes is the
one signal orthogonal to card_boost. This module fetches the league's per-game
box logs once, reconstructs real_score per game via the locked formula
(predict.scoring), and produces as-of (walk-forward-safe) per-player features:

    recent_minutes : EWMA of recent minutes (the projection baseline)
    per_min_rate   : EWMA(real)/EWMA(min), the stable skill term
    minutes_vol    : std of recent minutes (drives sampling sigma)
    n_games        : prior games seen (drives the boost<->minutes blend weight)

Keyed by (first_initial, last_name, team) with a (first_initial, last_name)
fallback so job1 can match Real Sports pool players. Everything degrades to an
empty dict on any nba_api failure -- the picker then falls back to the boost
predictor, so a stats.wnba.com outage never blocks a fire.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from wnba_oracle.common.logging import get_logger
from wnba_oracle.predict.minutes import MinutesConfig, _ewma
from wnba_oracle.predict.scoring import box_to_real_score

log = get_logger("oracle.ingest.minutes_features")

_BOX_STATS = ("pts", "reb", "oreb", "dreb", "ast", "stl", "blk", "tov",
              "fgm", "fga", "fg3m", "ftm", "fta")


@dataclass(frozen=True)
class MinutesFeatures:
    recent_minutes: float
    per_min_rate: float
    minutes_vol: float
    n_games: int


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return s.strip().lower()


def _fetch_league_logs(season: str) -> list[dict]:
    """One league-wide PlayerGameLogs call. Raises on failure (caller catches)."""
    from nba_api.stats.endpoints import playergamelogs

    df = playergamelogs.PlayerGameLogs(
        season_nullable=season, league_id_nullable="10"
    ).get_data_frames()[0]
    return df.to_dict("records")


def _std(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = sum(vals) / len(vals)
    return (sum((v - m) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5


def build_minutes_features(
    *,
    as_of_date: str,
    seasons: list[str],
    cfg: MinutesConfig = MinutesConfig(),
) -> dict[tuple[str, str, str], MinutesFeatures]:
    """Build per-player minutes features from games STRICTLY BEFORE as_of_date.

    Returns {(initial, last, team): MinutesFeatures}. Also inserts a
    (initial, last, "") fallback key (team-agnostic) for each player. Empty
    dict on any fetch failure.
    """
    rows: list[dict] = []
    for season in seasons:
        try:
            rows.extend(_fetch_league_logs(season))
        except Exception as exc:
            log.warning("minutes_logs_fetch_failed", season=season, error=str(exc)[:120])
    if not rows:
        log.warning("minutes_features_empty", as_of_date=as_of_date)
        return {}

    # Group prior games per (initial, last, team), most-recent-first.
    by_player: dict[tuple[str, str, str], list[dict]] = {}
    for r in rows:
        gd = str(r.get("GAME_DATE", ""))[:10]
        if not gd or gd >= as_of_date:  # walk-forward: only games before the slate
            continue
        try:
            mins = float(r.get("MIN") or 0.0)
        except (TypeError, ValueError):
            continue
        if mins <= 0:
            continue
        name = str(r.get("PLAYER_NAME", ""))
        initial = _norm(name)[:1]
        last = _norm(name.split()[-1]) if name.strip() else ""
        team = str(r.get("TEAM_ABBREVIATION", "")).upper()
        if not last:
            continue
        box = {s: float(r.get(s.upper()) or 0.0) for s in _BOX_STATS}
        rec = {"date": gd, "min": mins, "real": box_to_real_score(box)}
        by_player.setdefault((initial, last, team), []).append(rec)

    out: dict[tuple[str, str, str], MinutesFeatures] = {}
    for (initial, last, team), games in by_player.items():
        games.sort(key=lambda g: g["date"], reverse=True)  # most-recent-first
        min_series = [g["min"] for g in games]
        reals = [g["real"] for g in games]
        rec_min, _ = _ewma(min_series, cfg.half_life)
        r_mean, _ = _ewma(reals, cfg.half_life)
        m_mean, _ = _ewma(min_series, cfg.half_life)
        rate = cfg.league_rate if m_mean <= 0 else min(cfg.max_rate, max(cfg.min_rate, r_mean / m_mean))
        feat = MinutesFeatures(
            recent_minutes=rec_min,
            per_min_rate=rate,
            minutes_vol=_std(min_series[:8]),
            n_games=len(games),
        )
        out[(initial, last, team)] = feat
        # team-agnostic fallback (keep the one with more games on collision)
        key = (initial, last, "")
        if key not in out or out[key].n_games < feat.n_games:
            out[key] = feat
    log.info("minutes_features_built", as_of_date=as_of_date, n_players=len(by_player))
    return out


def lookup(
    feats: dict[tuple[str, str, str], MinutesFeatures],
    *,
    display_name: str,
    team: str,
) -> MinutesFeatures | None:
    """Match a Real Sports pool player to their minutes features."""
    initial = _norm(display_name)[:1]
    parts = _norm(display_name).split()
    last = parts[-1] if parts else ""
    if not last:
        return None
    return feats.get((initial, last, team.upper())) or feats.get((initial, last, ""))

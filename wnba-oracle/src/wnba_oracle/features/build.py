"""Slate feature matrix builder.

`build_slate_features(slate_date, pool, game_logs, team_stats, odds,
lineups, resolver)` joins all per-player inputs into a single DataFrame
keyed by (slate_date, platform_player_id).

The output passes the pre-game allowlist gate
(`assert_predict_features_allowed(df.columns)`) before being handed to
the predict pipeline. Identical code paths back the training pipeline
so train-serve parity is mechanical (see `features.parity`).
"""

from __future__ import annotations

from collections.abc import Iterable

import polars as pl

from wnba_oracle.common.logging import get_logger
from wnba_oracle.features.allowlist import assert_predict_features_allowed
from wnba_oracle.features.injury_cascade import (
    CascadeConfig,
    CascadeInput,
    redistribute_minutes,
)
from wnba_oracle.features.rolling import build_rolling_features
from wnba_oracle.features.spec import cohort_for_position
from wnba_oracle.ingest.identity import Resolver
from wnba_oracle.ingest.odds import GameOdds
from wnba_oracle.ingest.realsports import PlatformPlayer
from wnba_oracle.ingest.rotowire import LineupEntry

log = get_logger("oracle.features.build")


def build_slate_features(
    slate_date: str,
    pool: list[PlatformPlayer],
    *,
    game_logs_by_player: dict[int, pl.DataFrame],
    team_stats: pl.DataFrame,
    odds: list[GameOdds],
    lineups: Iterable[LineupEntry],
    resolver: Resolver,
) -> pl.DataFrame:
    """Assemble the slate's feature matrix.

    Returns one row per drafted-eligible player (after identity resolution).
    Players we cannot resolve to a stats.wnba.com id are dropped and logged
    via `Resolver.write_unresolved_log`. Players with zero historical games
    are kept with zero-filled rolling features; the LightGBM categorical
    embedding for player_id and the EB baseline absorb the rookie prior.
    """
    # 1) Resolve identity for each pool entry.
    rows: list[dict[str, object]] = []
    unresolved: list[dict[str, object]] = []
    for p in pool:
        pid = resolver.resolve(
            real_sports_id=p.platform_id,
            display_name=p.display_name,
            first_name=p.first_name,
            last_name=p.last_name,
            team=p.team,
        )
        if pid is None:
            unresolved.append(
                {
                    "real_sports_id": p.platform_id,
                    "display_name": p.display_name,
                    "team": p.team,
                }
            )
            continue
        rows.append(
            {
                "slate_date": slate_date,
                "player_id": int(pid),
                "platform_player_id": p.platform_id,
                "team": p.team,
                "position": p.position,
                "cohort": cohort_for_position(p.position),
                "card_boost": float(p.multiplier_bonus),
                "primary_ranking": int(p.primary_ranking) if p.primary_ranking is not None else None,
            }
        )
    if unresolved:
        log.info("identity_unresolved", n=len(unresolved))
    if not rows:
        return pl.DataFrame()

    base = pl.from_dicts(rows)

    # 2) Compute per-player rolling features from each player's game log.
    rolling_rows: list[pl.DataFrame] = []
    for _pid, log_df in game_logs_by_player.items():
        if log_df is None or log_df.is_empty():
            continue
        roll = build_rolling_features(log_df, as_of_date=slate_date)
        if roll.is_empty():
            continue
        rolling_rows.append(roll)
    rolling = pl.concat(rolling_rows, how="vertical") if rolling_rows else pl.DataFrame(
        {"player_id": []}
    )
    if not rolling.is_empty():
        base = base.join(rolling, on="player_id", how="left")

    # 2b) Injury-cascade minutes redistribution. RotoWire surfaces an
    # `injury_status` per starter ("IL" / "OUT" / "GTD" / "" etc); we
    # treat IL/OUT as donors. Same-cohort teammates inherit the freed
    # minutes inversely weighted by their current minutes. Each
    # recipient's mins_l10 is bumped by the cascade bonus before the
    # picker reads it. See DECISIONS D29.
    cascade_rows = _build_cascade_inputs(base, lineups)
    cascade_bonuses = redistribute_minutes(cascade_rows, CascadeConfig())
    if cascade_bonuses and "mins_l10" in base.columns:
        bonuses_map: dict[int, float] = {int(k): float(v) for k, v in cascade_bonuses.items()}

        def _bonus_lookup(pid: object) -> float:
            if not isinstance(pid, (int, str)):
                return 0.0
            try:
                return bonuses_map.get(int(pid), 0.0)
            except (TypeError, ValueError):
                return 0.0

        base = base.with_columns(
            pl.col("player_id")
            .map_elements(_bonus_lookup, return_dtype=pl.Float64)
            .alias("_cascade_bonus")
        ).with_columns(
            (pl.col("mins_l10") + pl.col("_cascade_bonus")).alias("mins_l10")
        ).drop("_cascade_bonus")

    # 3) Team / opponent context.
    team_lookup, opp_pace_map, _ = _team_lookup_from_stats(team_stats)
    base = base.with_columns(
        [
            pl.col("team").map_elements(
                lambda t: team_lookup.get(str(t), {}).get("pace", 0.0),
                return_dtype=pl.Float64,
            ).alias("team_pace"),
            pl.col("team").map_elements(
                lambda t: team_lookup.get(str(t), {}).get("off_rating", 0.0),
                return_dtype=pl.Float64,
            ).alias("team_off_rtg"),
            pl.col("team").map_elements(
                lambda t: team_lookup.get(str(t), {}).get("def_rating", 0.0),
                return_dtype=pl.Float64,
            ).alias("team_def_rtg"),
        ]
    )

    # 4) Odds + lineup overlays via team key.
    odds_by_team = _odds_by_team(odds)
    base = base.with_columns(
        [
            pl.col("team").map_elements(
                lambda t: odds_by_team.get(str(t), {}).get("opponent", ""),
                return_dtype=pl.String,
            ).alias("opponent"),
            pl.col("team").map_elements(
                lambda t: 1 if odds_by_team.get(str(t), {}).get("is_home", False) else 0,
                return_dtype=pl.Int64,
            ).alias("is_home"),
            pl.col("team").map_elements(
                lambda t: _as_float(odds_by_team.get(str(t), {}).get("total", 0.0)),
                return_dtype=pl.Float64,
            ).alias("vegas_total"),
            pl.col("team").map_elements(
                lambda t: _as_float(odds_by_team.get(str(t), {}).get("spread", 0.0)),
                return_dtype=pl.Float64,
            ).alias("vegas_spread"),
        ]
    ).with_columns(
        # Implied team total = (vegas_total - vegas_spread) / 2; positive
        # spread is the underdog so subtract.
        (
            (pl.col("vegas_total") - pl.col("vegas_spread")) / pl.lit(2.0)
        ).alias("implied_team_total"),
        pl.lit(0.0).alias("home_moneyline"),
        pl.lit(0.0).alias("away_moneyline"),
    )

    # Opponent pace + def rtg via opponent team key.
    base = base.with_columns(
        [
            pl.col("opponent").map_elements(
                lambda t: opp_pace_map.get(str(t), 0.0),
                return_dtype=pl.Float64,
            ).alias("opp_pace"),
            pl.col("opponent").map_elements(
                lambda t: team_lookup.get(str(t), {}).get("off_rating", 0.0),
                return_dtype=pl.Float64,
            ).alias("opp_off_rtg"),
            pl.col("opponent").map_elements(
                lambda t: team_lookup.get(str(t), {}).get("def_rating", 0.0),
                return_dtype=pl.Float64,
            ).alias("opp_def_rtg"),
        ]
    ).with_columns(
        ((pl.col("team_pace") + pl.col("opp_pace")) / pl.lit(2.0)).alias(
            "game_pace_implied"
        ),
        pl.lit(0.0).alias("opp_dvp_guard"),
        pl.lit(0.0).alias("opp_dvp_forward"),
        pl.lit(0.0).alias("opp_dvp_center"),
        pl.lit(0).alias("team_l10_wins"),
        pl.lit(0).alias("opp_l10_wins"),
    )

    # 5) Lineup overlay
    lineups_idx: dict[tuple[str, str], LineupEntry] = {}
    for entry in lineups:
        lineups_idx[(entry.team, entry.player_name.lower())] = entry

    pool_by_pid = {p.platform_id: p for p in pool}

    def _conf_starter(s: dict) -> int:
        return _starter_flag(s, lineups_idx, pool_by_pid, want_confirmed=True)

    def _exp_starter(s: dict) -> int:
        return _starter_flag(s, lineups_idx, pool_by_pid, want_confirmed=False)

    def _slot(s: dict) -> int:
        return _starter_slot(s, lineups_idx, pool_by_pid)

    base = base.with_columns(
        [
            pl.struct(["team", "platform_player_id"]).map_elements(
                _conf_starter, return_dtype=pl.Int64
            ).alias("is_confirmed_starter"),
            pl.struct(["team", "platform_player_id"]).map_elements(
                _exp_starter, return_dtype=pl.Int64
            ).alias("is_expected_starter"),
            pl.struct(["team", "platform_player_id"]).map_elements(
                _slot, return_dtype=pl.Int64
            ).alias("starter_slot"),
        ]
    ).with_columns(pl.lit(0).alias("is_injury_flag"))

    # 6) Schedule context (deferred: needs a separate ingest of the WNBA
    # schedule). Zero-fill for now; Step 8 wires the schedule fetch.
    base = base.with_columns(
        [
            pl.lit(2).alias("days_rest"),
            pl.lit(0).alias("is_back_to_back"),
            pl.lit(0).alias("season_game_number"),
            pl.lit(0.0).alias("travel_distance_miles"),
            pl.lit("").alias("team_starter_status"),
            # Season-wide aggregates - zero-fill placeholders (populated by
            # joining with fetch_player_season_averages output in Step 6).
            pl.lit(0.0).alias("ts_pct"),
            pl.lit(0.0).alias("efg_pct"),
            pl.lit(0.0).alias("usg_pct"),
            pl.lit(0.0).alias("ast_pct"),
            pl.lit(0.0).alias("tov_pct"),
            pl.lit(0.0).alias("oreb_pct"),
            pl.lit(0.0).alias("dreb_pct"),
            pl.lit(0.0).alias("stl_pct"),
            pl.lit(0.0).alias("blk_pct"),
            pl.lit(0.0).alias("per"),
            pl.lit(0.0).alias("bpm"),
            pl.lit(0.0).alias("pie"),
            pl.lit(0.0).alias("fg3a_rate"),
            pl.lit(0.0).alias("ftr"),
        ]
    )

    # Fill nulls for any missing rolling cols so the matrix is rectangular.
    base = base.fill_null(0.0)

    # Verify the result against the pre-game allowlist.
    assert_predict_features_allowed(base.columns)
    return base


_OUT_STATUS_TOKENS = {"OUT", "IL", "INJ", "NA", "INACTIVE"}


def _build_cascade_inputs(
    base: pl.DataFrame,
    lineups: Iterable[LineupEntry],
) -> list[CascadeInput]:
    """Cross-join the slate's per-player base frame against RotoWire's
    starter list to flag OUT donors + collect minutes for recipients.

    Players not in the lineup list are assumed available with their
    current mins_l10. Players whose RotoWire `injury_status` matches a
    common OUT marker (IL, OUT, INJ, NA, INACTIVE) are donors. Other
    statuses (GTD, DTD, P, Q) are treated as available - they may sit
    last minute but the cascade fires only on confirmed OUT.
    """
    if base.is_empty() or "player_id" not in base.columns:
        return []
    # name -> RotoWire entry (lower-cased for case-insensitive lookup)
    by_team_name: dict[tuple[str, str], LineupEntry] = {}
    for entry in lineups:
        by_team_name[(entry.team, entry.player_name.lower())] = entry

    out: list[CascadeInput] = []
    mins_col = "mins_l10" if "mins_l10" in base.columns else None
    for row in base.iter_rows(named=True):
        pid = row.get("player_id")
        team = str(row.get("team", "") or "")
        position = str(row.get("position", "") or "")
        if pid is None or not team:
            continue
        mins_l10 = float(row.get(mins_col, 0.0) or 0.0) if mins_col else 0.0
        # Look up RotoWire injury_status by team + name. We have
        # display_name on the pool but not here. Heuristic: scan all
        # lineup entries for this team and pick the one matching position.
        is_out = False
        for (lt, _ln), entry in by_team_name.items():
            if lt != team:
                continue
            status = (entry.injury_status or "").strip().upper()
            if not status:
                continue
            if any(tok in status for tok in _OUT_STATUS_TOKENS):
                is_out = True
                break
        out.append(
            CascadeInput(
                player_id=int(pid),
                team=team,
                position=position,
                minutes_l10=mins_l10,
                is_out=is_out,
            )
        )
    return out


def _team_lookup_from_stats(
    team_stats: pl.DataFrame,
) -> tuple[dict[str, dict[str, float]], dict[str, float], list[str]]:
    if team_stats.is_empty():
        return {}, {}, []
    cols = team_stats.columns
    # nba_api LeagueDashTeamStats Advanced returns TEAM_ABBREVIATION + PACE + OFF_RATING + DEF_RATING
    team_col = "TEAM_ABBREVIATION" if "TEAM_ABBREVIATION" in cols else "TEAM_NAME"
    lookup: dict[str, dict[str, float]] = {}
    for row in team_stats.iter_rows(named=True):
        key = str(row.get(team_col, "")).strip().upper()
        if not key:
            continue
        lookup[key] = {
            "pace": float(row.get("PACE", 0.0) or 0.0),
            "off_rating": float(row.get("OFF_RATING", 0.0) or 0.0),
            "def_rating": float(row.get("DEF_RATING", 0.0) or 0.0),
        }
    opp_pace = {k: v["pace"] for k, v in lookup.items()}
    return lookup, opp_pace, list(lookup.keys())


def _odds_by_team(odds: list[GameOdds]) -> dict[str, dict[str, object]]:
    """The Odds API returns full team names ("Las Vegas Aces"). We coarsely
    map by uppercase-startswith-team-key. Step 8 hardens this with a
    team-name → abbreviation table."""
    by_team: dict[str, dict[str, object]] = {}
    for g in odds:
        home_key = team_key_from_full_name(g.home_team)
        away_key = team_key_from_full_name(g.away_team)
        by_team[home_key] = {
            "opponent": away_key,
            "is_home": True,
            "total": g.total_point,
            "spread": g.spread_home_point,
        }
        by_team[away_key] = {
            "opponent": home_key,
            "is_home": False,
            "total": g.total_point,
            "spread": g.spread_away_point,
        }
    return by_team


WNBA_TEAM_NAME_TO_KEY: dict[str, str] = {
    "Las Vegas Aces": "LVA",
    "New York Liberty": "NYL",
    "Phoenix Mercury": "PHO",
    "Chicago Sky": "CHI",
    "Toronto Tempo": "TOR",
    "Minnesota Lynx": "MIN",
    "Atlanta Dream": "ATL",
    "Indiana Fever": "IND",
    "Connecticut Sun": "CON",
    "Dallas Wings": "DAL",
    "Los Angeles Sparks": "LAS",
    "Seattle Storm": "SEA",
    "Washington Mystics": "WAS",
    "Golden State Valkyries": "GSV",
}


def team_key_from_full_name(name: str) -> str:
    if name in WNBA_TEAM_NAME_TO_KEY:
        return WNBA_TEAM_NAME_TO_KEY[name]
    return name[:3].upper()


def _as_float(x: object) -> float:
    if x is None:
        return 0.0
    try:
        return float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _starter_flag(
    s: dict,
    lineup_idx: dict[tuple[str, str], LineupEntry],
    pool_by_pid: dict[str, PlatformPlayer],
    *,
    want_confirmed: bool,
) -> int:
    team = str(s.get("team", ""))
    pid = str(s.get("platform_player_id", ""))
    pool_match = pool_by_pid.get(pid)
    if pool_match is None:
        return 0
    name = pool_match.display_name.lower()
    entry = lineup_idx.get((team, name))
    if entry is None:
        return 0
    if want_confirmed:
        return 1 if entry.confirmed else 0
    return 1


def _starter_slot(
    s: dict,
    lineup_idx: dict[tuple[str, str], LineupEntry],
    pool_by_pid: dict[str, PlatformPlayer],
) -> int:
    team = str(s.get("team", ""))
    pid = str(s.get("platform_player_id", ""))
    pool_match = pool_by_pid.get(pid)
    if pool_match is None:
        return 0
    name = pool_match.display_name.lower()
    entry = lineup_idx.get((team, name))
    return int(entry.starter_slot) if entry else 0

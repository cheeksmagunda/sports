"""Append completed WNBA games from ``wnba_game_logs`` rows into matchup corpus.

Reads an offline CSV (``scripts/export_game_logs.py``) or stdin-shaped rows and
groups by ``game_id`` / date. Does not call nba_api or Real Sports. Nightly
path: export after dayclose game_log_refresh, then append into the durable
corpus root (``backups`` branch or dedicated corpus repo).
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from oracle_core.corpus_matchup import GameMatchupRecord, append_completed_game

BOX_KEYS = (
    "min",
    "pts",
    "reb",
    "oreb",
    "dreb",
    "ast",
    "stl",
    "blk",
    "tov",
    "fgm",
    "fga",
    "fg3m",
    "ftm",
    "fta",
)


def _float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _team_sides(rows: list[Mapping[str, Any]]) -> tuple[str | None, str | None]:
    home: str | None = None
    away: str | None = None
    for row in rows:
        team = str(row.get("team") or "").strip().upper() or None
        home_away = str(row.get("home_away") or "").strip().lower()
        if home_away in {"h", "home"} and team:
            home = team
        elif home_away in {"a", "away"} and team:
            away = team
    if home is None or away is None:
        # Fall back to first row team + opponent when home_away is missing.
        sample = rows[0]
        team = str(sample.get("team") or "").strip().upper() or None
        opp = str(sample.get("opponent") or "").strip().upper() or None
        ha = str(sample.get("home_away") or "").strip().lower()
        if ha in {"h", "home"}:
            home, away = team, opp
        elif ha in {"a", "away"}:
            home, away = opp, team
        else:
            home, away = team, opp
    return home, away


def matchup_from_game_log_rows(
    rows: list[Mapping[str, Any]],
    *,
    captured_at: str | None = None,
) -> tuple[GameMatchupRecord, dict[str, Any]]:
    if not rows:
        raise ValueError("empty_game_log_group")
    sample = rows[0]
    game_id = str(sample.get("game_id") or "").strip()
    if not game_id:
        # Synthetic key when GAME_ID was historically null.
        game_id = f"{sample.get('game_date')}_{sample.get('team')}_{sample.get('opponent')}"
    season = str(sample.get("season") or "").strip() or "unknown"
    home, away = _team_sides(rows)
    home_pts = sum(
        _float(r.get("pts")) or 0.0 for r in rows if str(r.get("team") or "").upper() == home
    )
    away_pts = sum(
        _float(r.get("pts")) or 0.0 for r in rows if str(r.get("team") or "").upper() == away
    )
    # Possessions proxy: FGA - OREB + TOV + 0.44*FTA, averaged across teams when present.
    pace = None
    poss_by_team: dict[str, float] = defaultdict(float)
    for row in rows:
        team = str(row.get("team") or "").strip().upper()
        if not team:
            continue
        fga = _float(row.get("fga")) or 0.0
        oreb = _float(row.get("oreb")) or 0.0
        tov = _float(row.get("tov")) or 0.0
        fta = _float(row.get("fta")) or 0.0
        poss_by_team[team] += fga - oreb + tov + 0.44 * fta
    if len(poss_by_team) >= 2:
        pace = round(sum(poss_by_team.values()) / len(poss_by_team), 3)

    record = GameMatchupRecord(
        sport="wnba",
        season=season,
        game_id=game_id,
        home_team=home,
        away_team=away,
        is_final=True,
        source="wnba_game_logs",
        captured_at=captured_at or datetime.now(tz=UTC).isoformat(),
        game_date=str(sample.get("game_date") or "") or None,
        home_score=home_pts,
        away_score=away_pts,
        pace=pace,
        box_lines={
            "home_pts": home_pts,
            "away_pts": away_pts,
            "n_player_rows": len(rows),
            "possessions_by_team": dict(poss_by_team),
        },
    )
    stats = {
        "game_id": game_id,
        "season": season,
        "game_date": sample.get("game_date"),
        "players": [
            {
                "player_id": row.get("player_id"),
                "player_name": row.get("player_name"),
                "team": row.get("team"),
                "opponent": row.get("opponent"),
                "home_away": row.get("home_away"),
                **{key: _float(row.get(key)) for key in BOX_KEYS},
            }
            for row in rows
        ],
    }
    return record, stats


def group_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        game_id = str(row.get("game_id") or "").strip()
        if not game_id:
            game_id = f"{row.get('game_date')}_{row.get('team')}_{row.get('opponent')}"
        grouped[game_id].append(row)
    return grouped


def append_from_csv(csv_path: Path, out_root: Path) -> dict[str, int]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        grouped = group_rows(reader)
    appended = unchanged = errors = 0
    for _game_id, rows in sorted(grouped.items()):
        try:
            record, stats = matchup_from_game_log_rows(list(rows))
            result = append_completed_game(out_root, matchup=record, stats=stats)
        except (TypeError, ValueError):
            errors += 1
            continue
        if result.wrote_matchup or result.wrote_stats:
            appended += 1
        else:
            unchanged += 1
    return {
        "games": len(grouped),
        "appended": appended,
        "unchanged": unchanged,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--game-logs-csv",
        type=Path,
        required=True,
        help="CSV from scripts/export_game_logs.py",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        required=True,
        help="Durable matchup corpus root ({sport}/{season}/{game_id}/)",
    )
    args = parser.parse_args(argv)
    summary = append_from_csv(args.game_logs_csv, args.out_root)
    print(
        "wnba matchup append: "
        f"games={summary['games']} appended={summary['appended']} "
        f"unchanged={summary['unchanged']} errors={summary['errors']}"
    )
    return 0 if summary["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

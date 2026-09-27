"""Derive matchup.json sidecars from existing NFL Corpus G game dirs.

Offline only: reads local ``stats.json`` + ``feed.json`` (or ``feed_all.json``)
already on disk and appends a durable matchup record via oracle-core. Does not
call Real Sports. Nightly wiring belongs after PR #512 Corpus G coverage.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from oracle_core.corpus_matchup import GameMatchupRecord, append_completed_game


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else None


def _feed_game(feed: dict[str, Any] | None) -> dict[str, Any]:
    if not feed:
        return {}
    game = feed.get("game")
    return game if isinstance(game, dict) else {}


def matchup_from_corpus_g_game(
    game_dir: Path,
    *,
    season: str | int,
    game_id: str | int,
    captured_at: str | None = None,
) -> tuple[GameMatchupRecord, dict[str, Any] | None]:
    """Build a matchup record + optional stats payload from one Corpus G dir."""

    stats = _load_json(game_dir / "stats.json")
    feed = _load_json(game_dir / "feed.json") or _load_json(game_dir / "feed_all.json")
    game = _feed_game(feed)
    box = stats.get("gameBoxScore") if isinstance(stats, dict) else None
    box = box if isinstance(box, dict) else {}

    home_team = (
        game.get("homeTeamKey")
        or game.get("homeTeam")
        or (str(game["homeTeamId"]) if game.get("homeTeamId") is not None else None)
    )
    away_team = (
        game.get("awayTeamKey")
        or game.get("awayTeam")
        or (str(game["awayTeamId"]) if game.get("awayTeamId") is not None else None)
    )
    status = str(game.get("status") or game.get("gameStatus") or "").lower()
    is_final = status in {"final", "closed", "complete", "completed"} or bool(
        box.get("homeScore") is not None and box.get("awayScore") is not None
    )
    pace = None
    if game.get("pace") is not None:
        try:
            pace = float(game["pace"])
        except (TypeError, ValueError):
            pace = None

    record = GameMatchupRecord(
        sport="nfl",
        season=str(season),
        game_id=str(game_id),
        home_team=str(home_team) if home_team is not None else None,
        away_team=str(away_team) if away_team is not None else None,
        is_final=is_final,
        source="corpus_g",
        captured_at=captured_at or datetime.now(tz=UTC).isoformat(),
        game_date=str(game.get("day") or "") or None,
        home_score=box.get("homeScore"),
        away_score=box.get("awayScore"),
        pace=pace,
        venue=str(game.get("venue") or game.get("venueName") or "") or None,
        box_lines={
            "home_score": box.get("homeScore"),
            "away_score": box.get("awayScore"),
            "n_player_box_scores": len(list((stats or {}).get("playerBoxScores") or [])),
        },
        extra={
            "week": game.get("week"),
            "home_team_id": game.get("homeTeamId"),
            "away_team_id": game.get("awayTeamId"),
        },
    )
    return record, stats


def append_from_corpus_g_root(
    corpus_g_root: Path,
    out_root: Path,
    *,
    seasons: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Walk Corpus G seasons and append matchup sidecars into ``out_root``."""

    results: list[dict[str, Any]] = []
    if not corpus_g_root.is_dir():
        return results
    season_dirs = sorted(p for p in corpus_g_root.iterdir() if p.is_dir())
    for season_dir in season_dirs:
        if seasons is not None and season_dir.name not in seasons:
            continue
        for game_path in sorted(p for p in season_dir.iterdir() if p.is_dir()):
            try:
                record, stats = matchup_from_corpus_g_game(
                    game_path, season=season_dir.name, game_id=game_path.name
                )
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                results.append(
                    {
                        "season": season_dir.name,
                        "game_id": game_path.name,
                        "status": "error",
                        "error": type(exc).__name__,
                    }
                )
                continue
            if not record.is_final:
                results.append(
                    {
                        "season": season_dir.name,
                        "game_id": game_path.name,
                        "status": "skipped_non_final",
                    }
                )
                continue
            append = append_completed_game(out_root, matchup=record, stats=stats)
            status = "appended" if append.wrote_matchup or append.wrote_stats else "unchanged"
            results.append(
                {
                    "season": append.season,
                    "game_id": append.game_id,
                    "status": status,
                    "wrote_matchup": append.wrote_matchup,
                    "wrote_stats": append.wrote_stats,
                }
            )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus-g-root",
        type=Path,
        required=True,
        help="Existing NFL Corpus G root (data/raw/corpus_g)",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        required=True,
        help="Durable matchup corpus root ({sport}/{season}/{game_id}/)",
    )
    parser.add_argument(
        "--season",
        action="append",
        dest="seasons",
        help="Optional season filter (repeatable)",
    )
    args = parser.parse_args(argv)
    rows = append_from_corpus_g_root(args.corpus_g_root, args.out_root, seasons=args.seasons)
    appended = sum(1 for row in rows if row.get("status") == "appended")
    unchanged = sum(1 for row in rows if row.get("status") == "unchanged")
    print(f"nfl matchup append: scanned={len(rows)} appended={appended} unchanged={unchanged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Append NHL public boxscore games into the durable matchup corpus.

Offline/adapter path: accepts a public NHL API boxscore JSON (already fetched
by ``nhl_oracle.history_loader``) and writes matchup+stats via oracle-core.
Does not mint credentials. Nightly: run after history-sync / #512-style append.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from oracle_core.corpus_matchup import GameMatchupRecord, append_completed_game

from nhl_oracle.history_loader import flatten_boxscore_player_rows


def _venue_name(boxscore: dict[str, Any]) -> str | None:
    venue = boxscore.get("venue")
    if isinstance(venue, dict):
        for key in ("default", "name", "fr"):
            value = venue.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
    if isinstance(venue, str) and venue.strip():
        return venue.strip()
    return None


def matchup_from_nhl_boxscore(
    boxscore: dict[str, Any],
    *,
    source_url: str = "nhl_public_boxscore",
    captured_at: str | None = None,
) -> tuple[GameMatchupRecord, dict[str, Any]]:
    away = boxscore.get("awayTeam")
    home = boxscore.get("homeTeam")
    if not isinstance(away, dict) or not isinstance(home, dict):
        raise ValueError("boxscore_team_payload_missing")
    game_id = boxscore.get("id")
    if game_id is None:
        raise ValueError("boxscore_game_id_missing")
    season_code = boxscore.get("season")
    season = str(season_code) if season_code is not None else "unknown"
    state = str(boxscore.get("gameState") or "").upper()
    is_final = state in {"OFF", "FINAL", "CLOSED"}
    stamp = captured_at or datetime.now(tz=UTC).isoformat()
    players = flatten_boxscore_player_rows(boxscore, fetched_at=stamp, source_url=source_url)
    record = GameMatchupRecord(
        sport="nhl",
        season=season,
        game_id=str(game_id),
        home_team=str(home.get("abbrev") or home.get("id") or "") or None,
        away_team=str(away.get("abbrev") or away.get("id") or "") or None,
        is_final=is_final,
        source="nhl_public_boxscore",
        captured_at=stamp,
        game_date=str(boxscore.get("gameDate") or "") or None,
        home_score=home.get("score"),
        away_score=away.get("score"),
        pace=None,  # NHL pace not on public boxscore; fill later from team metrics.
        venue=_venue_name(boxscore),
        box_lines={
            "home_score": home.get("score"),
            "away_score": away.get("score"),
            "n_player_rows": len(players),
            "game_state": state,
        },
        extra={"season_code": season_code, "game_type": boxscore.get("gameType")},
    )
    stats = {"game_id": game_id, "players": players, "source_url": source_url}
    return record, stats


def append_boxscore_file(path: Path, out_root: Path) -> dict[str, Any]:
    boxscore = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(boxscore, dict):
        raise ValueError("boxscore_not_object")
    record, stats = matchup_from_nhl_boxscore(boxscore, source_url=str(path))
    if not record.is_final:
        return {"status": "skipped_non_final", "game_id": record.game_id}
    result = append_completed_game(out_root, matchup=record, stats=stats)
    return {
        "status": "appended" if result.wrote_matchup or result.wrote_stats else "unchanged",
        "game_id": result.game_id,
        "season": result.season,
        "wrote_matchup": result.wrote_matchup,
        "wrote_stats": result.wrote_stats,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boxscore-json", type=Path, required=True)
    parser.add_argument("--out-root", type=Path, required=True)
    args = parser.parse_args(argv)
    summary = append_boxscore_file(args.boxscore_json, args.out_root)
    print(f"nhl matchup append: {summary}")
    return 0 if summary.get("status") != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())

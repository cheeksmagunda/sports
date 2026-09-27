"""NBA game-stats matchup corpus append scaffold.

NBA has no live Real Sports game-stat ingest on ``main`` yet. This CLI accepts
an offline completed-game payload (public box or future Corpus G shape) and
appends into the shared durable layout. Fail-closed when ``is_final`` is false.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from oracle_core.corpus_matchup import GameMatchupRecord, append_completed_game


def matchup_from_nba_payload(
    payload: dict[str, Any],
    *,
    captured_at: str | None = None,
) -> tuple[GameMatchupRecord, dict[str, Any]]:
    game_id = payload.get("game_id") or payload.get("gameId")
    if game_id is None:
        raise ValueError("nba_payload_missing_game_id")
    season = str(payload.get("season") or "unknown")
    home = payload.get("home_team") or payload.get("homeTeam")
    away = payload.get("away_team") or payload.get("awayTeam")
    is_final = bool(payload.get("is_final", payload.get("game_status") == "final"))
    record = GameMatchupRecord(
        sport="nba",
        season=season,
        game_id=str(game_id),
        home_team=str(home) if home is not None else None,
        away_team=str(away) if away is not None else None,
        is_final=is_final,
        source=str(payload.get("source") or "nba_offline_scaffold"),
        captured_at=captured_at or datetime.now(tz=UTC).isoformat(),
        game_date=str(payload.get("game_date") or "") or None,
        home_score=payload.get("home_score"),
        away_score=payload.get("away_score"),
        pace=_as_float(payload.get("pace")),
        venue=str(payload.get("venue") or "") or None,
        box_lines=payload.get("box_lines")
        if isinstance(payload.get("box_lines"), dict)
        else {
            "home_score": payload.get("home_score"),
            "away_score": payload.get("away_score"),
        },
    )
    stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else payload
    return record, stats


def _as_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload-json", type=Path, required=True)
    parser.add_argument("--out-root", type=Path, required=True)
    args = parser.parse_args(argv)
    payload = json.loads(args.payload_json.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        print("ERROR: payload must be a JSON object")
        return 1
    record, stats = matchup_from_nba_payload(payload)
    if not record.is_final:
        print("skipped_non_final")
        return 0
    result = append_completed_game(args.out_root, matchup=record, stats=stats)
    status = "appended" if result.wrote_matchup or result.wrote_stats else "unchanged"
    print(f"nba matchup append: status={status} game_id={result.game_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

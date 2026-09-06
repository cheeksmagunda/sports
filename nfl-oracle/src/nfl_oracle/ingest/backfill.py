"""Resumable season-by-season Corpus G backfill with coverage tracking."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from oracle_core.artifacts import atomic_write_json

from nfl_oracle.common.logging import configure_logging, get_logger
from nfl_oracle.ingest.corpus_g import CorpusGStore, GameIngestResult, ingest_game
from nfl_oracle.ingest.realsports import (
    StorageStateMissing,
    StorageStateStale,
    headers_or_capture,
)

log = get_logger("nfl_oracle.ingest.backfill")

DEFAULT_INTER_GAME_DELAY_S = 2.0

# Seed game ids for honest first-pass proofs. Not a full season census.
SEED_GAMES: dict[int, list[int]] = {
    2002: [126323],
    2014: [123127],
    2018: [122057],
    2022: [18000],
    2023: [18497],
    2024: [18800],
    2025: [19450, 19451],
}


@dataclass
class BackfillCursor:
    season: int | None = None
    last_game_id: int | None = None
    completed_game_ids: list[int] = field(default_factory=list)
    updated_at: str = ""


@dataclass
class CoverageCell:
    season: int
    game_id: int
    day: str | None
    status: str | None
    box_count: int
    value_nonnull: int
    player_count: int
    play_count: int
    paths: dict[str, str]
    ingested_at: str


def cursor_path(store: CorpusGStore) -> Path:
    return store.catalog_root / "backfill_cursor.json"


def coverage_matrix_path(store: CorpusGStore) -> Path:
    return store.catalog_root / "coverage_matrix.json"


def season_game_ids_path(store: CorpusGStore | None = None) -> Path:
    store = store or CorpusGStore()
    return store.catalog_root / "season_game_ids.json"


def load_cursor(store: CorpusGStore) -> BackfillCursor:
    path = cursor_path(store)
    if not path.is_file():
        return BackfillCursor()
    raw = json.loads(path.read_text(encoding="utf-8"))
    return BackfillCursor(
        season=raw.get("season"),
        last_game_id=raw.get("last_game_id"),
        completed_game_ids=list(raw.get("completed_game_ids") or []),
        updated_at=str(raw.get("updated_at") or ""),
    )


def save_cursor(store: CorpusGStore, cursor: BackfillCursor) -> None:
    cursor.updated_at = datetime.now(UTC).isoformat()
    atomic_write_json(cursor_path(store), asdict(cursor))


def load_coverage_matrix(store: CorpusGStore) -> dict[str, Any]:
    path = coverage_matrix_path(store)
    if not path.is_file():
        return {"generated_at": None, "seasons": {}, "gaps": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("coverage matrix must be a JSON object")
    return payload


def _upsert_coverage(store: CorpusGStore, cell: CoverageCell) -> None:
    matrix = load_coverage_matrix(store)
    seasons: dict[str, Any] = matrix.setdefault("seasons", {})
    season_key = str(cell.season)
    season_block = seasons.setdefault(season_key, {"games": {}})
    games: dict[str, Any] = season_block.setdefault("games", {})
    games[str(cell.game_id)] = asdict(cell)
    matrix["generated_at"] = datetime.now(UTC).isoformat()
    atomic_write_json(coverage_matrix_path(store), matrix)


def load_season_game_ids(
    season: int,
    *,
    catalog_path: Path | None = None,
    explicit: list[int] | None = None,
    store: CorpusGStore | None = None,
) -> list[int]:
    if explicit:
        return [int(x) for x in explicit]
    path = catalog_path or season_game_ids_path(store)
    if path.is_file():
        raw = json.loads(path.read_text(encoding="utf-8"))
        values = raw.get(str(season)) or raw.get(season) or []
        if values:
            return [int(x) for x in values]
    return list(SEED_GAMES.get(season, []))


async def backfill_season(
    *,
    season: int,
    game_ids: list[int],
    store: CorpusGStore | None = None,
    delay_s: float = DEFAULT_INTER_GAME_DELAY_S,
    resume: bool = True,
) -> list[GameIngestResult]:
    store = store or CorpusGStore()
    cursor = load_cursor(store) if resume else BackfillCursor()
    done = set(cursor.completed_game_ids if cursor.season == season else [])
    results: list[GameIngestResult] = []

    headers = await headers_or_capture()

    async def refresh() -> Any:
        return await headers_or_capture()

    async with httpx.AsyncClient(timeout=60.0) as client:
        for index, game_id in enumerate(game_ids):
            if game_id in done:
                log.info("skip_already_done", game_id=game_id, season=season)
                continue
            result = await ingest_game(
                game_id=game_id,
                store=store,
                client=client,
                headers=headers,
                refresh_headers=refresh,
                season_hint=season,
            )
            results.append(result)
            cell = CoverageCell(
                season=result.season if result.season is not None else season,
                game_id=result.game_id,
                day=result.day,
                status=result.status,
                box_count=result.box_count,
                value_nonnull=result.value_nonnull,
                player_count=result.player_count,
                play_count=result.play_count,
                paths={a.provenance.endpoint: str(a.path) for a in result.artifacts},
                ingested_at=datetime.now(UTC).isoformat(),
            )
            _upsert_coverage(store, cell)
            done.add(game_id)
            cursor = BackfillCursor(
                season=season,
                last_game_id=game_id,
                completed_game_ids=sorted(done),
            )
            save_cursor(store, cursor)
            log.info(
                "ingested_game",
                game_id=game_id,
                season=result.season,
                boxes=result.box_count,
                value=result.value_nonnull,
                plays=result.play_count,
                players=result.player_count,
                skipped=list(result.skipped_unchanged),
            )
            if index + 1 < len(game_ids) and delay_s > 0:
                await asyncio.sleep(delay_s)
                headers = await headers_or_capture()
    return results


def backfill_season_sync(**kwargs: Any) -> list[GameIngestResult]:
    return asyncio.run(backfill_season(**kwargs))


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="Resumable Corpus G season backfill")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--game-id", type=int, action="append", default=None)
    parser.add_argument("--delay-s", type=float, default=DEFAULT_INTER_GAME_DELAY_S)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args(argv)
    game_ids = load_season_game_ids(args.season, explicit=args.game_id)
    if not game_ids:
        print(f"[BLOCK] no game ids for season {args.season}; pass --game-id", file=sys.stderr)
        return 2
    try:
        results = backfill_season_sync(
            season=args.season,
            game_ids=game_ids,
            delay_s=args.delay_s,
            resume=not args.no_resume,
        )
    except (StorageStateMissing, StorageStateStale) as exc:
        print(f"[BLOCK] {exc}", file=sys.stderr)
        return 78
    for result in results:
        print(
            f"game={result.game_id} season={result.season} day={result.day} "
            f"boxes={result.box_count} value={result.value_nonnull} "
            f"players={result.player_count} plays={result.play_count}"
        )
    store = CorpusGStore()
    print(f"coverage={coverage_matrix_path(store)}")
    print(f"cursor={cursor_path(store)}")
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())

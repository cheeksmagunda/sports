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
    2025: [19440, 19445, 19449, 19450, 19451],
    2024: [18790, 18800, 18810, 18900],
    2023: [18490, 18497, 18500, 18550],
    2022: [18000, 18010, 18050, 18100],
    2021: [17700, 17800, 17900, 17950],
    2018: [122050, 122057, 122060],
    2014: [123120, 123127, 123130],
    2003: [126320],
    2002: [126323, 126330],
}


@dataclass
class BackfillCursor:
    season: int | None = None
    last_game_id: int | None = None
    completed_game_ids: list[int] = field(default_factory=list)
    updated_at: str = ""


# Season-level coverage vocabulary for the matrix (not HTTP status).
SEASON_STATUS_KNOWN = "known"
SEASON_STATUS_UNKNOWN = "unknown"
SEASON_STATUS_BLOCKED = "blocked"

# Seasons we track in the matrix even before game ids are discovered.
TRACKED_SEASONS: tuple[int, ...] = tuple(range(2002, 2026))


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
    event_time: str | None = None
    source_available_at: str | None = None
    captured_at: str | None = None
    decision_at: str | None = None
    value_note: str | None = None


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


def _value_note_for_cell(cell: CoverageCell) -> str:
    if cell.box_count <= 0:
        return "no playerBoxScores observed"
    if cell.value_nonnull <= 0:
        return "boxes present but Real value all-null (not usable as label yet)"
    ratio = cell.value_nonnull / cell.box_count
    return (
        f"Real value present on {cell.value_nonnull}/{cell.box_count} boxes "
        f"({ratio:.0%}); usable as post-final training label only"
    )


def _summarize_season_block(season_key: str, season_block: dict[str, Any]) -> dict[str, Any]:
    games: dict[str, Any] = season_block.get("games") or {}
    explicit_status = season_block.get("status")
    if explicit_status == SEASON_STATUS_BLOCKED and not games:
        status = SEASON_STATUS_BLOCKED
    elif games:
        status = SEASON_STATUS_KNOWN
    else:
        status = explicit_status or SEASON_STATUS_UNKNOWN

    value_notes: list[str] = []
    total_boxes = 0
    total_value = 0
    for game in games.values():
        if not isinstance(game, dict):
            continue
        boxes = int(game.get("box_count") or 0)
        value = int(game.get("value_nonnull") or 0)
        total_boxes += boxes
        total_value += value
        note = game.get("value_note")
        if note:
            value_notes.append(f"game {game.get('game_id')}: {note}")
    if games and total_boxes > 0:
        season_value_note = (
            f"{len(games)} game(s) ingested; Real value on {total_value}/{total_boxes} boxes"
        )
    elif status == SEASON_STATUS_BLOCKED:
        season_value_note = str(
            season_block.get("value_note")
            or "blocked (auth/storage or provider refusal); no honest ingest"
        )
    else:
        season_value_note = str(
            season_block.get("value_note") or "no game ids discovered / ingested yet"
        )

    out = dict(season_block)
    out["status"] = status
    out["games"] = games
    out["games_ingested"] = len(games)
    out["value_note"] = season_value_note
    if value_notes:
        out["game_value_notes"] = value_notes
    out.setdefault("season", int(season_key) if season_key.isdigit() else season_key)
    return out


def ensure_season_skeleton(matrix: dict[str, Any]) -> dict[str, Any]:
    """Ensure tracked seasons exist with known/unknown/blocked status fields."""

    seasons: dict[str, Any] = matrix.setdefault("seasons", {})
    for season in TRACKED_SEASONS:
        key = str(season)
        block = seasons.setdefault(key, {"games": {}, "status": SEASON_STATUS_UNKNOWN})
        if "games" not in block or not isinstance(block.get("games"), dict):
            block["games"] = {}
        seasons[key] = _summarize_season_block(key, block)
    matrix["seasons"] = dict(sorted(seasons.items(), key=lambda kv: kv[0], reverse=True))
    matrix.setdefault("gaps", [])
    matrix["status_vocabulary"] = {
        SEASON_STATUS_KNOWN: "At least one Corpus G game ingested for the season",
        SEASON_STATUS_UNKNOWN: "No game ids discovered or ingested yet",
        SEASON_STATUS_BLOCKED: "Auth/storage missing/stale or provider systematically refused",
    }
    return matrix


def mark_season_blocked(store: CorpusGStore, season: int, reason: str) -> None:
    matrix = ensure_season_skeleton(load_coverage_matrix(store))
    key = str(season)
    block = matrix["seasons"].setdefault(key, {"games": {}})
    block["status"] = SEASON_STATUS_BLOCKED
    block["value_note"] = reason
    matrix["seasons"][key] = _summarize_season_block(key, block)
    matrix["generated_at"] = datetime.now(UTC).isoformat()
    gaps = matrix.setdefault("gaps", [])
    gap = {"season": season, "status": SEASON_STATUS_BLOCKED, "reason": reason}
    if gap not in gaps:
        gaps.append(gap)
    atomic_write_json(coverage_matrix_path(store), matrix)


def refresh_coverage_matrix(store: CorpusGStore) -> dict[str, Any]:
    matrix = ensure_season_skeleton(load_coverage_matrix(store))
    matrix["generated_at"] = datetime.now(UTC).isoformat()
    atomic_write_json(coverage_matrix_path(store), matrix)
    return matrix


def _upsert_coverage(store: CorpusGStore, cell: CoverageCell) -> None:
    matrix = ensure_season_skeleton(load_coverage_matrix(store))
    seasons: dict[str, Any] = matrix.setdefault("seasons", {})
    season_key = str(cell.season)
    season_block = seasons.setdefault(season_key, {"games": {}})
    games: dict[str, Any] = season_block.setdefault("games", {})
    cell_payload = asdict(cell)
    if not cell_payload.get("value_note"):
        cell_payload["value_note"] = _value_note_for_cell(cell)
    games[str(cell.game_id)] = cell_payload
    season_block["games"] = games
    season_block["status"] = SEASON_STATUS_KNOWN
    seasons[season_key] = _summarize_season_block(season_key, season_block)
    matrix["seasons"] = dict(sorted(seasons.items(), key=lambda kv: kv[0], reverse=True))
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
            ingested_at = datetime.now(UTC).isoformat()
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
                ingested_at=ingested_at,
                event_time=result.event_time,
                source_available_at=result.source_available_at,
                captured_at=result.captured_at or ingested_at,
                decision_at=result.decision_at,
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
    parser.add_argument("--season", type=int, required=False, default=None)
    parser.add_argument("--game-id", type=int, action="append", default=None)
    parser.add_argument("--delay-s", type=float, default=DEFAULT_INTER_GAME_DELAY_S)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument(
        "--refresh-matrix-only",
        action="store_true",
        help="Rewrite coverage_matrix.json season skeleton/statuses without network I/O",
    )
    args = parser.parse_args(argv)
    if args.refresh_matrix_only:
        store = CorpusGStore()
        matrix = refresh_coverage_matrix(store)
        print(f"coverage={coverage_matrix_path(store)}")
        for key, block in (matrix.get("seasons") or {}).items():
            print(f"season={key} status={block.get('status')} note={block.get('value_note')}")
        return 0
    if args.season is None:
        print("[BLOCK] --season is required unless --refresh-matrix-only", file=sys.stderr)
        return 2
    game_ids = load_season_game_ids(args.season, explicit=args.game_id)
    if not game_ids:
        print(f"[BLOCK] no game ids for season {args.season}; pass --game-id", file=sys.stderr)
        return 2
    store = CorpusGStore()
    refresh_coverage_matrix(store)
    try:
        results = backfill_season_sync(
            season=args.season,
            game_ids=game_ids,
            delay_s=args.delay_s,
            resume=not args.no_resume,
        )
    except (StorageStateMissing, StorageStateStale) as exc:
        mark_season_blocked(store, args.season, f"auth blocked: {exc}")
        print(f"[BLOCK] {exc}", file=sys.stderr)
        return 78
    for result in results:
        print(
            f"game={result.game_id} season={result.season} day={result.day} "
            f"boxes={result.box_count} value={result.value_nonnull} "
            f"players={result.player_count} plays={result.play_count} "
            f"event_time={result.event_time} source_available_at={result.source_available_at}"
        )
    matrix = refresh_coverage_matrix(store)
    season_block = (matrix.get("seasons") or {}).get(str(args.season), {})
    print(f"season_status={season_block.get('status')} value_note={season_block.get('value_note')}")
    print(f"coverage={coverage_matrix_path(store)}")
    print(f"cursor={cursor_path(store)}")
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())

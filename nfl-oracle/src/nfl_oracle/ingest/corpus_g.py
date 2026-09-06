"""Corpus G persistence for Real Sports NFL game payloads."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx
from oracle_core.artifacts import atomic_write_bytes, atomic_write_json, sha256_bytes

from nfl_oracle.common.paths import resolve_project_root
from nfl_oracle.ingest.clocks import (
    clock_field_docs,
    clocks_for_game,
    event_time_from_game,
    source_available_at_from_game,
)
from nfl_oracle.ingest.realsports import (
    BASE,
    SPORT,
    RequestHeaders,
    fetch_game_feed,
    fetch_game_players,
    fetch_game_stats,
)
from nfl_oracle.ingest.redact import assert_no_identity_leak, redact_corpus_payload

EndpointName = Literal["stats", "players", "feed"]

ENDPOINT_FILENAMES: dict[EndpointName, str] = {
    "stats": "stats.json",
    "players": "players.json",
    "feed": "feed.json",
}


@dataclass(frozen=True)
class Provenance:
    game_id: int
    season: int | None
    endpoint: EndpointName
    source_url: str
    content_sha256: str
    captured_at: str
    byte_len: int
    redacted: bool = True
    event_time: str | None = None
    source_available_at: str | None = None
    decision_at: str | None = None


@dataclass(frozen=True)
class StoredArtifact:
    path: Path
    provenance_path: Path
    provenance: Provenance
    wrote: bool


@dataclass(frozen=True)
class GameCoverageCounts:
    n_player_box_scores: int
    n_value_nonnull: int
    n_players: int
    n_plays: int
    game_day: str | None
    game_season: int | None
    game_status: str | None
    event_time: str | None = None
    source_available_at: str | None = None
    game: dict[str, Any] | None = None


@dataclass(frozen=True)
class GameIngestResult:
    game_id: int
    season: int | None
    day: str | None
    status: str | None
    box_count: int
    value_nonnull: int
    player_count: int
    play_count: int
    artifacts: tuple[StoredArtifact, ...]
    skipped_unchanged: tuple[str, ...]
    manifest_path: str = ""
    event_time: str | None = None
    source_available_at: str | None = None
    captured_at: str | None = None
    decision_at: str | None = None


def summarize_payloads(
    *,
    stats: dict[str, Any] | None,
    players: dict[str, Any] | None,
    feed: dict[str, Any] | None,
) -> GameCoverageCounts:
    boxes = list((stats or {}).get("playerBoxScores") or [])
    n_value = 0
    for row in boxes:
        if isinstance(row, dict) and row.get("value") is not None and str(row.get("value")).strip():
            n_value += 1
    player_rows = list((players or {}).get("players") or [])
    plays = list((feed or {}).get("plays") or [])
    game_raw = (feed or {}).get("game")
    game: dict[str, Any] = game_raw if isinstance(game_raw, dict) else {}
    season_raw = game.get("season")
    season: int | None
    try:
        season = int(season_raw) if season_raw is not None else None
    except (TypeError, ValueError):
        season = None
    return GameCoverageCounts(
        n_player_box_scores=len(boxes),
        n_value_nonnull=n_value,
        n_players=len(player_rows),
        n_plays=len(plays),
        game_day=str(game.get("day")) if game.get("day") else None,
        game_season=season,
        game_status=str(game.get("status")) if game.get("status") else None,
        event_time=event_time_from_game(game),
        source_available_at=source_available_at_from_game(game),
        game=game or None,
    )


class CorpusGStore:
    """Filesystem store for redacted Corpus G payloads."""

    def __init__(self, root: Path | str | None = None) -> None:
        if root is None or root == "":
            project = resolve_project_root(__file__)
        else:
            project = Path(root)
        self.project_root = project
        self.raw_root = project / "data" / "raw" / "corpus_g"
        self.catalog_root = project / "data" / "catalog"
        self.raw_root.mkdir(parents=True, exist_ok=True)
        self.catalog_root.mkdir(parents=True, exist_ok=True)

    @property
    def coverage_path(self) -> Path:
        return self.catalog_root / "coverage_matrix.json"

    @property
    def cursor_path(self) -> Path:
        return self.catalog_root / "backfill_cursor.json"

    def game_dir(self, season: int | None, game_id: int) -> Path:
        season_key = str(season) if season is not None else "unknown"
        path = self.raw_root / season_key / str(game_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def persist_endpoint(
        self,
        *,
        game_id: int,
        season: int | None,
        endpoint: EndpointName,
        payload: dict[str, Any],
        source_url: str,
        captured_at: datetime | None = None,
        event_time: str | None = None,
        source_available_at: str | None = None,
        decision_at: str | None = None,
    ) -> StoredArtifact:
        redacted = redact_corpus_payload(payload)
        assert_no_identity_leak(redacted)
        body = json.dumps(
            redacted, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        digest = sha256_bytes(body)
        captured = (captured_at or datetime.now(UTC)).isoformat().replace("+00:00", "Z")
        prov = Provenance(
            game_id=game_id,
            season=season,
            endpoint=endpoint,
            source_url=source_url,
            content_sha256=digest,
            captured_at=captured,
            byte_len=len(body),
            event_time=event_time,
            source_available_at=source_available_at,
            decision_at=decision_at,
        )
        directory = self.game_dir(season, game_id)
        payload_path = directory / ENDPOINT_FILENAMES[endpoint]
        provenance_path = directory / f"{ENDPOINT_FILENAMES[endpoint]}.provenance.json"
        wrote = True
        if payload_path.is_file() and provenance_path.is_file():
            existing = json.loads(provenance_path.read_text(encoding="utf-8"))
            if existing.get("content_sha256") == digest:
                wrote = False
        if wrote:
            atomic_write_bytes(payload_path, body)
            atomic_write_json(provenance_path, asdict(prov))
        return StoredArtifact(
            path=payload_path,
            provenance_path=provenance_path,
            provenance=prov,
            wrote=wrote,
        )

    def write_manifest(self, result: GameIngestResult) -> Path:
        directory = self.game_dir(result.season, result.game_id)
        path = directory / "manifest.json"
        clocks = clocks_for_game(
            None,
            captured_at=result.captured_at,
            decision_at=result.decision_at,
        )
        # Prefer clocks already resolved on the ingest result (from feed.game).
        clocks["event_time"] = result.event_time
        clocks["source_available_at"] = result.source_available_at
        payload = {
            "corpus": "G",
            "sport": "nfl",
            "game_id": result.game_id,
            "season": result.season,
            "day": result.day,
            "status": result.status,
            "host": BASE,
            "read_only": True,
            "clocks": clocks,
            "clock_field_docs": clock_field_docs(),
            "coverage": {
                "n_player_box_scores": result.box_count,
                "n_value_nonnull": result.value_nonnull,
                "n_players": result.player_count,
                "n_plays": result.play_count,
            },
            "artifacts": [
                {
                    "endpoint": item.provenance.endpoint,
                    "path": str(item.path),
                    "sha256": item.provenance.content_sha256,
                    "bytes": item.provenance.byte_len,
                    "source_url": item.provenance.source_url,
                    "wrote": item.wrote,
                    "captured_at": item.provenance.captured_at,
                    "event_time": item.provenance.event_time,
                    "source_available_at": item.provenance.source_available_at,
                    "decision_at": item.provenance.decision_at,
                }
                for item in result.artifacts
            ],
            "provenance": {
                "ingest": "nfl_oracle.ingest.corpus_g",
                "auth": "headers_or_capture",
            },
        }
        atomic_write_json(path, payload)
        return path


async def ingest_game(
    *,
    game_id: int,
    store: CorpusGStore,
    client: httpx.AsyncClient,
    headers: RequestHeaders,
    refresh_headers: Any | None = None,
    season_hint: int | None = None,
) -> GameIngestResult:
    """Fetch stats/players/feed for one game and persist redacted artifacts."""

    stats = await fetch_game_stats(client, game_id, headers, refresh_headers=refresh_headers)
    players = await fetch_game_players(client, game_id, headers, refresh_headers=refresh_headers)
    feed = await fetch_game_feed(client, game_id, headers, refresh_headers=refresh_headers)
    coverage = summarize_payloads(stats=stats, players=players, feed=feed)
    season = coverage.game_season if coverage.game_season is not None else season_hint

    captured_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    artifacts: list[StoredArtifact] = []
    skipped: list[str] = []
    for endpoint, payload, url in (
        ("stats", stats, f"{BASE}/games/{game_id}/sport/{SPORT}/stats"),
        ("players", players, f"{BASE}/games/{game_id}/sport/{SPORT}/players"),
        (
            "feed",
            feed,
            f"{BASE}/games/{game_id}/sport/{SPORT}/feed?version=2&view=all&viewFrame=default",
        ),
    ):
        stored = store.persist_endpoint(
            game_id=game_id,
            season=season,
            endpoint=endpoint,  # type: ignore[arg-type]
            payload=payload,
            source_url=url,
            captured_at=datetime.fromisoformat(captured_at.replace("Z", "+00:00")),
            event_time=coverage.event_time,
            source_available_at=coverage.source_available_at,
            decision_at=None,
        )
        artifacts.append(stored)
        if not stored.wrote:
            skipped.append(endpoint)

    result = GameIngestResult(
        game_id=game_id,
        season=season,
        day=coverage.game_day,
        status=coverage.game_status,
        box_count=coverage.n_player_box_scores,
        value_nonnull=coverage.n_value_nonnull,
        player_count=coverage.n_players,
        play_count=coverage.n_plays,
        artifacts=tuple(artifacts),
        skipped_unchanged=tuple(skipped),
        event_time=coverage.event_time,
        source_available_at=coverage.source_available_at,
        captured_at=captured_at,
        decision_at=None,
    )
    manifest_path = store.write_manifest(result)
    return GameIngestResult(
        game_id=result.game_id,
        season=result.season,
        day=result.day,
        status=result.status,
        box_count=result.box_count,
        value_nonnull=result.value_nonnull,
        player_count=result.player_count,
        play_count=result.play_count,
        artifacts=result.artifacts,
        skipped_unchanged=result.skipped_unchanged,
        manifest_path=str(manifest_path),
        event_time=result.event_time,
        source_available_at=result.source_available_at,
        captured_at=result.captured_at,
        decision_at=result.decision_at,
    )

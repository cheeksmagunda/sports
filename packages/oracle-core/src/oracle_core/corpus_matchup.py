"""Provider-neutral durable game-stats + matchup corpus layout.

Sports Oracle keeps completed-game box scores and matchup context on disk so
HV/TDV models train against offline history instead of re-fetching every past
game on each slate. Each sport owns its scrape/source adapters; this module
only defines the shared append layout and idempotent write helpers.

Layout (under an explicit corpus root, often the orphan ``backups`` branch or a
dedicated corpus repository)::

    {root}/{sport}/{season}/{game_id}/
      matchup.json   # opponent / home-away / pace / box-line summary
      stats.json     # sport-owned player or team box payload
      manifest.json  # sha256 + captured_at + source

Writes are content-addressed: an identical payload is a no-op (``wrote=False``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from oracle_core.artifacts import atomic_write_json, sha256_bytes

MATCHUP_SCHEMA_VERSION = 1

MATCHUP_FILENAME = "matchup.json"
STATS_FILENAME = "stats.json"
MANIFEST_FILENAME = "manifest.json"

REQUIRED_MATCHUP_KEYS = frozenset(
    {
        "schema_version",
        "sport",
        "season",
        "game_id",
        "home_team",
        "away_team",
        "is_final",
        "source",
        "captured_at",
    }
)


@dataclass(frozen=True)
class GameMatchupRecord:
    """Minimal matchup context needed for Total Value / Highest-value models."""

    sport: str
    season: str
    game_id: str
    home_team: str | None
    away_team: str | None
    is_final: bool
    source: str
    captured_at: str
    game_date: str | None = None
    home_score: float | int | None = None
    away_score: float | int | None = None
    pace: float | None = None
    venue: str | None = None
    box_lines: Mapping[str, Any] | None = None
    extra: Mapping[str, Any] | None = None
    schema_version: int = MATCHUP_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.box_lines is not None:
            payload["box_lines"] = dict(self.box_lines)
        if self.extra is not None:
            payload["extra"] = dict(self.extra)
        return payload


@dataclass(frozen=True)
class AppendResult:
    sport: str
    season: str
    game_id: str
    game_dir: Path
    wrote_matchup: bool
    wrote_stats: bool
    wrote_manifest: bool
    matchup_sha256: str
    stats_sha256: str | None


def game_dir(root: Path, sport: str, season: str | int, game_id: str | int) -> Path:
    """Return ``{root}/{sport}/{season}/{game_id}/`` without creating it."""

    return Path(root) / str(sport).lower() / str(season) / str(game_id)


def _canonical_bytes(payload: Mapping[str, Any] | list[Any]) -> bytes:
    import json

    # Match atomic_write_json on-disk form (canonical JSON + trailing newline).
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"{body}\n".encode()


def _content_fingerprint(payload: Mapping[str, Any]) -> str:
    """Hash game facts only so re-appends with a fresh captured_at stay no-ops."""

    body = {key: value for key, value in payload.items() if key != "captured_at"}
    return sha256_bytes(_canonical_bytes(body))


def _existing_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.is_file():
        return None
    import json

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw


def _existing_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return sha256_bytes(path.read_bytes())


def validate_matchup_payload(payload: Mapping[str, Any]) -> list[str]:
    """Return human-readable problems; empty means the payload is append-ready."""

    problems: list[str] = []
    for key in sorted(REQUIRED_MATCHUP_KEYS):
        if key not in payload:
            problems.append(f"missing:{key}")
    if payload.get("schema_version") != MATCHUP_SCHEMA_VERSION:
        problems.append(f"schema_version_expected_{MATCHUP_SCHEMA_VERSION}")
    sport = payload.get("sport")
    if not isinstance(sport, str) or not sport.strip():
        problems.append("sport_must_be_nonempty_string")
    if "is_final" in payload and not isinstance(payload.get("is_final"), bool):
        problems.append("is_final_must_be_bool")
    return problems


def append_completed_game(
    root: Path,
    *,
    matchup: GameMatchupRecord | Mapping[str, Any],
    stats: Mapping[str, Any] | list[Any] | None = None,
) -> AppendResult:
    """Append one completed game's matchup (+ optional stats) into the corpus.

    Idempotent: if ``matchup.json`` / ``stats.json`` already match the payload
    bytes, those files are left untouched.
    """

    payload: dict[str, Any]
    if isinstance(matchup, GameMatchupRecord):
        payload = matchup.to_dict()
    else:
        payload = dict(matchup)
        payload.setdefault("schema_version", MATCHUP_SCHEMA_VERSION)
        payload.setdefault("captured_at", datetime.now(tz=UTC).isoformat())

    problems = validate_matchup_payload(payload)
    if problems:
        raise ValueError("invalid_matchup_payload:" + ",".join(problems))
    if not payload.get("is_final"):
        raise ValueError("refusing_non_final_game_append")

    sport = str(payload["sport"]).lower()
    season = str(payload["season"])
    game_id = str(payload["game_id"])
    destination = game_dir(root, sport, season, game_id)
    destination.mkdir(parents=True, exist_ok=True)

    matchup_path = destination / MATCHUP_FILENAME
    matchup_bytes = _canonical_bytes(payload)
    matchup_sha = sha256_bytes(matchup_bytes)
    existing_matchup = _existing_json(matchup_path)
    wrote_matchup = True
    if isinstance(existing_matchup, dict):
        wrote_matchup = _content_fingerprint(existing_matchup) != _content_fingerprint(payload)
    if wrote_matchup:
        atomic_write_json(matchup_path, payload)

    wrote_stats = False
    stats_sha: str | None = None
    if stats is not None:
        stats_path = destination / STATS_FILENAME
        stats_bytes = _canonical_bytes(stats)
        stats_sha = sha256_bytes(stats_bytes)
        wrote_stats = _existing_sha256(stats_path) != stats_sha
        if wrote_stats:
            atomic_write_json(stats_path, stats)

    # Preserve first-write captured_at on the manifest when matchup facts are unchanged.
    manifest_captured_at = payload["captured_at"]
    if not wrote_matchup and isinstance(existing_matchup, dict):
        prior = existing_matchup.get("captured_at")
        if isinstance(prior, str) and prior:
            manifest_captured_at = prior

    if wrote_matchup:
        stored_matchup_sha = matchup_sha
    else:
        stored_matchup_sha = _existing_sha256(matchup_path) or matchup_sha

    manifest = {
        "schema_version": MATCHUP_SCHEMA_VERSION,
        "sport": sport,
        "season": season,
        "game_id": game_id,
        "matchup_sha256": stored_matchup_sha,
        "stats_sha256": stats_sha,
        "captured_at": manifest_captured_at,
        "source": payload["source"],
        "files": [MATCHUP_FILENAME] + ([STATS_FILENAME] if stats is not None else []),
    }
    manifest_path = destination / MANIFEST_FILENAME
    existing_manifest = _existing_json(manifest_path)
    wrote_manifest = True
    if isinstance(existing_manifest, dict):
        wrote_manifest = _content_fingerprint(existing_manifest) != _content_fingerprint(manifest)
    if wrote_manifest:
        atomic_write_json(manifest_path, manifest)

    return AppendResult(
        sport=sport,
        season=season,
        game_id=game_id,
        game_dir=destination,
        wrote_matchup=wrote_matchup,
        wrote_stats=wrote_stats,
        wrote_manifest=wrote_manifest,
        matchup_sha256=matchup_sha,
        stats_sha256=stats_sha,
    )


def list_appended_games(root: Path, sport: str | None = None) -> list[tuple[str, str, str]]:
    """Return ``(sport, season, game_id)`` triples that already have matchup.json."""

    base = Path(root)
    if not base.is_dir():
        return []
    out: list[tuple[str, str, str]] = []
    if sport:
        sport_dirs = [base / sport.lower()]
    else:
        sport_dirs = sorted(path for path in base.iterdir() if path.is_dir())
    for sport_dir in sport_dirs:
        if not sport_dir.is_dir():
            continue
        sport_key = sport_dir.name
        for season_dir in sorted(p for p in sport_dir.iterdir() if p.is_dir()):
            for game in sorted(p for p in season_dir.iterdir() if p.is_dir()):
                if (game / MATCHUP_FILENAME).is_file():
                    out.append((sport_key, season_dir.name, game.name))
    return out

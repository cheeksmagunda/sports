"""Durable Total Value / Highest-value leaderboard helpers (issue #526).

Provider-neutral contract for appending Real Sports Daily Draft Stats
``highestBoostedValuePlayers`` (Highest value / Total Value Daily Leaderboard)
into a **separate** GitHub-tracked corpus repo.

Canonical on-disk layout is owned by ``oracle_core.realsports_corpus``::

    {sport}/{season}/{slate_or_game_id}/hv_board.json
    coverage/manifest.json

This module builds the HV board document and delegates append to that layout.
Legacy ``hv_boards/...`` paths are no longer written.

Row fields (every player on the HV board)::

    player_id, name, team, real_score, base, card_boost, slot, drafts, value

Sport packages own endpoint parsing; this module only normalizes persistence.
Never store secrets, cookies, or storage_state material in corpus files.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from oracle_core.artifacts import sha256_bytes
from oracle_core.realsports_corpus import (
    append_artifact,
    season_from_iso_date,
    slate_or_game_key,
)

SportCode = Literal["wnba", "nfl", "nba", "nhl"]

HV_SECTION = "highestBoostedValuePlayers"
SCHEMA_VERSION = 1
# Retained name for callers that previously imported CORPUS_ROOT_DIRNAME.
CORPUS_ROOT_DIRNAME = ""


@dataclass(frozen=True)
class HvBoardPlayer:
    """One row on a Highest-value / Total Value Daily Leaderboard."""

    player_id: int
    name: str
    team: str
    real_score: float | None
    base: float | None
    card_boost: float | None
    slot: int | None
    drafts: int | None
    value: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HvBoardDocument:
    """One finalized slate's HV board, ready for corpus append."""

    sport: SportCode
    year: int
    slate_date: str
    contest_id: int | None
    section: str
    scraped_at: str
    players: tuple[HvBoardPlayer, ...]
    schema_version: int = SCHEMA_VERSION
    source: str = "realsports.draftStats.highestBoostedValuePlayers"

    @property
    def slate_key(self) -> str:
        return slate_or_game_key(slate_date=self.slate_date, contest_id=self.contest_id)

    def relative_path(self) -> Path:
        return Path(self.sport) / str(self.year) / self.slate_key / "hv_board.json"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "sport": self.sport,
            "year": self.year,
            "season": str(self.year),
            "slate_date": self.slate_date,
            "contest_id": self.contest_id,
            "slate_key": self.slate_key,
            "slate_or_game_id": self.slate_key,
            "section": self.section,
            "source": self.source,
            "scraped_at": self.scraped_at,
            "label": "total_value_leaderboard",
            "player_count": len(self.players),
            "players": [p.to_dict() for p in self.players],
            # Feature wiring: HV value + card_boost + team map into own-model
            # ridge/valuelaw/EB surfaces tracked under issues #523 / #453.
            "own_model_refs": {
                "issue": 523,
                "label": "total_value_leaderboard",
                "fields": {
                    "value": "train_label (Total Value)",
                    "real_score": "raw Real score when distinct",
                    "card_boost": "slate_meta / boost prior (not post-settlement)",
                    "team": "matchup.opponent_team / home_away join key",
                    "drafts": "ownership prior when pre-lock measured",
                },
            },
        }

    def content_sha256(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return sha256_bytes(payload)


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def year_from_slate_date(slate_date: str) -> int:
    """Return YYYY from an ISO slate date; raise on malformed input."""

    if len(slate_date) < 4 or not slate_date[:4].isdigit():
        raise ValueError(f"invalid slate_date for year: {slate_date!r}")
    return int(slate_date[:4])


def build_hv_board(
    *,
    sport: SportCode,
    slate_date: str,
    contest_id: int | None,
    players: list[HvBoardPlayer] | tuple[HvBoardPlayer, ...],
    scraped_at: str | None = None,
    section: str = HV_SECTION,
) -> HvBoardDocument:
    """Build a board document; sorts players by value desc then player_id."""

    ordered = sorted(
        players,
        key=lambda p: (
            -(p.value if p.value is not None else float("-inf")),
            p.player_id,
        ),
    )
    return HvBoardDocument(
        sport=sport,
        year=year_from_slate_date(slate_date),
        slate_date=slate_date,
        contest_id=contest_id,
        section=section,
        scraped_at=scraped_at or utc_now_iso(),
        players=tuple(ordered),
    )


def write_hv_board(doc: HvBoardDocument, corpus_root: Path) -> Path:
    """Atomically write ``doc`` under ``corpus_root``; return absolute path."""

    summary = append_hv_board(doc, corpus_root)
    return corpus_root / summary["path"]


def update_manifest(corpus_root: Path, doc: HvBoardDocument, *, path: Path) -> Path:
    """Compatibility shim: coverage manifest lives at ``coverage/manifest.json``."""

    _ = (doc, path)
    from oracle_core.realsports_corpus import COVERAGE_MANIFEST_RELPATH

    return corpus_root / COVERAGE_MANIFEST_RELPATH


def append_hv_board(doc: HvBoardDocument, corpus_root: Path) -> dict[str, Any]:
    """Write board + update coverage manifest; return a value-free summary."""

    season = season_from_iso_date(doc.slate_date)
    summary = append_artifact(
        corpus_root,
        sport=doc.sport,
        season=season,
        slate_or_game_id=doc.slate_key,
        artifact="hv_board",
        payload=doc.to_dict(),
        source=doc.source,
        scraped_at=doc.scraped_at,
    )
    return {
        "sport": doc.sport,
        "slate_date": doc.slate_date,
        "contest_id": doc.contest_id,
        "slate_key": doc.slate_key,
        "player_count": len(doc.players),
        "path": summary["path"],
        "manifest": "coverage/manifest.json",
        "content_sha256": summary["sha256_12"],
        "wrote": summary["wrote"],
    }

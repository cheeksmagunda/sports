"""Export durable WNBA Real Sports contest tables into corpus layout (#526).

Reads Postgres ``slate_labels`` (all draftStats sections) and
``contest_leaderboards`` (top-20 recorded states) and writes per-slate
shards under::

    sport=wnba/season=YYYY/slate=YYYY-MM-DD/
      total_value_leaderboard.json   # section=highestBoostedValuePlayers
      draft_stats_all_sections.jsonl # every section row
      lineups_top20.json             # leaderboards as recorded_states
      manifest.json                  # shard checksums + row counts

Designed for the sibling ``sports-realsports-corpus`` repo, or a
gitignored monorepo ``corpus/`` staging tree. Never prints connection
strings or secrets.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HV_SECTION = "highestBoostedValuePlayers"
SCHEMA_VERSION = 1
SPORT = "wnba"

SLATE_LABEL_FIELDS = (
    "contest_id",
    "slate_date",
    "section",
    "platform_player_id",
    "display_name",
    "team_key",
    "card_boost",
    "drafts",
    "real_score",
    "ingested_at",
)
LEADERBOARD_FIELDS = (
    "contest_id",
    "slate_date",
    "entry_id",
    "rank",
    "paged_rank",
    "user_id",
    "score",
    "lineup",
    "num_brawlers",
    "ingested_at",
)


@dataclass(frozen=True)
class SlateExportSummary:
    """Value-free summary of one written slate shard."""

    slate_date: str
    season: int
    path: str
    hv_rows: int
    draft_stats_rows: int
    lineup_rows: int
    contest_ids: tuple[int, ...]


def year_from_slate_date(slate_date: str) -> int:
    if len(slate_date) < 4 or not slate_date[:4].isdigit():
        raise ValueError(f"invalid slate_date for season: {slate_date!r}")
    return int(slate_date[:4])


def slate_dir(corpus_root: Path, slate_date: str) -> Path:
    season = year_from_slate_date(slate_date)
    return corpus_root / f"sport={SPORT}" / f"season={season}" / f"slate={slate_date}"


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> bytes:
    payload = json.dumps(value, indent=2, sort_keys=True, default=str).encode("utf-8") + b"\n"
    _atomic_write_bytes(path, payload)
    return payload


def _atomic_write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> bytes:
    lines = [json.dumps(row, sort_keys=True, separators=(",", ":"), default=str) for row in rows]
    payload = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    _atomic_write_bytes(path, payload)
    return payload


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _as_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def label_row_to_player(row: Mapping[str, Any]) -> dict[str, Any]:
    """Map a ``slate_labels`` row to the corpus HV / draftStats player shape.

    Provider ``value`` is stored as ``real_score``; ``base`` mirrors it when
    no separate base exists. ``slot`` is null on section boards (lineup
    recorded_states carry slot multipliers inside ``lineup`` JSON).
    """

    real_score = _as_float(row.get("real_score"))
    card_boost = _as_float(row.get("card_boost"))
    return {
        "player_id": _as_int(row.get("platform_player_id")),
        "name": str(row.get("display_name") or ""),
        "team": str(row.get("team_key") or ""),
        "real_score": real_score,
        "base": real_score,
        "card_boost": card_boost,
        "slot": None,
        "drafts": _as_int(row.get("drafts")),
        "value": real_score,
        "section": str(row.get("section") or ""),
        "contest_id": _as_int(row.get("contest_id")),
        "slate_date": str(row.get("slate_date") or ""),
        "ingested_at": row.get("ingested_at"),
    }


def leaderboard_row_to_recorded_state(row: Mapping[str, Any]) -> dict[str, Any]:
    """Map a ``contest_leaderboards`` row to a recorded_state object."""

    lineup = row.get("lineup")
    if isinstance(lineup, str):
        try:
            lineup = json.loads(lineup)
        except json.JSONDecodeError:
            lineup = {"raw": lineup}
    return {
        "contest_id": _as_int(row.get("contest_id")),
        "slate_date": str(row.get("slate_date") or ""),
        "entry_id": _as_int(row.get("entry_id")),
        "rank": _as_int(row.get("rank")),
        "paged_rank": _as_int(row.get("paged_rank")),
        "user_id": str(row.get("user_id") or ""),
        "score": _as_float(row.get("score")),
        "lineup": lineup,
        "num_brawlers": _as_int(row.get("num_brawlers")),
        "ingested_at": row.get("ingested_at"),
    }


def build_total_value_leaderboard(
    *,
    slate_date: str,
    hv_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    players = [label_row_to_player(row) for row in hv_rows]
    players.sort(
        key=lambda p: (
            -(p["value"] if p["value"] is not None else float("-inf")),
            p["player_id"] if p["player_id"] is not None else 0,
        )
    )
    contest_ids = sorted(
        {cid for cid in (_as_int(r.get("contest_id")) for r in hv_rows) if cid is not None}
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "sport": SPORT,
        "season": year_from_slate_date(slate_date),
        "slate_date": slate_date,
        "section": HV_SECTION,
        "source": "wnba.postgres.slate_labels",
        "contest_ids": contest_ids,
        "player_count": len(players),
        "players": players,
    }


def build_lineups_top20(
    *,
    slate_date: str,
    leaderboard_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    states = [leaderboard_row_to_recorded_state(row) for row in leaderboard_rows]
    states.sort(
        key=lambda s: (
            s["rank"] if s["rank"] is not None else 10**9,
            s["entry_id"] if s["entry_id"] is not None else 0,
        )
    )
    contest_ids = sorted(
        {cid for cid in (_as_int(r.get("contest_id")) for r in leaderboard_rows) if cid is not None}
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "sport": SPORT,
        "season": year_from_slate_date(slate_date),
        "slate_date": slate_date,
        "source": "wnba.postgres.contest_leaderboards",
        "contest_ids": contest_ids,
        "recorded_state_count": len(states),
        "recorded_states": states,
    }


def write_slate_shard(
    corpus_root: Path,
    *,
    slate_date: str,
    label_rows: Sequence[Mapping[str, Any]],
    leaderboard_rows: Sequence[Mapping[str, Any]],
    exported_at: str | None = None,
) -> SlateExportSummary:
    """Write one slate's files + shard manifest; return a value-free summary."""

    destination = slate_dir(corpus_root, slate_date)
    destination.mkdir(parents=True, exist_ok=True)
    when = exported_at or utc_now_iso()

    hv_rows = [row for row in label_rows if str(row.get("section")) == HV_SECTION]
    all_section_players = [label_row_to_player(row) for row in label_rows]
    # Stable JSONL order: section, value desc, player_id.
    all_section_players.sort(
        key=lambda p: (
            p["section"],
            -(p["value"] if p["value"] is not None else float("-inf")),
            p["player_id"] if p["player_id"] is not None else 0,
        )
    )

    tv_doc = build_total_value_leaderboard(slate_date=slate_date, hv_rows=hv_rows)
    lineups_doc = build_lineups_top20(slate_date=slate_date, leaderboard_rows=leaderboard_rows)

    tv_path = destination / "total_value_leaderboard.json"
    jsonl_path = destination / "draft_stats_all_sections.jsonl"
    lineups_path = destination / "lineups_top20.json"
    manifest_path = destination / "manifest.json"

    tv_bytes = _atomic_write_json(tv_path, tv_doc)
    jsonl_bytes = _atomic_write_jsonl(jsonl_path, all_section_players)
    lineups_bytes = _atomic_write_json(lineups_path, lineups_doc)

    files = {
        "total_value_leaderboard.json": {
            "rows": tv_doc["player_count"],
            "bytes": len(tv_bytes),
            "sha256": _sha256_bytes(tv_bytes),
            "section": HV_SECTION,
        },
        "draft_stats_all_sections.jsonl": {
            "rows": len(all_section_players),
            "bytes": len(jsonl_bytes),
            "sha256": _sha256_bytes(jsonl_bytes),
        },
        "lineups_top20.json": {
            "rows": lineups_doc["recorded_state_count"],
            "bytes": len(lineups_bytes),
            "sha256": _sha256_bytes(lineups_bytes),
        },
    }
    contest_ids = sorted(
        {
            cid
            for cid in (
                *(_as_int(r.get("contest_id")) for r in label_rows),
                *(_as_int(r.get("contest_id")) for r in leaderboard_rows),
            )
            if cid is not None
        }
    )
    sections = sorted({str(r.get("section") or "") for r in label_rows if r.get("section")})
    shard_manifest = {
        "schema_version": SCHEMA_VERSION,
        "sport": SPORT,
        "season": year_from_slate_date(slate_date),
        "slate_date": slate_date,
        "contest_ids": contest_ids,
        "sections": sections,
        "exported_at": when,
        "source": "wnba.postgres.slate_labels+contest_leaderboards",
        "files": files,
    }
    _atomic_write_json(manifest_path, shard_manifest)

    rel = str(destination.relative_to(corpus_root)).replace("\\", "/")
    return SlateExportSummary(
        slate_date=slate_date,
        season=year_from_slate_date(slate_date),
        path=rel,
        hv_rows=int(tv_doc["player_count"]),
        draft_stats_rows=len(all_section_players),
        lineup_rows=int(lineups_doc["recorded_state_count"]),
        contest_ids=tuple(contest_ids),
    )


def update_coverage_index(
    corpus_root: Path,
    summaries: Sequence[SlateExportSummary],
    *,
    exported_at: str | None = None,
) -> Path:
    """Upsert ``manifest/coverage_wnba.json`` with exported slate shards."""

    index_path = corpus_root / "manifest" / "coverage_wnba.json"
    if index_path.is_file():
        coverage: dict[str, Any] = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        coverage = {
            "schema_version": SCHEMA_VERSION,
            "sport": SPORT,
            "slates": {},
        }
    slates = coverage.setdefault("slates", {})
    if not isinstance(slates, dict):
        raise ValueError("coverage_wnba.slates must be an object")
    when = exported_at or utc_now_iso()
    for summary in summaries:
        slates[summary.slate_date] = {
            "season": summary.season,
            "path": summary.path,
            "hv_rows": summary.hv_rows,
            "draft_stats_rows": summary.draft_stats_rows,
            "lineup_rows": summary.lineup_rows,
            "contest_ids": list(summary.contest_ids),
            "status": "present",
            "exported_at": when,
        }
    coverage["updated_at"] = when
    coverage["slate_count"] = len(slates)
    _atomic_write_json(index_path, coverage)
    return index_path


def export_slates(
    corpus_root: Path,
    *,
    label_rows: Sequence[Mapping[str, Any]],
    leaderboard_rows: Sequence[Mapping[str, Any]],
    slate_dates: Iterable[str] | None = None,
) -> list[SlateExportSummary]:
    """Group rows by slate_date and write every requested shard."""

    labels_by_date: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in label_rows:
        date = str(row.get("slate_date") or "").strip()
        if date:
            labels_by_date[date].append(row)

    boards_by_date: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in leaderboard_rows:
        date = str(row.get("slate_date") or "").strip()
        if date:
            boards_by_date[date].append(row)

    if slate_dates is None:
        dates = sorted(set(labels_by_date) | set(boards_by_date))
    else:
        dates = sorted({d.strip() for d in slate_dates if d and d.strip()})

    when = utc_now_iso()
    summaries = [
        write_slate_shard(
            corpus_root,
            slate_date=date,
            label_rows=labels_by_date.get(date, []),
            leaderboard_rows=boards_by_date.get(date, []),
            exported_at=when,
        )
        for date in dates
    ]
    if summaries:
        update_coverage_index(corpus_root, summaries, exported_at=when)
    return summaries


def fake_demo_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Schema-faithful demo rows for dry-run / unit tests (no secrets)."""

    labels = [
        {
            "contest_id": 2100,
            "slate_date": "2026-09-25",
            "section": HV_SECTION,
            "platform_player_id": 11,
            "display_name": "A. Wilson",
            "team_key": "LVA",
            "card_boost": 1.5,
            "drafts": 120,
            "real_score": 42.5,
            "ingested_at": "2026-09-26T06:00:00Z",
        },
        {
            "contest_id": 2100,
            "slate_date": "2026-09-25",
            "section": "popularPlayers",
            "platform_player_id": 22,
            "display_name": "B. Clark",
            "team_key": "IND",
            "card_boost": 0.5,
            "drafts": 800,
            "real_score": 31.0,
            "ingested_at": "2026-09-26T06:00:00Z",
        },
        {
            "contest_id": 2100,
            "slate_date": "2026-09-25",
            "section": HV_SECTION,
            "platform_player_id": 33,
            "display_name": "C. Collier",
            "team_key": "MIN",
            "card_boost": 2.0,
            "drafts": 40,
            "real_score": 38.0,
            "ingested_at": "2026-09-26T06:00:00Z",
        },
    ]
    leaderboards = [
        {
            "contest_id": 2100,
            "slate_date": "2026-09-25",
            "entry_id": 9001,
            "rank": 1,
            "paged_rank": 1,
            "user_id": "opaqueUser1",
            "score": 215.5,
            "lineup": [
                {
                    "playerId": 11,
                    "displayName": "A. Wilson",
                    "multiplier": 2.0,
                    "multiplierBonus": 1.5,
                    "value": "42.5",
                    "score": 148.75,
                }
            ],
            "num_brawlers": 5,
            "ingested_at": "2026-09-26T06:05:00Z",
        },
        {
            "contest_id": 2100,
            "slate_date": "2026-09-25",
            "entry_id": 9002,
            "rank": 2,
            "paged_rank": 2,
            "user_id": "opaqueUser2",
            "score": 210.0,
            "lineup": [
                {
                    "playerId": 33,
                    "displayName": "C. Collier",
                    "multiplier": 1.5,
                    "multiplierBonus": 2.0,
                    "value": "38.0",
                    "score": 133.0,
                }
            ],
            "num_brawlers": 5,
            "ingested_at": "2026-09-26T06:05:00Z",
        },
    ]
    return labels, leaderboards


def load_rows_from_engine(engine: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read both corpus tables from one read-only repeatable-read snapshot."""

    from sqlalchemy import text

    label_sql = text(
        "SELECT contest_id, slate_date, section, platform_player_id, display_name, "
        "team_key, card_boost, drafts, real_score, ingested_at "
        "FROM slate_labels ORDER BY slate_date, contest_id, section, platform_player_id"
    )
    board_sql = text(
        "SELECT contest_id, slate_date, entry_id, rank, paged_rank, user_id, score, "
        "lineup, num_brawlers, ingested_at "
        "FROM contest_leaderboards ORDER BY slate_date, contest_id, rank, entry_id"
    )
    connection = engine.connect().execution_options(isolation_level="REPEATABLE READ")
    try:
        with connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            label_result = connection.execute(label_sql)
            labels = [dict(row._mapping) for row in label_result]
            board_result = connection.execute(board_sql)
            boards = [dict(row._mapping) for row in board_result]
    finally:
        connection.close()
    return labels, boards

"""Export WNBA slate_labels + contest_leaderboards into kind-first corpus layout.

Layout (sibling sports-realsports-corpus / local staging root)::

    total_value_leaderboards/wnba/{year}/slate_{date}/highestBoostedValuePlayers.json
    recorded_states/wnba/{year}/slate_{date}/draft_stats_all_sections.jsonl
    recorded_states/wnba/{year}/slate_{date}/contest_leaderboards.json
    manifest/draft_stats_sections.json

Every ``slate_labels.section`` row lands in ``recorded_states`` (observation /
history dump). Only ``highestBoostedValuePlayers`` is also written under
``total_value_leaderboards`` for train/grade. ``contest_leaderboards`` lineup
JSON is recorded_states only — never a train label.

Refs #526.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from oracle_core.draft_stats_catalog import (
    HV_SECTION,
    SCHEMA_VERSION,
    catalog_document,
)

SPORT = "wnba"


@dataclass(frozen=True)
class SlateExportSummary:
    """Value-free summary of one slate write."""

    slate_date: str
    year: int
    hv_rows: int
    recorded_draft_stats_rows: int
    recorded_lineup_rows: int
    sections: tuple[str, ...]
    contest_ids: tuple[int, ...]
    tv_path: str
    recorded_draft_stats_path: str
    recorded_lineups_path: str


def year_from_slate_date(slate_date: str) -> int:
    if len(slate_date) < 4 or not slate_date[:4].isdigit():
        raise ValueError(f"invalid slate_date for year: {slate_date!r}")
    return int(slate_date[:4])


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def family_slate_dir(corpus_root: Path, family: str, slate_date: str) -> Path:
    year = year_from_slate_date(slate_date)
    return corpus_root / family / SPORT / str(year) / f"slate_{slate_date}"


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _as_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None


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


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    payload = json.dumps(value, indent=2, sort_keys=True, default=str).encode("utf-8") + b"\n"
    _atomic_write_bytes(path, payload)


def _atomic_write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    lines = [json.dumps(row, sort_keys=True, separators=(",", ":"), default=str) for row in rows]
    payload = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    _atomic_write_bytes(path, payload)


def label_row_to_recorded(row: Mapping[str, Any]) -> dict[str, Any]:
    """Project one slate_labels row into a recorded_states draftStats record."""

    real_score = _as_float(row.get("real_score"))
    return {
        "contest_id": _as_int(row.get("contest_id")),
        "slate_date": str(row.get("slate_date") or ""),
        "section": str(row.get("section") or ""),
        "player_id": _as_int(row.get("platform_player_id")),
        "name": str(row.get("display_name") or ""),
        "team": str(row.get("team_key") or ""),
        "real_score": real_score,
        "base": real_score,
        "card_boost": _as_float(row.get("card_boost")),
        "slot": None,
        "drafts": _as_int(row.get("drafts")),
        "value": real_score,
        "ingested_at": row.get("ingested_at"),
        "role": "recorded_state",
        "train_label": str(row.get("section") or "") == HV_SECTION,
    }


def leaderboard_row_to_recorded(row: Mapping[str, Any]) -> dict[str, Any]:
    """Project one contest_leaderboards row (lineup JSON) as observation only."""

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
        "role": "recorded_state",
        "train_label": False,
        "source": "wnba.postgres.contest_leaderboards",
    }


def build_hv_document(
    *,
    slate_date: str,
    hv_rows: Sequence[Mapping[str, Any]],
    exported_at: str,
) -> dict[str, Any]:
    players = [label_row_to_recorded(row) for row in hv_rows]
    for player in players:
        player["train_label"] = True
        player["role"] = "total_value_leaderboard"
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
        "year": year_from_slate_date(slate_date),
        "slate_date": slate_date,
        "section": HV_SECTION,
        "source": "wnba.postgres.slate_labels",
        "exported_at": exported_at,
        "contest_ids": contest_ids,
        "player_count": len(players),
        "players": players,
        "train_label": True,
    }


def write_section_catalog(corpus_root: Path) -> Path:
    """Persist the portfolio draftStats section catalog under manifest/."""

    path = corpus_root / "manifest" / "draft_stats_sections.json"
    _atomic_write_json(path, catalog_document())
    return path


def write_slate_export(
    corpus_root: Path,
    *,
    slate_date: str,
    label_rows: Sequence[Mapping[str, Any]],
    leaderboard_rows: Sequence[Mapping[str, Any]],
    exported_at: str | None = None,
) -> SlateExportSummary:
    """Write HV board + all-section recorded_states + leaderboard observations."""

    when = exported_at or utc_now_iso()
    hv_rows = [row for row in label_rows if str(row.get("section")) == HV_SECTION]
    recorded_stats = [label_row_to_recorded(row) for row in label_rows]
    recorded_stats.sort(
        key=lambda p: (
            p["section"],
            -(p["value"] if p["value"] is not None else float("-inf")),
            p["player_id"] if p["player_id"] is not None else 0,
        )
    )
    recorded_lineups = [leaderboard_row_to_recorded(row) for row in leaderboard_rows]
    recorded_lineups.sort(
        key=lambda s: (
            s["rank"] if s["rank"] is not None else 10**9,
            s["entry_id"] if s["entry_id"] is not None else 0,
        )
    )

    tv_dir = family_slate_dir(corpus_root, "total_value_leaderboards", slate_date)
    rs_dir = family_slate_dir(corpus_root, "recorded_states", slate_date)
    tv_path = tv_dir / f"{HV_SECTION}.json"
    draft_path = rs_dir / "draft_stats_all_sections.jsonl"
    lineups_path = rs_dir / "contest_leaderboards.json"

    _atomic_write_json(
        tv_path,
        build_hv_document(slate_date=slate_date, hv_rows=hv_rows, exported_at=when),
    )
    _atomic_write_jsonl(draft_path, recorded_stats)
    _atomic_write_json(
        lineups_path,
        {
            "schema_version": SCHEMA_VERSION,
            "sport": SPORT,
            "year": year_from_slate_date(slate_date),
            "slate_date": slate_date,
            "source": "wnba.postgres.contest_leaderboards",
            "exported_at": when,
            "role": "recorded_state",
            "train_label": False,
            "entry_count": len(recorded_lineups),
            "entries": recorded_lineups,
        },
    )
    write_section_catalog(corpus_root)

    sections = tuple(sorted({str(r.get("section") or "") for r in label_rows if r.get("section")}))
    contest_ids = tuple(
        sorted(
            {
                cid
                for cid in (
                    *(_as_int(r.get("contest_id")) for r in label_rows),
                    *(_as_int(r.get("contest_id")) for r in leaderboard_rows),
                )
                if cid is not None
            }
        )
    )
    root = corpus_root.resolve()
    return SlateExportSummary(
        slate_date=slate_date,
        year=year_from_slate_date(slate_date),
        hv_rows=len(hv_rows),
        recorded_draft_stats_rows=len(recorded_stats),
        recorded_lineup_rows=len(recorded_lineups),
        sections=sections,
        contest_ids=contest_ids,
        tv_path=str(tv_path.resolve().relative_to(root)).replace("\\", "/"),
        recorded_draft_stats_path=str(draft_path.resolve().relative_to(root)).replace("\\", "/"),
        recorded_lineups_path=str(lineups_path.resolve().relative_to(root)).replace("\\", "/"),
    )


def export_slates(
    corpus_root: Path,
    *,
    label_rows: Sequence[Mapping[str, Any]],
    leaderboard_rows: Sequence[Mapping[str, Any]],
    slate_dates: Iterable[str] | None = None,
) -> list[SlateExportSummary]:
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
    return [
        write_slate_export(
            corpus_root,
            slate_date=date,
            label_rows=labels_by_date.get(date, []),
            leaderboard_rows=boards_by_date.get(date, []),
            exported_at=when,
        )
        for date in dates
    ]


def fake_demo_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Offline demo rows covering every known WNBA slate_labels section."""

    labels = [
        {
            "contest_id": 2100,
            "slate_date": "2026-09-24",
            "section": HV_SECTION,
            "platform_player_id": 11,
            "display_name": "A. Wilson",
            "team_key": "LVA",
            "card_boost": 1.5,
            "drafts": 120,
            "real_score": 42.5,
            "ingested_at": "2026-09-25T06:00:00Z",
        },
        {
            "contest_id": 2100,
            "slate_date": "2026-09-24",
            "section": "popularPlayers",
            "platform_player_id": 22,
            "display_name": "B. Clark",
            "team_key": "IND",
            "card_boost": 0.5,
            "drafts": 800,
            "real_score": 31.0,
            "ingested_at": "2026-09-25T06:00:00Z",
        },
        {
            "contest_id": 2100,
            "slate_date": "2026-09-24",
            "section": "mostCommon3xPlayers",
            "platform_player_id": 33,
            "display_name": "C. Collier",
            "team_key": "MIN",
            "card_boost": 2.0,
            "drafts": 40,
            "real_score": 38.0,
            "ingested_at": "2026-09-25T06:00:00Z",
        },
        {
            "contest_id": 2100,
            "slate_date": "2026-09-24",
            "section": "leaderboard_lineup",
            "platform_player_id": 44,
            "display_name": "D. Supplemental",
            "team_key": "NYL",
            "card_boost": 0.0,
            "drafts": None,
            "real_score": 12.0,
            "ingested_at": "2026-09-25T06:00:00Z",
        },
    ]
    leaderboards = [
        {
            "contest_id": 2100,
            "slate_date": "2026-09-24",
            "entry_id": 9001,
            "rank": 1,
            "paged_rank": 1,
            "user_id": "opaqueUser1",
            "score": 215.5,
            "lineup": [
                {
                    "order": 0,
                    "playerId": 11,
                    "displayName": "A. Wilson",
                    "multiplier": 2.0,
                    "multiplierBonus": 1.5,
                    "value": "42.5",
                    "score": 148.75,
                }
            ],
            "num_brawlers": 5000,
            "ingested_at": "2026-09-25T06:05:00Z",
        }
    ]
    return labels, leaderboards

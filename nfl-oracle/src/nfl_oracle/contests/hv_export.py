"""Export Corpus C draft_stats into durable Total Value / HV board artifacts.

NFL does not store a dedicated Highest-value table. Real Sports puts the
Total Value Daily Leaderboard in ``draftStats`` as
``highestBoostedValuePlayers`` (plus sibling sections). This module walks an
on-disk Corpus C tree (Railway volume or local fixtures), reconstructs the HV
board when that section is missing, and writes per-contest export files plus a
coverage manifest of gaps.

Env:

- ``NFL_CORPUS_C_ROOT`` — Corpus C root (default ``{project}/data/raw/corpus_c``).
  On Railway the worker volume mounts at ``/app/nfl-oracle/data``, so the
  default becomes ``/app/nfl-oracle/data/raw/corpus_c``.
- ``NFL_HV_EXPORT_ROOT`` — optional default export destination.

Coordinate with portfolio #526 (HV corpus repo), #453 / #503 (Corpus G volume),
and PR #512 (nightly Corpus G). Never mint credentials; read-only disk walk.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from oracle_core.artifacts import atomic_write_bytes, atomic_write_json, sha256_bytes

from nfl_oracle.contests.parse import ContestParseError, ParsedContest, load_contest
from nfl_oracle.contests.schema import DraftStatRow
from nfl_oracle.contests.store import ContestStore, corpus_c_root, project_root
from nfl_oracle.recommendations.high_tv import high_tv_board_from_draft_stats

HV_SECTION = "highestBoostedValuePlayers"
SCHEMA_VERSION = 1
TOTAL_VALUE_FILENAME = "total_value_leaderboard.json"
DRAFT_STATS_FILENAME = "draft_stats_all_sections.jsonl"
MATCHUPS_FILENAME = "matchups.json"
COVERAGE_MANIFEST_FILENAME = "coverage_manifest.json"

GapKind = Literal[
    "corpus_c_empty",
    "corpus_c_missing",
    "missing_stats",
    "missing_hv_section",
    "hv_board_unreconstructable",
    "parse_error",
    "no_matchup_links",
]


@dataclass(frozen=True)
class LeaderboardPlayer:
    """One row on the exported Total Value / Highest-value board."""

    player_id: int
    name: str | None
    team_id: int | None
    real_score: float | None
    base: float | None
    card_boost: float | None
    slot: int | None
    drafts: int | None
    value: float | None
    rank: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContestExportResult:
    contest_id: int
    slate_date: str | None
    season: int | None
    status: Literal["exported", "partial", "skipped", "error"]
    hv_source: str | None = None
    player_count: int = 0
    section_count: int = 0
    matchup_game_ids: list[int] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    export_dir: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExportSummary:
    corpus_c_root: str
    export_root: str
    contests_seen: int
    contests_exported: int
    contests_partial: int
    contests_skipped: int
    contests_errored: int
    gaps: list[dict[str, Any]]
    results: list[ContestExportResult]
    volume_empty: bool
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "sport": "nfl",
            "corpus_c_root": self.corpus_c_root,
            "export_root": self.export_root,
            "contests_seen": self.contests_seen,
            "contests_exported": self.contests_exported,
            "contests_partial": self.contests_partial,
            "contests_skipped": self.contests_skipped,
            "contests_errored": self.contests_errored,
            "volume_empty": self.volume_empty,
            "gaps": self.gaps,
            "results": [r.to_dict() for r in self.results],
            "updated_at": self.updated_at,
            "railway_volume_mount": "/app/nfl-oracle/data",
            "notes": (
                "NFL HV boards are reconstructed from Corpus C draft_stats "
                f"({HV_SECTION} when present); Corpus G/C are not on the "
                "backups branch. Coordinate with #512 Corpus G nightly."
            ),
        }


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_corpus_c_root(override: Path | None = None, *, project: Path | None = None) -> Path:
    """Resolve Corpus C root: CLI override, then ``NFL_CORPUS_C_ROOT``, then default."""

    if override is not None:
        return Path(override).expanduser().resolve()
    env = os.environ.get("NFL_CORPUS_C_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return corpus_c_root(project).resolve()


def resolve_export_root(override: Path | None = None, *, project: Path | None = None) -> Path:
    if override is not None:
        return Path(override).expanduser().resolve()
    env = os.environ.get("NFL_HV_EXPORT_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    root = project_root(project)
    return (root / "data" / "export" / "hv_boards").resolve()


def contest_export_dir(export_root: Path, *, year: int, slate_date: str, contest_id: int) -> Path:
    return export_root / "nfl" / str(year) / slate_date / f"contest_{contest_id}"


def _section_name(section: Mapping[str, Any]) -> str:
    return str(section.get("sectionName") or section.get("label") or "unknown")


def iter_raw_draft_stat_rows(
    stats_payload: Mapping[str, Any], *, contest_id: int
) -> Iterator[dict[str, Any]]:
    """Yield one flat dict per player row across every draftStats section."""

    sections = stats_payload.get("draftStats")
    if not isinstance(sections, list):
        return
    for section in sections:
        if not isinstance(section, dict):
            continue
        name = _section_name(section)
        for row in section.get("players") or []:
            if not isinstance(row, dict):
                continue
            raw_player = row.get("player")
            raw_team = row.get("team")
            player: dict[str, Any] = raw_player if isinstance(raw_player, dict) else {}
            team: dict[str, Any] = raw_team if isinstance(raw_team, dict) else {}
            first = player.get("firstName")
            last = player.get("lastName")
            display = f"{first} {last}" if first and last else None
            player_id = row.get("playerId") or player.get("id")
            yield {
                "contest_id": contest_id,
                "section": name,
                "player_id": player_id,
                "name": display,
                "team_id": row.get("teamId") or team.get("id"),
                "team_key": team.get("key"),
                "card_boost": row.get("multiplierBonus"),
                "value": row.get("value"),
                "drafts": row.get("count"),
                "avg_multiplier": row.get("avgMultiplier"),
                "avg_position": row.get("avgPosition"),
                "avg_score": row.get("avgScore"),
                "highest_score": row.get("highestScore"),
                "base_boosted_value": row.get("baseBoostedValue"),
                "most_common_slot": row.get("mostCommonPosition"),
                "count_at_highest_slot": row.get("countAtHighestPosition"),
                "slot_of_highest_score": row.get("positionOfHighestScore"),
            }


def leaderboard_from_hv_section(rows: Sequence[DraftStatRow]) -> list[LeaderboardPlayer]:
    hv = [r for r in rows if r.section == HV_SECTION]
    ordered = sorted(
        hv,
        key=lambda r: (
            -(r.value if r.value is not None else float("-inf")),
            r.player_id,
        ),
    )
    out: list[LeaderboardPlayer] = []
    for rank, row in enumerate(ordered, start=1):
        out.append(
            LeaderboardPlayer(
                player_id=row.player_id,
                name=row.display_name,
                team_id=row.team_id,
                real_score=row.value,
                base=row.base_boosted_value,
                card_boost=row.card_boost,
                slot=row.most_common_slot,
                drafts=row.draft_count,
                value=row.value,
                rank=rank,
            )
        )
    return out


def leaderboard_from_reconstruction(
    parsed: ParsedContest, *, top_n: int | None = None
) -> tuple[list[LeaderboardPlayer], str]:
    """Fall back to reconstructed high-TV board from all draft_stats values."""

    n = top_n if top_n is not None else max(5, len({r.player_id for r in parsed.draft_stats}))
    board = high_tv_board_from_draft_stats(parsed, top_n=n)
    by_id = {row.player_id: row for row in parsed.draft_stats}
    values = {
        row.player_id: float(row.value) for row in parsed.draft_stats if row.value is not None
    }
    players: list[LeaderboardPlayer] = []
    if board is None or not board.value_ranked_player_ids:
        return players, "unreconstructable"
    for rank, player_id in enumerate(board.value_ranked_player_ids, start=1):
        row = by_id.get(player_id)
        score = values.get(player_id)
        players.append(
            LeaderboardPlayer(
                player_id=player_id,
                name=None if row is None else row.display_name,
                team_id=None if row is None else row.team_id,
                real_score=score,
                base=None if row is None else row.base_boosted_value,
                card_boost=None if row is None else row.card_boost,
                slot=None if row is None else row.most_common_slot,
                drafts=None if row is None else row.draft_count,
                value=score,
                rank=rank,
            )
        )
    return players, board.source


def extract_matchup_links(
    *,
    parsed: ParsedContest,
    draftinfo: Mapping[str, Any] | None,
    stats: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Collect contest→game links when Corpus C payloads expose them."""

    game_ids: list[int] = []
    games: list[dict[str, Any]] = []

    if parsed.contest.game_id is not None:
        game_ids.append(int(parsed.contest.game_id))

    for source in (draftinfo, stats):
        if not isinstance(source, Mapping):
            continue
        for key in ("games", "matchups", "gameLinks", "slateGames"):
            raw = source.get(key)
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict):
                        gid = item.get("id") or item.get("gameId")
                        if isinstance(gid, int) or (isinstance(gid, str) and gid.isdigit()):
                            game_ids.append(int(gid))
                        games.append(
                            {
                                "game_id": int(gid) if gid is not None else None,
                                "home_team_key": (item.get("homeTeam") or {}).get("key")
                                if isinstance(item.get("homeTeam"), dict)
                                else item.get("homeTeamKey"),
                                "away_team_key": (item.get("awayTeam") or {}).get("key")
                                if isinstance(item.get("awayTeam"), dict)
                                else item.get("awayTeamKey"),
                                "day": item.get("day"),
                                "home_team_id": item.get("homeTeamId"),
                                "away_team_id": item.get("awayTeamId"),
                            }
                        )
                    elif isinstance(item, int):
                        game_ids.append(item)

    unique_ids = sorted(set(game_ids))
    return {
        "schema_version": SCHEMA_VERSION,
        "contest_id": parsed.contest.contest_id,
        "slate_date": parsed.contest.day.isoformat(),
        "contest_game_id": parsed.contest.game_id,
        "game_ids": unique_ids,
        "games": games,
        "corpus_g_paths": [
            f"data/raw/corpus_g/{parsed.contest.season or parsed.contest.day.year}/{gid}/"
            for gid in unique_ids
        ],
        "present": bool(unique_ids),
    }


def build_total_value_document(
    parsed: ParsedContest,
    players: Sequence[LeaderboardPlayer],
    *,
    hv_source: str,
) -> dict[str, Any]:
    record = parsed.contest
    return {
        "schema_version": SCHEMA_VERSION,
        "sport": "nfl",
        "contest_id": record.contest_id,
        "slate_date": record.day.isoformat(),
        "season": record.season,
        "section": HV_SECTION,
        "source": hv_source,
        "player_count": len(players),
        "players": [p.to_dict() for p in players],
        "exported_at": utc_now_iso(),
    }


def write_draft_stats_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    lines = [
        json.dumps(dict(row), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for row in rows
    ]
    payload = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(path, payload, mode=0o600)


def export_one_contest(
    store: ContestStore,
    contest_id: int,
    export_root: Path,
) -> ContestExportResult:
    gaps: list[str] = []
    try:
        parsed = load_contest(store, contest_id)
    except (ContestParseError, ValueError, KeyError, TypeError) as exc:
        return ContestExportResult(
            contest_id=contest_id,
            slate_date=None,
            season=None,
            status="error",
            gaps=["parse_error"],
            error=str(exc),
        )
    if parsed is None:
        return ContestExportResult(
            contest_id=contest_id,
            slate_date=None,
            season=None,
            status="skipped",
            gaps=["parse_error"],
            error="load_contest_returned_none",
        )

    record = parsed.contest
    slate_date = record.day.isoformat()
    year = int(record.season) if record.season is not None else record.day.year
    out_dir = contest_export_dir(
        export_root, year=year, slate_date=slate_date, contest_id=contest_id
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_stats = store.read_route(contest_id, "stats")
    draftinfo = store.read_route(contest_id, "draftinfo")
    if raw_stats is None:
        gaps.append("missing_stats")

    raw_rows = list(iter_raw_draft_stat_rows(raw_stats or {}, contest_id=contest_id))
    section_names = sorted({str(r["section"]) for r in raw_rows})
    write_draft_stats_jsonl(out_dir / DRAFT_STATS_FILENAME, raw_rows)

    hv_players = leaderboard_from_hv_section(parsed.draft_stats)
    if hv_players:
        hv_source = f"draft_stats.{HV_SECTION}"
    else:
        gaps.append("missing_hv_section")
        hv_players, hv_source = leaderboard_from_reconstruction(parsed)
        if not hv_players:
            gaps.append("hv_board_unreconstructable")
            hv_source = "unreconstructable"

    tv_doc = build_total_value_document(parsed, hv_players, hv_source=hv_source)
    atomic_write_json(out_dir / TOTAL_VALUE_FILENAME, tv_doc, mode=0o600)

    matchups = extract_matchup_links(parsed=parsed, draftinfo=draftinfo, stats=raw_stats)
    if not matchups["present"]:
        gaps.append("no_matchup_links")
    atomic_write_json(out_dir / MATCHUPS_FILENAME, matchups, mode=0o600)

    status: Literal["exported", "partial", "skipped", "error"]
    if hv_players and "missing_stats" not in gaps:
        status = "partial" if gaps else "exported"
    elif hv_players:
        status = "partial"
    else:
        status = "partial" if raw_rows else "skipped"

    return ContestExportResult(
        contest_id=contest_id,
        slate_date=slate_date,
        season=record.season,
        status=status,
        hv_source=hv_source,
        player_count=len(hv_players),
        section_count=len(section_names),
        matchup_game_ids=list(matchups["game_ids"]),
        gaps=gaps,
        export_dir=str(out_dir),
    )


def write_coverage_manifest(export_root: Path, summary: ExportSummary) -> Path:
    path = export_root / COVERAGE_MANIFEST_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, summary.to_dict(), mode=0o600)
    return path


def export_corpus_c(
    *,
    corpus_root: Path | None = None,
    export_root: Path | None = None,
    project: Path | None = None,
    contest_ids: Sequence[int] | None = None,
) -> ExportSummary:
    """Walk Corpus C and write HV / draft_stats / matchup exports + coverage gaps."""

    c_root = resolve_corpus_c_root(corpus_root, project=project)
    e_root = resolve_export_root(export_root, project=project)
    e_root.mkdir(parents=True, exist_ok=True)

    gaps: list[dict[str, Any]] = []
    results: list[ContestExportResult] = []
    volume_empty = False

    if not c_root.exists():
        volume_empty = True
        gaps.append(
            {
                "kind": "corpus_c_missing",
                "path": str(c_root),
                "detail": (
                    "Corpus C root missing. On Railway mount volume at "
                    "/app/nfl-oracle/data and set NFL_CORPUS_C_ROOT or use "
                    "default data/raw/corpus_c under that mount."
                ),
            }
        )
    else:
        store = ContestStore(c_root)
        ids = list(contest_ids) if contest_ids is not None else store.collected_ids()
        if not ids:
            volume_empty = True
            gaps.append(
                {
                    "kind": "corpus_c_empty",
                    "path": str(c_root),
                    "detail": "Corpus C root exists but has no contest directories with meta.json",
                }
            )
        for contest_id in ids:
            result = export_one_contest(store, contest_id, e_root)
            results.append(result)
            for gap in result.gaps:
                gaps.append(
                    {
                        "kind": gap,
                        "contest_id": contest_id,
                        "slate_date": result.slate_date,
                        "detail": result.error,
                    }
                )

    summary = ExportSummary(
        corpus_c_root=str(c_root),
        export_root=str(e_root),
        contests_seen=len(results),
        contests_exported=sum(1 for r in results if r.status == "exported"),
        contests_partial=sum(1 for r in results if r.status == "partial"),
        contests_skipped=sum(1 for r in results if r.status == "skipped"),
        contests_errored=sum(1 for r in results if r.status == "error"),
        gaps=gaps,
        results=results,
        volume_empty=volume_empty,
        updated_at=utc_now_iso(),
    )
    write_coverage_manifest(e_root, summary)
    # Content-address empty scaffold marker when volume is empty so CI can prove
    # the path without Real Sports or a live volume.
    if volume_empty:
        marker = {
            "schema_version": SCHEMA_VERSION,
            "sport": "nfl",
            "status": "scaffold",
            "volume_empty": True,
            "updated_at": summary.updated_at,
        }
        atomic_write_json(e_root / "scaffold.json", marker, mode=0o600)
        _ = sha256_bytes(json.dumps(marker, sort_keys=True).encode())
    return summary

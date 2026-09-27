"""Offline-safe export stubs from existing durable stores into corpus layout.

Maps what already exists today:

WNBA Postgres (see ``wnba-oracle/scripts/backup_corpus.py``):
  - slate_labels → total_value_leaderboards (section=highestBoostedValuePlayers)
    and players / combined_stats rows for other draftStats sections
  - contest_leaderboards → lineups
  - wnba_game_logs → matchups (+ combined box metrics when present)
  - job1_enrichment → slate_rosters (draftable pool snapshot)

NFL Corpus G (``nfl-oracle`` ``data/raw/corpus_g``):
  - players.json → players
  - stats.json → combined_stats / matchups (playerBoxScores + game context)
  - feed.json → matchups / recorded_states (game + plays clocks)

NFL Corpus C (``data/raw/corpus_c``) when present:
  - stats.json draftStats highestBoostedValuePlayers → total_value_leaderboards
  - entries.json → lineups
  - draftinfo.json → slate_rosters / team_weights (when fields exist)

Families with no durable source yet stay ``stub`` (NBA/NHL, team_weights /
averages / recorded_states gaps). No Real Sports network calls. No credential
minting.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from oracle_core.artifacts import atomic_write_json

from realsports_corpus.coverage_manifest import (
    CoverageManifest,
    build_empty_manifest,
    record_family_status,
)
from realsports_corpus.layout import (
    REQUIRED_VARIABLE_FAMILIES,
    SlateKey,
    VariableFamily,
    ensure_slate_layout,
    family_dir,
)

HV_SECTION = "highestBoostedValuePlayers"

# SQL used when a live WNBA engine is wired later (not executed by stubs).
WNBA_EXPORT_SQL: dict[VariableFamily, str] = {
    "total_value_leaderboards": (
        "SELECT contest_id, slate_date, section, platform_player_id, display_name, "
        "team_key, card_boost, drafts, real_score, ingested_at "
        "FROM slate_labels WHERE section = 'highestBoostedValuePlayers' "
        "ORDER BY slate_date, contest_id, platform_player_id"
    ),
    "players": (
        "SELECT DISTINCT ON (platform_player_id) platform_player_id, display_name, "
        "team_key, slate_date FROM slate_labels "
        "ORDER BY platform_player_id, slate_date DESC"
    ),
    "lineups": (
        "SELECT contest_id, slate_date, entry_id, rank, score, lineup::text AS lineup, "
        "num_brawlers, ingested_at FROM contest_leaderboards "
        "ORDER BY slate_date, contest_id, rank"
    ),
    "slate_rosters": (
        "SELECT slate_date, platform_player_id, display_name, team, position, "
        "card_boost, captured_at FROM job1_enrichment "
        "ORDER BY slate_date, platform_player_id"
    ),
    "matchups": ("SELECT * FROM wnba_game_logs ORDER BY game_date, game_id, player_id"),
    "combined_stats": (
        "SELECT contest_id, slate_date, section, platform_player_id, display_name, "
        "team_key, card_boost, drafts, real_score FROM slate_labels "
        "WHERE section <> 'highestBoostedValuePlayers' "
        "ORDER BY slate_date, section, platform_player_id"
    ),
    "team_weights": "-- no durable WNBA table yet; stub only",
    "averages": "-- no durable WNBA RS averages table yet; stub only",
    "recorded_states": "-- no durable WNBA recorded_states table yet; stub only",
    "draft_stats_all_sections": (
        "SELECT contest_id, slate_date, section, platform_player_id, display_name, "
        "team_key, card_boost, drafts, real_score FROM slate_labels "
        "ORDER BY slate_date, section, platform_player_id"
    ),
    "feeds": "-- no durable WNBA feeds table yet; stub only",
}


@dataclass(frozen=True)
class ExportResult:
    family: VariableFamily
    path: Path
    rows: int
    source: str
    status: str


def _write_rows(
    path: Path, *, rows: Sequence[Mapping[str, Any]], meta: Mapping[str, Any]
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"meta": dict(meta), "rows": [dict(r) for r in rows]}
    atomic_write_json(path, payload)
    return len(rows)


def export_wnba_slate_labels_rows(
    *,
    corpus_root: Path,
    key: SlateKey,
    slate_label_rows: Sequence[Mapping[str, Any]],
) -> list[ExportResult]:
    """Project in-memory slate_labels rows into TV + players + combined_stats."""

    ensure_slate_layout(corpus_root, key)
    hv = [r for r in slate_label_rows if str(r.get("section") or "") == HV_SECTION]
    other = [r for r in slate_label_rows if str(r.get("section") or "") != HV_SECTION]
    players: dict[str, dict[str, Any]] = {}
    for row in slate_label_rows:
        pid = str(row.get("platform_player_id") or row.get("player_id") or "")
        if not pid or pid in players:
            continue
        players[pid] = {
            "platform_player_id": pid,
            "display_name": row.get("display_name") or row.get("name"),
            "team_key": row.get("team_key") or row.get("team"),
        }

    results: list[ExportResult] = []
    tv_path = (
        family_dir(corpus_root, key, "total_value_leaderboards")
        / "highestBoostedValuePlayers.json"
    )
    n = _write_rows(
        tv_path,
        rows=hv,
        meta={
            "source": "wnba.slate_labels",
            "section": HV_SECTION,
            "slate_date": key.slate_date,
        },
    )
    results.append(
        ExportResult(
            "total_value_leaderboards",
            tv_path,
            n,
            "wnba.slate_labels",
            "present" if n else "stub",
        )
    )

    players_path = family_dir(corpus_root, key, "players") / "players.json"
    n = _write_rows(
        players_path,
        rows=list(players.values()),
        meta={"source": "wnba.slate_labels", "slate_date": key.slate_date},
    )
    results.append(
        ExportResult(
            "players", players_path, n, "wnba.slate_labels", "present" if n else "stub"
        )
    )

    combined_path = (
        family_dir(corpus_root, key, "combined_stats") / "draft_stats_other.json"
    )
    n = _write_rows(
        combined_path,
        rows=other,
        meta={"source": "wnba.slate_labels", "exclude_section": HV_SECTION},
    )
    results.append(
        ExportResult(
            "combined_stats",
            combined_path,
            n,
            "wnba.slate_labels",
            "present" if n else "stub",
        )
    )
    return results


def export_wnba_leaderboard_rows(
    *,
    corpus_root: Path,
    key: SlateKey,
    leaderboard_rows: Sequence[Mapping[str, Any]],
) -> ExportResult:
    ensure_slate_layout(corpus_root, key)
    path = family_dir(corpus_root, key, "lineups") / "contest_leaderboards.json"
    n = _write_rows(
        path,
        rows=leaderboard_rows,
        meta={"source": "wnba.contest_leaderboards", "slate_date": key.slate_date},
    )
    return ExportResult(
        "lineups", path, n, "wnba.contest_leaderboards", "present" if n else "stub"
    )


def export_wnba_game_log_rows(
    *,
    corpus_root: Path,
    key: SlateKey,
    game_log_rows: Sequence[Mapping[str, Any]],
) -> ExportResult:
    ensure_slate_layout(corpus_root, key)
    path = family_dir(corpus_root, key, "matchups") / "wnba_game_logs.json"
    n = _write_rows(
        path,
        rows=game_log_rows,
        meta={"source": "wnba.wnba_game_logs", "slate_date": key.slate_date},
    )
    return ExportResult(
        "matchups", path, n, "wnba.wnba_game_logs", "present" if n else "stub"
    )


def export_wnba_job1_roster_rows(
    *,
    corpus_root: Path,
    key: SlateKey,
    roster_rows: Sequence[Mapping[str, Any]],
) -> ExportResult:
    ensure_slate_layout(corpus_root, key)
    path = family_dir(corpus_root, key, "slate_rosters") / "job1_enrichment.json"
    n = _write_rows(
        path,
        rows=roster_rows,
        meta={"source": "wnba.job1_enrichment", "slate_date": key.slate_date},
    )
    return ExportResult(
        "slate_rosters", path, n, "wnba.job1_enrichment", "present" if n else "stub"
    )


def write_family_stubs(
    corpus_root: Path,
    key: SlateKey,
    families: Iterable[VariableFamily],
    *,
    reason: str,
) -> list[ExportResult]:
    ensure_slate_layout(corpus_root, key)
    out: list[ExportResult] = []
    for family in families:
        path = family_dir(corpus_root, key, family) / "STUB.json"
        atomic_write_json(
            path,
            {
                "meta": {
                    "source": "stub",
                    "status": "stub",
                    "reason": reason,
                    "slate_date": key.slate_date,
                    "sport": key.sport,
                    "sql_hint": WNBA_EXPORT_SQL.get(family),
                },
                "rows": [],
            },
        )
        out.append(ExportResult(family, path, 0, "stub", "stub"))
    return out


def export_nfl_corpus_g_game(
    *,
    corpus_root: Path,
    key: SlateKey,
    game_dir: Path,
) -> list[ExportResult]:
    """Map one Corpus G game directory into players / combined_stats / matchups."""

    ensure_slate_layout(corpus_root, key)
    game_dir = Path(game_dir)
    results: list[ExportResult] = []

    players_src = game_dir / "players.json"
    if players_src.is_file():
        raw = json.loads(players_src.read_text(encoding="utf-8"))
        rows = list(raw.get("players") or []) if isinstance(raw, dict) else []
        path = family_dir(corpus_root, key, "players") / f"{game_dir.name}_players.json"
        n = _write_rows(
            path,
            rows=rows if all(isinstance(r, dict) for r in rows) else [],
            meta={"source": "nfl.corpus_g.players", "game_dir": game_dir.name},
        )
        results.append(
            ExportResult(
                "players", path, n, "nfl.corpus_g", "present" if n else "partial"
            )
        )
    else:
        results.extend(
            write_family_stubs(
                corpus_root, key, ("players",), reason="corpus_g players.json missing"
            )
        )

    stats_src = game_dir / "stats.json"
    if stats_src.is_file():
        raw = json.loads(stats_src.read_text(encoding="utf-8"))
        boxes = list(raw.get("playerBoxScores") or []) if isinstance(raw, dict) else []
        path = (
            family_dir(corpus_root, key, "combined_stats")
            / f"{game_dir.name}_stats.json"
        )
        n = _write_rows(
            path,
            rows=boxes if all(isinstance(r, dict) for r in boxes) else [],
            meta={"source": "nfl.corpus_g.stats", "game_dir": game_dir.name},
        )
        results.append(
            ExportResult(
                "combined_stats", path, n, "nfl.corpus_g", "present" if n else "partial"
            )
        )
    else:
        results.extend(
            write_family_stubs(
                corpus_root,
                key,
                ("combined_stats",),
                reason="corpus_g stats.json missing",
            )
        )

    feed_src = game_dir / "feed.json"
    matchup_rows: list[dict[str, Any]] = []
    if feed_src.is_file():
        raw = json.loads(feed_src.read_text(encoding="utf-8"))
        game = raw.get("game") if isinstance(raw, dict) else None
        if isinstance(game, dict):
            matchup_rows.append(
                {
                    "game_id": game.get("id") or game.get("gameId"),
                    "home": game.get("homeTeam") or game.get("home"),
                    "away": game.get("awayTeam") or game.get("away"),
                    "day": game.get("day"),
                    "season": game.get("season"),
                    "status": game.get("status"),
                }
            )
        path = (
            family_dir(corpus_root, key, "matchups")
            / f"{game_dir.name}_feed_matchup.json"
        )
        n = _write_rows(
            path,
            rows=matchup_rows,
            meta={"source": "nfl.corpus_g.feed", "game_dir": game_dir.name},
        )
        results.append(
            ExportResult(
                "matchups", path, n, "nfl.corpus_g", "present" if n else "partial"
            )
        )

        # Feed is also the best existing recorded_states proxy (clocks / plays).
        state_path = (
            family_dir(corpus_root, key, "recorded_states")
            / f"{game_dir.name}_feed.json"
        )
        atomic_write_json(
            state_path,
            {
                "meta": {"source": "nfl.corpus_g.feed", "game_dir": game_dir.name},
                "payload": raw if isinstance(raw, dict) else {},
            },
        )
        results.append(
            ExportResult(
                "recorded_states",
                state_path,
                1 if isinstance(raw, dict) else 0,
                "nfl.corpus_g",
                "present" if isinstance(raw, dict) else "stub",
            )
        )
        feeds_path = (
            family_dir(corpus_root, key, "feeds") / f"{game_dir.name}_feed.json"
        )
        atomic_write_json(
            feeds_path,
            {
                "meta": {"source": "nfl.corpus_g.feed", "game_dir": game_dir.name},
                "payload": raw if isinstance(raw, dict) else {},
            },
        )
        results.append(
            ExportResult(
                "feeds",
                feeds_path,
                1 if isinstance(raw, dict) else 0,
                "nfl.corpus_g",
                "present" if isinstance(raw, dict) else "stub",
            )
        )
    else:
        results.extend(
            write_family_stubs(
                corpus_root,
                key,
                ("matchups", "recorded_states", "feeds"),
                reason="corpus_g feed.json missing",
            )
        )

    return results


def export_nfl_corpus_c_contest(
    *,
    corpus_root: Path,
    key: SlateKey,
    contest_dir: Path,
) -> list[ExportResult]:
    """Map one Corpus C contest directory into TV / lineups / slate_rosters stubs."""

    ensure_slate_layout(corpus_root, key)
    contest_dir = Path(contest_dir)
    results: list[ExportResult] = []

    stats_src = contest_dir / "stats.json"
    if stats_src.is_file():
        raw = json.loads(stats_src.read_text(encoding="utf-8"))
        hv_rows: list[dict[str, Any]] = []
        for section in raw.get("draftStats") or [] if isinstance(raw, dict) else []:
            if not isinstance(section, dict):
                continue
            section_name = section.get("sectionName") or section.get("section")
            if section_name != HV_SECTION:
                continue
            for player in section.get("players") or []:
                if isinstance(player, dict):
                    hv_rows.append(player)
        path = (
            family_dir(corpus_root, key, "total_value_leaderboards")
            / f"{contest_dir.name}_hv.json"
        )
        n = _write_rows(
            path,
            rows=hv_rows,
            meta={
                "source": "nfl.corpus_c.stats",
                "section": HV_SECTION,
                "contest_dir": contest_dir.name,
            },
        )
        results.append(
            ExportResult(
                "total_value_leaderboards",
                path,
                n,
                "nfl.corpus_c",
                "present" if n else "partial",
            )
        )
        # Full draftStats dump (all sections) for complete variable capture.
        all_sections = (
            list(raw.get("draftStats") or []) if isinstance(raw, dict) else []
        )
        draft_path = (
            family_dir(corpus_root, key, "draft_stats_all_sections")
            / f"{contest_dir.name}_draft_stats.json"
        )
        atomic_write_json(
            draft_path,
            {
                "meta": {
                    "source": "nfl.corpus_c.stats",
                    "contest_dir": contest_dir.name,
                },
                "draftStats": all_sections,
            },
        )
        results.append(
            ExportResult(
                "draft_stats_all_sections",
                draft_path,
                len(all_sections),
                "nfl.corpus_c",
                "present" if all_sections else "partial",
            )
        )
    else:
        results.extend(
            write_family_stubs(
                corpus_root,
                key,
                ("total_value_leaderboards", "draft_stats_all_sections"),
                reason="corpus_c stats.json missing",
            )
        )

    entries_src = contest_dir / "entries.json"
    if entries_src.is_file():
        raw = json.loads(entries_src.read_text(encoding="utf-8"))
        entries = list(raw.get("entries") or raw.get("info", {}).get("entries") or [])
        if isinstance(raw, dict) and not entries and isinstance(raw.get("info"), dict):
            entries = list(raw["info"].get("entries") or [])
        rows = [e for e in entries if isinstance(e, dict)]
        path = (
            family_dir(corpus_root, key, "lineups") / f"{contest_dir.name}_entries.json"
        )
        n = _write_rows(
            path,
            rows=rows,
            meta={"source": "nfl.corpus_c.entries", "contest_dir": contest_dir.name},
        )
        results.append(
            ExportResult(
                "lineups", path, n, "nfl.corpus_c", "present" if n else "partial"
            )
        )
    else:
        results.extend(
            write_family_stubs(
                corpus_root, key, ("lineups",), reason="corpus_c entries missing"
            )
        )

    draft_src = contest_dir / "draftinfo.json"
    if draft_src.is_file():
        raw = json.loads(draft_src.read_text(encoding="utf-8"))
        info = raw.get("info") if isinstance(raw, dict) else None
        pool = []
        if isinstance(info, dict):
            for key_name in ("players", "playerPool", "draftPlayers"):
                cand = info.get(key_name)
                if isinstance(cand, list):
                    pool = [p for p in cand if isinstance(p, dict)]
                    break
        path = (
            family_dir(corpus_root, key, "slate_rosters")
            / f"{contest_dir.name}_draftinfo.json"
        )
        n = _write_rows(
            path,
            rows=pool,
            meta={"source": "nfl.corpus_c.draftinfo", "contest_dir": contest_dir.name},
        )
        results.append(
            ExportResult(
                "slate_rosters", path, n, "nfl.corpus_c", "present" if n else "partial"
            )
        )
        # team_weights: persist draftinfo multipliers / squad hints when present.
        weights_path = (
            family_dir(corpus_root, key, "team_weights")
            / f"{contest_dir.name}_draftinfo_weights.json"
        )
        atomic_write_json(
            weights_path,
            {
                "meta": {
                    "source": "nfl.corpus_c.draftinfo",
                    "contest_dir": contest_dir.name,
                },
                "defaultMultipliers": (info or {}).get("defaultMultipliers")
                if isinstance(info, dict)
                else None,
                "rows": [],
            },
        )
        results.append(
            ExportResult(
                "team_weights",
                weights_path,
                1 if isinstance(info, dict) and info.get("defaultMultipliers") else 0,
                "nfl.corpus_c",
                "partial",
            )
        )
    else:
        results.extend(
            write_family_stubs(
                corpus_root,
                key,
                ("slate_rosters", "team_weights"),
                reason="corpus_c draftinfo missing",
            )
        )

    return results


def export_wnba_backup_csvs(
    *,
    corpus_root: Path,
    key: SlateKey,
    backup_dir: Path,
) -> list[ExportResult]:
    """Read WNBA backup CSVs (slate_labels / contest_leaderboards) if present."""

    backup_dir = Path(backup_dir)
    results: list[ExportResult] = []
    labels_path = backup_dir / "slate_labels.csv"
    if labels_path.is_file():
        rows = _read_csv(labels_path)
        day_rows = [r for r in rows if str(r.get("slate_date") or "") == key.slate_date]
        results.extend(
            export_wnba_slate_labels_rows(
                corpus_root=corpus_root, key=key, slate_label_rows=day_rows
            )
        )
    boards_path = backup_dir / "contest_leaderboards.csv"
    if boards_path.is_file():
        rows = _read_csv(boards_path)
        day_rows = [r for r in rows if str(r.get("slate_date") or "") == key.slate_date]
        results.append(
            export_wnba_leaderboard_rows(
                corpus_root=corpus_root, key=key, leaderboard_rows=day_rows
            )
        )
    return results


def apply_export_results_to_manifest(
    manifest: CoverageManifest | None,
    *,
    sport: str,
    results: Sequence[ExportResult],
    year: int | None = None,
    slate_date: str | None = None,
) -> CoverageManifest:
    """Fold export stub outcomes into coverage_manifest family statuses."""

    current = manifest or build_empty_manifest()
    by_family: dict[VariableFamily, list[ExportResult]] = {
        f: [] for f in REQUIRED_VARIABLE_FAMILIES
    }
    for result in results:
        by_family[result.family].append(result)

    for family, items in by_family.items():
        if not items:
            continue
        total = sum(i.rows for i in items)
        statuses = {i.status for i in items}
        if statuses == {"present"} and total > 0:
            status = "present"
        elif "present" in statuses or "partial" in statuses:
            status = "partial"
        else:
            status = "stub"
        note = "; ".join(sorted({i.source for i in items}))
        current = record_family_status(
            current,
            sport=sport,  # type: ignore[arg-type]
            family=family,
            status=status,  # type: ignore[arg-type]
            artifact_count=total,
            note=note,
            year=year,
            slate_date=slate_date,
        )
    return current


def scaffold_all_stub_families(corpus_root: Path, key: SlateKey) -> list[ExportResult]:
    """Ensure every required family directory exists with an explicit STUB artifact."""

    return write_family_stubs(
        corpus_root,
        key,
        REQUIRED_VARIABLE_FAMILIES,
        reason="layout scaffold; wire durable export when source exists",
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))

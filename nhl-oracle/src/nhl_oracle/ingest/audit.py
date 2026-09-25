"""Read-only Real Sports NHL contract audit + redacted corpus seed.

Never submits contests or mutates provider state. Writes redacted fixtures via
NhlCorpusStore and an audit record with contest_entry=False.

When the current NHL slate has no contests (off-season / between cards), this
module may fall back to scanning recent global contest IDs for sport=nhl and
uses that historical contest for contract-field resolution while still
capturing the current slate games/players for coverage denominators.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from nhl_oracle.common.paths import resolve_project_root
from nhl_oracle.contract.discovery import discover_contract
from nhl_oracle.contract.gates import evaluate_nhl_audit
from nhl_oracle.contract.schema import NhlAuditFixture
from nhl_oracle.ingest.provenance import NhlCorpusStore
from nhl_oracle.ingest.realsports import (
    BASE,
    SPORT,
    RequestHeaders,
    capture_live_headers,
    fetch_contest_draftinfo,
    fetch_contest_meta,
    fetch_contest_stats,
    fetch_game_players,
    fetch_home_day,
    fetch_home_next,
    headers_or_capture,
    materialize_storage_state_from_env,
    try_fetch_contest_meta,
)
from nhl_oracle.ingest.redact import assert_no_identity_leak, redact_corpus_payload

# Known historical NHL contest observed on the shared Real Sports id sequence
# (used only when the live slate has no NHL contests).
_DEFAULT_HISTORICAL_NHL_CONTEST_IDS = (1901,)
_DEFAULT_SCAN_SEED = 2200
_DEFAULT_SCAN_MIN = 1800


@dataclass(frozen=True)
class AuditCoverage:
    games_scheduled: int
    games_captured: int
    players_seen: int
    players_resolved: int
    contest_ids: tuple[int, ...]
    game_ids: tuple[int, ...]


@dataclass(frozen=True)
class AuditResult:
    contest_entry: bool
    captured_at: str
    contract: dict[str, Any]
    open_questions: tuple[str, ...]
    coverage: AuditCoverage
    gates_ok: bool
    gate_blocked: tuple[str, ...]
    notes: tuple[str, ...]
    corpus_root: str
    fixture_paths: tuple[str, ...]


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_corpus_root() -> Path:
    return resolve_project_root(__file__)


def _season_from_day(day: str | None) -> int | None:
    if not day or len(day) < 4 or not day[:4].isdigit():
        return None
    return int(day[:4])


def _extract_day(home: dict[str, Any]) -> str | None:
    raw = home.get("latestDayContent")
    if isinstance(raw, dict):
        day = raw.get("day")
        if isinstance(day, str):
            return day
    content = home.get("content")
    if isinstance(content, dict):
        day = content.get("day")
        if isinstance(day, str):
            return day
    return None


def _extract_games(day_content: dict[str, Any]) -> list[dict[str, Any]]:
    content = day_content.get("content")
    if isinstance(content, dict) and isinstance(content.get("games"), list):
        return [g for g in content["games"] if isinstance(g, dict)]
    if isinstance(day_content.get("games"), list):
        return [g for g in day_content["games"] if isinstance(g, dict)]
    latest = day_content.get("latestDayContent")
    if isinstance(latest, dict) and isinstance(latest.get("games"), list):
        return [g for g in latest["games"] if isinstance(g, dict)]
    return []


def _extract_contest_ids(day_content: dict[str, Any]) -> list[int]:
    content = day_content.get("content")
    if not isinstance(content, dict):
        content = day_content
    config = content.get("config") if isinstance(content, dict) else None
    daily = config.get("dailyDraftInfo") if isinstance(config, dict) else None
    ids: list[int] = []
    if isinstance(daily, dict):
        contests = daily.get("contests")
        if isinstance(contests, list):
            for row in contests:
                if isinstance(row, dict) and isinstance(row.get("id"), int):
                    ids.append(row["id"])
                elif isinstance(row, int):
                    ids.append(row)
    return ids


def _game_id(game: dict[str, Any]) -> int | None:
    for key in ("id", "gameId"):
        raw = game.get(key)
        if isinstance(raw, int) and raw > 0:
            return raw
    return None


def _contest_sport(meta: dict[str, Any]) -> str | None:
    info = meta.get("info") if isinstance(meta.get("info"), dict) else {}
    contest = info.get("contest") if isinstance(info, dict) else None
    if not isinstance(contest, dict):
        return None
    sport = contest.get("sport")
    return sport if isinstance(sport, str) else None


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


def _env_contest_ids(name: str) -> list[int]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return []
    out: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
    return out


async def _resolve_nhl_contest_ids(
    client: httpx.AsyncClient,
    headers_holder: dict[str, RequestHeaders],
    refresh: Any,
    slate_ids: list[int],
) -> tuple[list[int], list[str]]:
    """Prefer live slate contests; otherwise find historical NHL contest ids."""

    notes: list[str] = []
    if slate_ids:
        notes.append(f"using_slate_contest_ids={slate_ids}")
        return slate_ids, notes

    notes.append("no_nhl_contest_ids_on_slate; attempting_historical_fallback")
    candidates: list[int] = []
    for cid in _env_contest_ids("NHL_AUDIT_CONTEST_IDS"):
        if cid not in candidates:
            candidates.append(cid)
    for cid in _DEFAULT_HISTORICAL_NHL_CONTEST_IDS:
        if cid not in candidates:
            candidates.append(cid)

    found: list[int] = []
    for cid in candidates:
        meta = await try_fetch_contest_meta(
            client, cid, headers_holder["headers"], refresh_headers=refresh
        )
        if meta is None:
            notes.append(f"historical_candidate_{cid}_missing")
            continue
        sport = _contest_sport(meta)
        if sport == "nhl":
            found.append(cid)
            notes.append(f"historical_nhl_contest_id={cid}")
            break
        notes.append(f"historical_candidate_{cid}_sport={sport}")

    if found:
        return found, notes

    seed = _env_int("NHL_AUDIT_CONTEST_SEED", _DEFAULT_SCAN_SEED)
    scan_min = _env_int("NHL_AUDIT_CONTEST_SCAN_MIN", _DEFAULT_SCAN_MIN)
    notes.append(f"scanning_contest_ids_from_{seed}_to_{scan_min}_for_nhl")
    for cid in range(seed, scan_min - 1, -1):
        if cid in candidates:
            continue
        meta = await try_fetch_contest_meta(
            client, cid, headers_holder["headers"], refresh_headers=refresh
        )
        if meta is None:
            continue
        if _contest_sport(meta) == "nhl":
            found.append(cid)
            notes.append(f"scanned_nhl_contest_id={cid}")
            break
    if not found:
        raise RuntimeError("no_nhl_contest_ids_on_slate_or_historical_scan")
    return found, notes


async def run_live_audit(
    *,
    corpus_root: Path | None = None,
    persist_fixtures: bool = True,
) -> AuditResult:
    """Fetch live NHL contest/game/player payloads (read-only) and seed corpus."""

    materialize_storage_state_from_env()
    captured_at = _now_iso()
    root = Path(corpus_root) if corpus_root is not None else default_corpus_root()
    store = NhlCorpusStore(root)
    fixture_paths: list[str] = []
    fallback_notes: list[str] = []

    headers = await headers_or_capture()
    headers_holder: dict[str, RequestHeaders] = {"headers": headers}

    async def refresh() -> RequestHeaders:
        refreshed = await capture_live_headers()
        headers_holder["headers"] = refreshed
        return refreshed

    async with httpx.AsyncClient(timeout=30.0) as client:
        home = await fetch_home_next(client, headers_holder["headers"], refresh_headers=refresh)
        day = _extract_day(home)
        day_payload: dict[str, Any] = home
        if day:
            day_payload = await fetch_home_day(
                client, day, headers_holder["headers"], refresh_headers=refresh
            )
        slate_ids = _extract_contest_ids(day_payload) or _extract_contest_ids(home)
        games = _extract_games(day_payload) or _extract_games(home)
        game_ids = [gid for gid in (_game_id(g) for g in games) if gid is not None]
        season = _season_from_day(day)

        if persist_fixtures:
            redacted_home = redact_corpus_payload(home)
            assert_no_identity_leak(redacted_home)
            art = store.persist_endpoint(
                game_id=0,
                season=season,
                endpoint="home",
                payload=redacted_home,
                source_url=f"{BASE}/home/{SPORT}/next",
                captured_at=captured_at,
            )
            fixture_paths.append(str(art.path))
            if day and day_payload is not home:
                redacted_day = redact_corpus_payload(day_payload)
                assert_no_identity_leak(redacted_day)
                art = store.persist_endpoint(
                    game_id=0,
                    season=season,
                    endpoint="home",
                    payload=redacted_day,
                    source_url=f"{BASE}/home/{SPORT}/day/next?day={day}",
                    captured_at=captured_at,
                )
                fixture_paths.append(str(art.path))

        contest_ids, fallback_notes = await _resolve_nhl_contest_ids(
            client, headers_holder, refresh, slate_ids
        )
        contest_id = contest_ids[0]
        meta = await fetch_contest_meta(
            client, contest_id, headers_holder["headers"], refresh_headers=refresh
        )
        draftinfo = await fetch_contest_draftinfo(
            client, contest_id, headers_holder["headers"], refresh_headers=refresh
        )
        contest_stats = await fetch_contest_stats(
            client, contest_id, headers_holder["headers"], refresh_headers=refresh
        )
        sport = _contest_sport(meta)
        if sport not in (None, "nhl"):
            raise RuntimeError(f"contest_sport_mismatch:{sport}")

        if persist_fixtures:
            for endpoint, payload, url in (
                ("contest", meta, f"{BASE}/games/playerratingcontest/{contest_id}"),
                (
                    "draftinfo",
                    draftinfo,
                    f"{BASE}/games/playerratingcontest/{contest_id}/draftinfo",
                ),
                (
                    "stats",
                    contest_stats,
                    f"{BASE}/games/playerratingcontest/{contest_id}/stats",
                ),
            ):
                redacted = redact_corpus_payload(payload)
                assert_no_identity_leak(redacted)
                art = store.persist_endpoint(
                    game_id=contest_id,
                    season=season,
                    endpoint=endpoint,  # type: ignore[arg-type]
                    payload=redacted,
                    source_url=url,
                    captured_at=captured_at,
                )
                fixture_paths.append(str(art.path))

        players_payloads: list[dict[str, Any]] = []
        captured_game_ids: list[int] = []
        for gid in game_ids:
            players = await fetch_game_players(
                client, gid, headers_holder["headers"], refresh_headers=refresh
            )
            players_payloads.append(players)
            captured_game_ids.append(gid)
            if persist_fixtures:
                redacted = redact_corpus_payload(players)
                assert_no_identity_leak(redacted)
                art = store.persist_endpoint(
                    game_id=gid,
                    season=season,
                    endpoint="players",
                    payload=redacted,
                    source_url=f"{BASE}/games/{gid}/sport/{SPORT}/players",
                    captured_at=captured_at,
                )
                fixture_paths.append(str(art.path))

    contract, evidence, candidates = discover_contract(
        meta=meta,
        draftinfo=draftinfo,
        players_payloads=players_payloads,
        contest_ids=tuple(contest_ids),
        game_ids=tuple(captured_game_ids),
        games_scheduled=len(game_ids),
        games_captured=len(captured_game_ids),
        captured_at=captured_at,
        contest_stats=contest_stats,
    )
    merged_notes = tuple(fallback_notes) + evidence.notes
    fixture = NhlAuditFixture(
        contract=contract,
        candidates=candidates,
        expected_roster_size=contract.roster_size,
    )
    decision_at = datetime.now(UTC)
    report = evaluate_nhl_audit(fixture, decision_at=decision_at)

    coverage = AuditCoverage(
        games_scheduled=evidence.games_scheduled,
        games_captured=evidence.games_captured,
        players_seen=evidence.players_seen,
        players_resolved=evidence.players_resolved,
        contest_ids=evidence.contest_ids,
        game_ids=evidence.game_ids,
    )
    result = AuditResult(
        contest_entry=False,
        captured_at=captured_at,
        contract={
            "sport": contract.sport,
            "format": str(contract.format),
            "lock_scope": str(contract.lock_scope),
            "boost_regime": str(contract.boost_regime),
            "score_value_label": contract.score_value_label,
            "roster_size": contract.roster_size,
            "slot_multipliers": list(contract.slot_multipliers)
            if contract.slot_multipliers is not None
            else None,
            "goalie_eligible": contract.goalie_eligible,
        },
        open_questions=contract.open_questions(),
        coverage=coverage,
        gates_ok=report.all_gates_ok,
        gate_blocked=report.blocked_reasons,
        notes=merged_notes,
        corpus_root=str(root),
        fixture_paths=tuple(fixture_paths),
    )

    if persist_fixtures:
        audit_payload = {
            "contest_entry": False,
            "observation_only": True,
            "captured_at": captured_at,
            "contract": result.contract,
            "open_questions": list(result.open_questions),
            "coverage": asdict(coverage),
            "gates_ok": result.gates_ok,
            "gate_blocked": list(result.gate_blocked),
            "notes": list(result.notes),
            "fixture_paths": list(result.fixture_paths),
        }
        art = store.persist_endpoint(
            game_id=contest_id,
            season=season,
            endpoint="audit",
            payload=audit_payload,
            source_url=f"nhl_oracle.ingest.audit:{captured_at}",
            captured_at=captured_at,
            decision_at=decision_at.isoformat().replace("+00:00", "Z"),
        )
        fixture_paths.append(str(art.path))
        result = AuditResult(
            contest_entry=False,
            captured_at=result.captured_at,
            contract=result.contract,
            open_questions=result.open_questions,
            coverage=result.coverage,
            gates_ok=result.gates_ok,
            gate_blocked=result.gate_blocked,
            notes=result.notes,
            corpus_root=result.corpus_root,
            fixture_paths=tuple(fixture_paths),
        )
        audit_dir = root / "data" / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        stamp = captured_at.replace(":", "").replace("-", "")
        summary_path = audit_dir / f"live_audit_{stamp}.json"
        summary_path.write_text(
            json.dumps(
                {
                    "contest_entry": False,
                    "captured_at": result.captured_at,
                    "contract": result.contract,
                    "open_questions": list(result.open_questions),
                    "coverage": asdict(result.coverage),
                    "gates_ok": result.gates_ok,
                    "gate_blocked": list(result.gate_blocked),
                    "notes": list(result.notes),
                    "corpus_root": result.corpus_root,
                    "fixture_paths": list(result.fixture_paths),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only NHL Real Sports contract audit")
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=None,
        help="Corpus root (default: nhl-oracle/)",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Fetch and infer only; do not write corpus fixtures",
    )
    args = parser.parse_args(argv)
    result = asyncio.run(
        run_live_audit(
            corpus_root=args.corpus_root,
            persist_fixtures=not args.no_persist,
        )
    )
    print(
        json.dumps(
            {
                "contest_entry": result.contest_entry,
                "captured_at": result.captured_at,
                "contract": result.contract,
                "open_questions": list(result.open_questions),
                "coverage": asdict(result.coverage),
                "gates_ok": result.gates_ok,
                "gate_blocked": list(result.gate_blocked),
                "notes": list(result.notes),
                "corpus_root": result.corpus_root,
                "fixture_count": len(result.fixture_paths),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

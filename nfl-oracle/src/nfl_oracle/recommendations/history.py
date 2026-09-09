"""Resumable, bounded historical collection and audited model input loading."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from oracle_core.artifacts import atomic_write_json, sha256_file

from nfl_oracle.ingest.clocks import clocks_for_game
from nfl_oracle.ingest.corpus_g import CorpusGStore, EndpointName
from nfl_oracle.ingest.realsports import BASE, headers_or_capture
from nfl_oracle.recommendations.model import HistoricalPerformance
from nfl_oracle.recommendations.provider import NFLReader, ObservationStore, ProviderError


def load_history_metadata(
    root: Path, rows: list[HistoricalPerformance]
) -> dict[tuple[int, int], dict[str, Any]]:
    """Read immutable player names and effective teams for audited history rows."""
    wanted = {(row.player_id, row.game_id) for row in rows}
    game_ids = {row.game_id for row in rows}
    result: dict[tuple[int, int], dict[str, Any]] = {}
    for stats_path in sorted(root.glob("*/*/stats.json")):
        directory = stats_path.parent
        if not directory.name.isdigit() or int(directory.name) not in game_ids:
            continue
        for name in ("feed", "stats"):
            path = directory / f"{name}.json"
            provenance = json.loads(path.with_suffix(".json.provenance.json").read_text())
            if sha256_file(path) != provenance["content_sha256"]:
                raise ValueError("historical_metadata_integrity")
        game = json.loads((directory / "feed.json").read_text())["game"]
        if game.get("sport") != "nfl" or game.get("isPostProcessed") is not True:
            raise ValueError("historical_metadata_game_invalid")
        for box in json.loads(stats_path.read_text())["playerBoxScores"]:
            key = (box["playerId"], game["id"])
            if key not in wanted:
                continue
            player = box.get("player") or {}
            if player.get("id") != key[0]:
                raise ValueError("historical_metadata_player_mismatch")
            home = box["teamId"] == game["homeTeamId"]
            result[key] = {
                "name": f"{player['firstName']} {player['lastName']}",
                "team": game["homeTeamKey"] if home else game["awayTeamKey"],
                "opponent": game["awayTeamKey"] if home else game["homeTeamKey"],
                "position": box.get("position") or "UNK",
                "season": game["season"],
                "week": game["week"],
                "season_type": game["seasonType"],
                "kickoff_at": game["dateTime"],
            }
    if set(result) != wanted:
        raise ValueError("historical_metadata_incomplete")
    return result


def load_history(root: Path) -> tuple[list[HistoricalPerformance], dict[str, int]]:
    rows: list[HistoricalPerformance] = []
    excluded: dict[str, int] = {}
    for stats_path in sorted(root.glob("*/*/stats.json")):
        directory = stats_path.parent
        try:
            stats_provenance = json.loads((directory / "stats.json.provenance.json").read_text())
            feed_provenance = json.loads((directory / "feed.json.provenance.json").read_text())
            if sha256_file(stats_path) != stats_provenance["content_sha256"]:
                raise ValueError("stats_integrity")
            if sha256_file(directory / "feed.json") != feed_provenance["content_sha256"]:
                raise ValueError("feed_integrity")
            game = json.loads((directory / "feed.json").read_text())["game"]
            if game.get("sport") != "nfl" or game.get("isPostProcessed") is not True:
                raise ValueError("not_finalized_nfl")
            if game.get("seasonType") == "preseason":
                excluded["preseason_game"] = excluded.get("preseason_game", 0) + 1
                continue
            if game.get("seasonType") not in {"regularseason", "postseason"}:
                raise ValueError("unknown_season_type")
            clocks = clocks_for_game(game, captured_at=stats_provenance["captured_at"])
            if not all(clocks[key] for key in ("source_available_at", "event_time", "captured_at")):
                raise ValueError("unknown_finalization_clock")
            stats = json.loads(stats_path.read_text())
            game_rows: list[HistoricalPerformance] = []
            for box in stats["playerBoxScores"]:
                if box.get("value") is None:
                    excluded["missing_value"] = excluded.get("missing_value", 0) + 1
                    continue
                value = float(box["value"])
                if not math.isfinite(value):
                    raise ValueError("nonfinite_value")
                team_id = box.get("teamId")
                if team_id not in (game["homeTeamId"], game["awayTeamId"]):
                    raise ValueError("historical_team_mismatch")
                # Real exposes offensive/defensive snaps separately. Preserve
                # opportunity as a measured count, never infer NFL minutes.
                advanced = {s["label"]: s.get("value") for s in box.get("advancedStatValues") or []}
                opportunity_raw = advanced.get("osnp")
                if opportunity_raw is None:
                    opportunity_raw = advanced.get("dsnp")
                opportunity = float(opportunity_raw) if opportunity_raw is not None else None
                game_rows.append(
                    HistoricalPerformance(
                        player_id=box["playerId"],
                        game_id=game["id"],
                        position=box.get("position") or "UNK",
                        kickoff_at=datetime.fromisoformat(str(clocks["event_time"])),
                        available_at=datetime.fromisoformat(str(clocks["source_available_at"])),
                        captured_at=datetime.fromisoformat(str(clocks["captured_at"])),
                        value=value,
                        opportunity=opportunity,
                        team_id=team_id,
                        opponent_team_id=game["awayTeamId"]
                        if team_id == game["homeTeamId"]
                        else game["homeTeamId"],
                        did_not_play=box.get("didNotPlay") is True,
                    )
                )
            if len({row.player_id for row in game_rows}) != len(game_rows):
                raise ValueError("duplicate_player_game")
            rows.extend(game_rows)
        except (OSError, ValueError, KeyError, TypeError) as error:
            # This is an evidence audit, not a permissive production fallback.
            # Any damaged game is reported and excluded; no exception text leaks.
            key = type(error).__name__
            excluded[key] = excluded.get(key, 0) + 1
    return rows, excluded


async def collect_history(
    project: Path,
    game_ids: list[int],
    *,
    seasons: set[int],
    refresh: bool = False,
) -> dict[str, Any]:
    store = CorpusGStore(project)
    headers = await headers_or_capture()
    audit_path = project / "data" / "artifacts" / "history_collection.json"
    audit: dict[str, Any] = {"completed": [], "skipped": [], "failed": [], "contest_entry": False}
    async with httpx.AsyncClient(timeout=25) as client:
        reader = NFLReader(
            client,
            headers,
            ObservationStore(project / "data/raw/observations"),
            max_requests=max(10, 2 * len(game_ids) + 5),
        )
        for game_id in game_ids:
            existing = [
                store.raw_root / str(season) / str(game_id) / "stats.json" for season in seasons
            ]
            if not refresh and any(path.exists() for path in existing):
                audit["skipped"].append(game_id)
                continue
            try:
                feed = await reader.get(
                    f"/games/{game_id}/sport/nfl/feed", version=2, view="all", viewFrame="default"
                )
                game = feed.get("game") or {}
                if (
                    game.get("id") != game_id
                    or game.get("sport") != "nfl"
                    or game.get("season") not in seasons
                    or game.get("isPostProcessed") is not True
                ):
                    audit["skipped"].append(game_id)
                    continue
                stats = await reader.get(f"/games/{game_id}/sport/nfl/stats")
                now = reader.clock()
                clocks = clocks_for_game(game, captured_at=now.isoformat())
                payloads: tuple[tuple[EndpointName, dict[str, Any]], ...] = (
                    ("feed", feed),
                    ("stats", stats),
                )
                for endpoint, payload in payloads:
                    store.persist_endpoint(
                        game_id=game_id,
                        season=game["season"],
                        endpoint=endpoint,
                        payload=payload,
                        source_url=f"{BASE}/games/{game_id}/sport/nfl/{endpoint}",
                        captured_at=now,
                        event_time=clocks["event_time"],
                        source_available_at=clocks["source_available_at"],
                    )
                atomic_write_json(
                    store.game_dir(game["season"], game_id) / "manifest.json",
                    {
                        "game_id": game_id,
                        "season": game["season"],
                        "clocks": clocks,
                        "source_hashes": reader.hashes[-2:],
                        "collector": "recommendation_history_v1",
                    },
                )
                audit["completed"].append(game_id)
            except ProviderError:
                audit["failed"].append(game_id)
                atomic_write_json(audit_path, audit)
                raise
            finally:
                audit["updated_at"] = datetime.now(UTC).isoformat()
                atomic_write_json(audit_path, audit)
            if len(audit["completed"]) % 25 == 0:
                print(
                    json.dumps({"completed": len(audit["completed"]), "last_game": game_id}),
                    flush=True,
                )
            await asyncio.sleep(0.2)
    return audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, default=Path("nfl-oracle"))
    parser.add_argument("--first-game", type=int, required=True)
    parser.add_argument("--last-game", type=int, required=True)
    parser.add_argument("--season", type=int, action="append", required=True)
    args = parser.parse_args()
    if not 0 <= args.last_game - args.first_game <= 1000:
        parser.error("one run must contain between 1 and 1001 game IDs")
    try:
        audit = asyncio.run(
            collect_history(
                args.project,
                list(range(args.first_game, args.last_game + 1)),
                seasons=set(args.season),
            )
        )
    except Exception as error:
        print(json.dumps({"status": "failed", "error_type": type(error).__name__}), flush=True)
        return 1
    print(json.dumps({"status": "complete", "games": len(audit["completed"])}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

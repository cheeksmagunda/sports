#!/usr/bin/env python3
"""Offline: build an IdentityMap summary from Corpus G / value_labels fixtures.

No network. No contest entry. Writes JSON under data/artifacts/ (gitignored).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from nfl_oracle.identity import (
    IdentityMap,
    summarize_identity_density,
    upsert_from_players_payload,
)

ROOT = Path(__file__).resolve().parents[1]
CT = ZoneInfo("America/Chicago")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ident = IdentityMap()
    sources: list[str] = []

    for players_fixture in (
        ROOT / "tests" / "fixtures" / "identity" / "dense_players.json",
        ROOT / "tests" / "fixtures" / "offline_research" / "data" / "identity" / "players.json",
        ROOT / "tests" / "fixtures" / "corpus_g" / "players.json",
        ROOT / "tests" / "fixtures" / "players_126323.json",
    ):
        if players_fixture.is_file():
            n = upsert_from_players_payload(ident, _load_json(players_fixture))
            sources.append(f"{players_fixture.relative_to(ROOT)}:{n}")

    # value_labels fixtures are stats-shaped; synthesize player rows from boxes
    for stats_path in sorted((ROOT / "tests" / "fixtures" / "value_labels").rglob("stats.json")):
        payload = _load_json(stats_path)
        boxes = payload.get("playerBoxScores") or []
        synthetic = {
            "players": [
                {
                    "playerId": row.get("playerId"),
                    "position": row.get("position"),
                    "teamId": row.get("teamId"),
                }
                for row in boxes
                if isinstance(row, dict)
            ]
        }
        n = upsert_from_players_payload(ident, synthetic)
        sources.append(f"{stats_path.relative_to(ROOT)}:{n}")

    density = summarize_identity_density(ident)
    out_dir = ROOT / "data" / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(CT).strftime("%Y%m%dT%H%M%S%z")
    payload = {
        "role": "identity_hydrate_fixtures",
        "contest_entry": False,
        "built_at_ct": datetime.now(CT).isoformat(),
        "n_identities": len(ident),
        "sources": sources,
        "player_ids": ident.player_ids(),
        "density": density.to_dict(),
    }
    path = out_dir / f"identity_fixtures_{stamp}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest = out_dir / "identity_fixtures_latest.json"
    latest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    print(
        "hydrate_identity_fixtures: "
        f"n={len(ident)} complete={density.n_complete} "
        f"ratio={density.complete_ratio:.3f} wrote {path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

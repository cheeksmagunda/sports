"""Identity hydration from Corpus G players fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from nfl_oracle.identity import IdentityMap, upsert_from_players_payload


def test_upsert_from_players_fixture() -> None:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "corpus_g" / "players.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    ident = IdentityMap()
    n = upsert_from_players_payload(ident, payload)
    assert n >= 1
    assert len(ident) == n

"""Identity alias/dedup reconciliation beyond first+last (offline)."""

from __future__ import annotations

from pathlib import Path

from nfl_oracle.identity.aliases import (
    name_match_keys,
    normalize_display_name,
    reconcile_alias_collisions,
    suggest_dedup_candidates,
    upsert_with_aliases,
)
from nfl_oracle.identity.load import load_identity_map_from_players_file, research_identity_summary
from nfl_oracle.identity.map import IdentityMap, IdentityRecord

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_normalize_display_name_strips_suffixes() -> None:
    assert normalize_display_name("Michael Johnson Jr.") == "michael johnson"
    assert normalize_display_name("James Brown III") == "james brown"
    assert normalize_display_name("  A.  Winfield  ") == "a winfield"
    assert normalize_display_name(None) is None


def test_name_match_keys_nickname_bridge() -> None:
    bob = name_match_keys("Bob Williams")
    rob = name_match_keys("Robert Williams")
    assert any(k.startswith("last_nick:") for k in bob)
    assert set(bob) & set(rob)
    assert "last_nick:williams|bob" in bob or "last_nick:williams|robert" in bob
    # Canonical nickname group collapses to sorted[0] == "bob"
    assert "last_nick:williams|bob" in bob
    assert "last_nick:williams|bob" in rob


def test_fixture_collisions_external_and_normalized() -> None:
    path = FIXTURES / "identity" / "dense_players.json"
    ident = load_identity_map_from_players_file(path)
    assert len(ident) >= 100
    report = reconcile_alias_collisions(ident)
    assert report["contest_entry"] is False
    assert report["alias_collision_count"] >= 1
    assert report["display_name_collision_count"] >= 1
    assert report["normalized_name_collision_count"] >= 1
    assert report["soft_name_collision_count"] >= 1
    # Shared gsis fixture
    assert any("00-collide-gsis" in k for k in report["alias_collisions"])
    # Jr vs non-Jr normalize to same key
    assert "michael johnson" in report["normalized_name_collisions"]
    candidates = suggest_dedup_candidates(ident)
    assert candidates
    assert all(c["auto_merge"] is False for c in candidates)
    summary = research_identity_summary(players_path=path)
    assert summary["aliases"]["alias_collision_count"] >= 1
    assert summary["aliases"]["normalized_name_collision_count"] >= 1


def test_suggest_dedup_does_not_auto_merge() -> None:
    blank = IdentityMap()
    upsert_with_aliases(
        blank,
        IdentityRecord(
            real_player_id=1,
            display_name="Alex Collision",
            external_ids={"gsis": "same"},
        ),
    )
    upsert_with_aliases(
        blank,
        IdentityRecord(
            real_player_id=2,
            display_name="Alex Collision",
            external_ids={"gsis": "same"},
        ),
    )
    assert len(blank) == 2
    cands = suggest_dedup_candidates(blank)
    assert any(c["kind"] == "external_alias" for c in cands)
    assert blank.get(1) is not None and blank.get(2) is not None

from __future__ import annotations

from nhl_oracle.identity.map import NhlIdentityMap, NhlIdentityRecord
from nhl_oracle.identity.reconcile import (
    drop_ambiguous_identity_rows,
    reconcile_identity_collisions,
)


def _identity_with_collision() -> NhlIdentityMap:
    identity = NhlIdentityMap()
    identity.upsert(
        NhlIdentityRecord(real_player_id=1, display_name="Sebastian Aho", position="C", team_id=10)
    )
    identity.upsert(
        NhlIdentityRecord(real_player_id=2, display_name="Sebastian Aho", position="D", team_id=20)
    )
    identity.upsert(
        NhlIdentityRecord(real_player_id=3, display_name="Connor McDavid", position="C", team_id=30)
    )
    return identity


def test_same_name_collision_is_reported_not_merged() -> None:
    report = reconcile_identity_collisions(_identity_with_collision())
    assert report["contest_entry"] is False
    assert report["observation_only"] is True
    assert report["n_identities"] == 3
    assert report["collision_count"] == 1
    assert report["collisions"]["sebastian aho"] == [1, 2]


def test_no_collision_when_names_are_distinct() -> None:
    identity = NhlIdentityMap()
    identity.upsert(NhlIdentityRecord(real_player_id=1, display_name="Connor McDavid"))
    identity.upsert(NhlIdentityRecord(real_player_id=2, display_name="Auston Matthews"))
    report = reconcile_identity_collisions(identity)
    assert report["collision_count"] == 0
    assert report["collisions"] == {}


def test_drop_ambiguous_identity_rows_drops_and_audits_collisions() -> None:
    identity = _identity_with_collision()
    rows = [
        {"real_player_id": 1, "score": 1.0},
        {"real_player_id": 2, "score": 2.0},
        {"real_player_id": 3, "score": 3.0},
    ]
    kept, dropped = drop_ambiguous_identity_rows(rows, identity=identity)

    assert [row["real_player_id"] for row in kept] == [3]
    assert {row["real_player_id"] for row in dropped} == {1, 2}
    assert all(row["drop_reason"] == "ambiguous_identity_same_name_collision" for row in dropped)


def test_drop_ambiguous_identity_rows_keeps_all_when_no_collision() -> None:
    identity = NhlIdentityMap()
    identity.upsert(NhlIdentityRecord(real_player_id=1, display_name="Connor McDavid"))
    rows = [{"real_player_id": 1, "score": 1.0}]
    kept, dropped = drop_ambiguous_identity_rows(rows, identity=identity)
    assert kept == rows
    assert dropped == []

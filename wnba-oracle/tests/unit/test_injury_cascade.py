"""Injury-cascade minutes redistribution."""

from __future__ import annotations

from wnba_oracle.features.injury_cascade import (
    CascadeConfig,
    CascadeInput,
    redistribute_minutes,
)


def test_no_out_players_means_no_redistribution() -> None:
    rows = [
        CascadeInput(1, "LVA", "G", 32.0, False),
        CascadeInput(2, "LVA", "F", 28.0, False),
    ]
    assert redistribute_minutes(rows) == {}


def test_out_starter_redistributes_to_same_position_bench() -> None:
    rows = [
        CascadeInput(1, "LVA", "G", 34.0, True),  # OUT starting G
        CascadeInput(2, "LVA", "G", 18.0, False),
        CascadeInput(3, "LVA", "G", 10.0, False),
        CascadeInput(4, "LVA", "F", 30.0, False),  # different cohort, no share
    ]
    # Raise per-player cap so the bench-bias differential shows through
    # (default 8.0 saturates both Gs in this small synthetic team).
    bonuses = redistribute_minutes(rows, cfg=CascadeConfig(per_player_cap_minutes=20.0))
    # Both Gs receive some; the bench G (10 min) more than the rotation G (18)
    assert bonuses[3] > bonuses[2]
    # Forward gets nothing from the G cascade
    assert 4 not in bonuses


def test_per_player_cap_holds() -> None:
    rows = [
        CascadeInput(1, "LVA", "G", 34.0, True),
        CascadeInput(2, "LVA", "G", 1.0, False),  # tiny minutes, huge inverse weight
    ]
    bonuses = redistribute_minutes(rows, cfg=CascadeConfig(per_player_cap_minutes=6.0))
    assert bonuses[2] <= 6.0


def test_center_out_shares_with_forwards() -> None:
    rows = [
        CascadeInput(1, "LVA", "C", 30.0, True),
        CascadeInput(2, "LVA", "C", 10.0, False),
        CascadeInput(3, "LVA", "F", 20.0, False),
    ]
    bonuses = redistribute_minutes(
        rows, cfg=CascadeConfig(center_forward_share=0.30, per_player_cap_minutes=20.0)
    )
    # Both backup C and the F should get bonuses (cross-cohort share)
    assert 2 in bonuses
    assert 3 in bonuses


def test_two_teams_independent() -> None:
    rows = [
        CascadeInput(1, "LVA", "G", 30.0, True),
        CascadeInput(2, "LVA", "G", 12.0, False),
        CascadeInput(3, "NYL", "G", 20.0, False),  # different team; no cascade
    ]
    bonuses = redistribute_minutes(rows)
    assert 2 in bonuses
    assert 3 not in bonuses

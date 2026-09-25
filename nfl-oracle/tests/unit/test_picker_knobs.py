"""Unit tests for boost-aware / position-calibration picker knobs (#280)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nfl_oracle.recommendations.model import Projection
from nfl_oracle.recommendations.picker_knobs import (
    PickerKnobs,
    apply_picker_knobs,
    picker_knobs_from_env,
    position_residual_bias,
)
from nfl_oracle.recommendations.schema import (
    Candidate,
    Contest,
    EvidenceClock,
    Game,
    Slate,
)

NOW = datetime(2026, 9, 25, 16, 0, tzinfo=UTC)


def _make_slate(boosts: dict[int, float], positions: dict[int, str] | None = None) -> Slate:
    positions = positions or {pid: "WR" for pid in boosts}
    kickoff = NOW + timedelta(hours=2)
    clock = EvidenceClock(source_available_at=NOW, captured_at=NOW)
    games = (
        Game(
            game_id=1,
            season=2026,
            kickoff_at=kickoff,
            home_team_id=1,
            away_team_id=2,
            home_team="HOM",
            away_team="AWY",
            status="scheduled",
        ),
    )
    candidates = tuple(
        Candidate(
            player_id=pid,
            game_id=1,
            team_id=1 if pid % 2 else 2,
            name=f"P{pid}",
            position=positions[pid],
            team="HOM" if pid % 2 else "AWY",
            opponent="AWY" if pid % 2 else "HOM",
            injury_status="Active",
            card_boost=boost,
            clock=clock,
        )
        for pid, boost in sorted(boosts.items())
    )
    return Slate(
        contest=Contest(
            contest_id=1,
            day=kickoff.date(),
            end_day=kickoff.date(),
            slot_multipliers=(2.0, 1.8, 1.6, 1.4, 1.2),
            is_locked=False,
            is_finalized=False,
            clock=clock,
            evidence_sha256="a" * 64,
        ),
        games=games,
        candidates=candidates,
        captured_at=NOW,
        source_hashes=("b" * 64,),
        pool_roster_count=len(candidates),
        pool_search_matched_count=len(candidates),
    )


def _proj(player_id: int, mean: float) -> Projection:
    return Projection(
        player_id=player_id,
        mean=mean,
        conditional_mean=mean,
        availability_probability=1.0,
        stddev=0.5,
        prior_games=5,
        samples=(mean, mean + 0.1, mean - 0.1),
        provenance=("test",),
    )


def test_identity_knobs_leave_projections_unchanged() -> None:
    slate = _make_slate({1: 0.0, 2: 1.5, 3: 3.0, 4: 0.5, 5: 2.0})
    projections = tuple(_proj(pid, float(pid)) for pid in range(1, 6))
    out = apply_picker_knobs(projections, slate, knobs=PickerKnobs())
    assert [p.conditional_mean for p in out] == [p.conditional_mean for p in projections]


def test_full_boost_rank_blend_reassigns_means_by_boost_order() -> None:
    slate = _make_slate({1: 0.0, 2: 1.0, 3: 3.0, 4: 0.5, 5: 2.0})
    projections = (
        _proj(1, 9.0),
        _proj(2, 5.0),
        _proj(3, 1.0),
        _proj(4, 3.0),
        _proj(5, 7.0),
    )
    out = apply_picker_knobs(
        projections,
        slate,
        knobs=PickerKnobs(boost_rank_blend=1.0, profile="full_boost"),
    )
    by_id = {p.player_id: p.conditional_mean for p in out}
    assert by_id[3] == max(by_id.values())
    assert by_id[1] == min(by_id.values())
    assert sorted(by_id.values()) == sorted(p.conditional_mean for p in projections)


def test_position_calibration_adds_weighted_bias() -> None:
    slate = _make_slate(
        {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0},
        positions={1: "QB", 2: "RB", 3: "WR", 4: "WR", 5: "TE"},
    )
    projections = tuple(_proj(pid, 4.0) for pid in range(1, 6))
    out = apply_picker_knobs(
        projections,
        slate,
        knobs=PickerKnobs(position_calibration=0.5, profile="pos"),
        position_bias={"QB": 2.0, "WR": -1.0},
    )
    by_id = {p.player_id: p.conditional_mean for p in out}
    assert by_id[1] == pytest.approx(5.0)
    assert by_id[3] == pytest.approx(3.5)
    assert by_id[2] == pytest.approx(4.0)


def test_picker_knobs_from_env_reads_unit_weights() -> None:
    knobs = picker_knobs_from_env(
        {
            "NFL_PICKER_BOOST_RANK_BLEND": "0.35",
            "NFL_PICKER_POSITION_CALIBRATION": "0.5",
            "NFL_PICKER_PROFILE": "weekend",
        }
    )
    assert knobs.boost_rank_blend == pytest.approx(0.35)
    assert knobs.position_calibration == pytest.approx(0.5)
    assert knobs.profile == "weekend"


def test_picker_knobs_from_env_rejects_out_of_range() -> None:
    with pytest.raises(ValueError, match="NFL_PICKER_BOOST_RANK_BLEND_out_of_range"):
        picker_knobs_from_env({"NFL_PICKER_BOOST_RANK_BLEND": "1.5"})


def test_position_residual_bias_means() -> None:
    assert position_residual_bias({"QB": [1.0, 3.0], "WR": []}) == {"QB": 2.0}


def test_partial_boost_blend_interpolates_toward_aligned_mean() -> None:
    slate = _make_slate({1: 0.0, 2: 3.0})
    projections = (_proj(1, 10.0), _proj(2, 2.0))
    out = apply_picker_knobs(
        projections,
        slate,
        knobs=PickerKnobs(boost_rank_blend=0.5, profile="half"),
    )
    by_id = {p.player_id: p.conditional_mean for p in out}
    # Full blend would swap 10<->2; half blend: player2 -> 2 + 0.5*(10-2)=6
    assert by_id[2] == pytest.approx(6.0)
    assert by_id[1] == pytest.approx(6.0)

"""Ollama tick tilt contract for NFL picker (#574)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from nfl_oracle.recommendations.model import Projection
from nfl_oracle.recommendations.ollama_tick_tilt import (
    apply_ollama_tick_tilt,
    load_slot_multipliers,
    ollama_tilt_from_env,
    slot_multipliers_from_tick,
)
from nfl_oracle.recommendations.picker_knobs import PickerKnobs, apply_picker_knobs
from nfl_oracle.recommendations.schema import (
    Candidate,
    Contest,
    EvidenceClock,
    Game,
    Slate,
)

NOW = datetime(2026, 9, 25, 16, 0, tzinfo=UTC)


def _make_slate(boosts: dict[int, float]) -> Slate:
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
            position="WR",
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


def _tick_payload() -> dict:
    return {
        "five_player_lineup": [
            {"slot": 1, "player_id": 3, "name": "A"},
            {"slot": 2, "player_id": 1, "name": "B"},
            {"slot": 3, "player_id": 5, "name": "C"},
            {"slot": 4, "player_id": 2, "name": "D"},
            {"slot": 5, "player_id": 4, "name": "E"},
        ]
    }


def test_weight_zero_never_requires_path() -> None:
    weight, path = ollama_tilt_from_env({})
    assert weight == 0.0
    assert path is None


def test_positive_weight_requires_path() -> None:
    with pytest.raises(ValueError, match="PATH_required"):
        ollama_tilt_from_env({"NFL_OLLAMA_TICK_TILT_WEIGHT": "0.2"})


def test_slot_multipliers_rank_slot_one_highest() -> None:
    mult = slot_multipliers_from_tick(_tick_payload(), weight=0.5)
    assert mult[3] == pytest.approx(1.5)  # slot 1
    assert mult[4] == pytest.approx(1.1)  # slot 5
    assert mult[3] > mult[1] > mult[4]


def test_apply_tilt_scales_only_listed_players() -> None:
    projections = tuple(_proj(pid, 10.0) for pid in range(1, 6))
    mult = {3: 1.5, 1: 1.25}
    out = apply_ollama_tick_tilt(projections, multipliers=mult)
    by_id = {p.player_id: p for p in out}
    assert by_id[3].conditional_mean == pytest.approx(15.0)
    assert by_id[1].conditional_mean == pytest.approx(12.5)
    assert by_id[2].conditional_mean == pytest.approx(10.0)
    assert any("ollama_tick_tilt=" in p for p in by_id[3].provenance)


def test_apply_picker_knobs_reads_latest_tick(tmp_path: Path) -> None:
    slate_dir = tmp_path / "nfl" / "2026-09-27"
    slate_dir.mkdir(parents=True)
    (slate_dir / "latest_tick.json").write_text(
        json.dumps(_tick_payload()) + "\n", encoding="utf-8"
    )
    slate = _make_slate({1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0})
    projections = tuple(_proj(pid, 10.0) for pid in range(1, 6))
    out = apply_picker_knobs(
        projections,
        slate,
        knobs=PickerKnobs(
            ollama_tick_tilt_weight=0.5,
            ollama_tick_tilt_path=str(slate_dir),
            profile="ollama_tilt",
        ),
    )
    by_id = {p.player_id: p.conditional_mean for p in out}
    assert by_id[3] == pytest.approx(15.0)
    assert by_id[4] == pytest.approx(11.0)


def test_load_slot_multipliers_missing_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="ollama_tick"):
        load_slot_multipliers(tmp_path / "missing.json", weight=0.1)


def test_identity_when_weight_zero_even_if_path_set(tmp_path: Path) -> None:
    tick = tmp_path / "tick.json"
    tick.write_text(json.dumps(_tick_payload()) + "\n", encoding="utf-8")
    slate = _make_slate({1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0})
    projections = tuple(_proj(pid, float(pid)) for pid in range(1, 6))
    out = apply_picker_knobs(
        projections,
        slate,
        knobs=PickerKnobs(
            ollama_tick_tilt_weight=0.0,
            ollama_tick_tilt_path=str(tick),
        ),
    )
    assert [p.conditional_mean for p in out] == [p.conditional_mean for p in projections]

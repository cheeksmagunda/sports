"""Tests for optional NFL Ollama influence (#574)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from nfl_oracle.recommendations.model import Projection
from nfl_oracle.recommendations.ollama_influence import (
    apply_ollama_influence,
    influence_enabled,
    load_tilt_map,
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


def test_influence_default_off() -> None:
    assert influence_enabled({}) is False
    assert load_tilt_map(slate_id="2026-09-27", environ={}) == {}


def test_apply_mult_and_identity(tmp_path: Path) -> None:
    projections = (_proj(1, 10.0), _proj(2, 20.0))
    out = apply_ollama_influence(projections, tilts={1: 1.1})
    assert abs(out[0].conditional_mean - 11.0) < 1e-9
    assert abs(out[1].conditional_mean - 20.0) < 1e-9
    assert "ollama_influence" in out[0].provenance[-1]


def test_load_fresh_advice_file(tmp_path: Path) -> None:
    path = tmp_path / "advice.json"
    now = datetime(2026, 9, 27, 14, 0, tzinfo=UTC)
    path.write_text(
        json.dumps(
            {
                "sport": "nfl",
                "slate_id": "2026-09-27",
                "written_at": (now - timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
                "max_age_seconds": 10800,
                "tilts": [{"player_id": 42, "mult": 1.08}],
            }
        ),
        encoding="utf-8",
    )
    tilts = load_tilt_map(
        slate_id="2026-09-27",
        environ={"NFL_OLLAMA_INFLUENCE": "1", "NFL_OLLAMA_ADVICE_PATH": str(path)},
        now=now,
    )
    assert tilts == {42: 1.08}


def test_stale_advice_ignored(tmp_path: Path) -> None:
    path = tmp_path / "advice.json"
    now = datetime(2026, 9, 27, 14, 0, tzinfo=UTC)
    path.write_text(
        json.dumps(
            {
                "sport": "nfl",
                "slate_id": "2026-09-27",
                "written_at": (now - timedelta(hours=5)).isoformat().replace("+00:00", "Z"),
                "max_age_seconds": 3600,
                "tilts": [{"player_id": 42, "mult": 1.08}],
            }
        ),
        encoding="utf-8",
    )
    tilts = load_tilt_map(
        slate_id="2026-09-27",
        environ={"NFL_OLLAMA_INFLUENCE": "1", "NFL_OLLAMA_ADVICE_PATH": str(path)},
        now=now,
    )
    assert tilts == {}

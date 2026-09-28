"""Default-off NFL advice influence (#574). Does not touch picker blend."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from nfl_oracle.recommendations.model import Projection
from nfl_oracle.recommendations.ollama_influence import (
    apply_ollama_influence,
    influence_enabled,
    load_tilt_map,
)
from nfl_oracle.recommendations.picker_knobs import picker_knobs_from_env


def _proj(player_id: int, mean: float) -> Projection:
    return Projection(
        player_id=player_id,
        mean=mean,
        conditional_mean=mean,
        availability_probability=1.0,
        stddev=0.5,
        prior_games=4,
        samples=(mean, mean + 1.0),
        provenance=("ridge",),
    )


def test_influence_default_off_and_blend_stays_zero() -> None:
    assert influence_enabled({}) is False
    assert load_tilt_map(slate_id="2026-09-28", environ={}) == {}
    knobs = picker_knobs_from_env({})
    assert knobs.boost_rank_blend == 0.0
    original = (_proj(1, 10.0),)
    assert apply_ollama_influence(original, tilts={}) == original


def test_fresh_advice_multiplies_and_stale_is_identity(tmp_path) -> None:
    now = datetime(2026, 9, 28, 18, 0, tzinfo=UTC)
    path = tmp_path / "advice.json"
    path.write_text(
        json.dumps(
            {
                "sport": "nfl",
                "slate_id": "2026-09-28",
                "written_at": (now - timedelta(minutes=2)).isoformat().replace("+00:00", "Z"),
                "max_age_seconds": 3600,
                "tilts": [{"player_id": 1, "mult": 1.4}, {"player_id": 2, "mult": 0.5}],
            }
        ),
        encoding="utf-8",
    )
    env = {
        "NFL_OLLAMA_INFLUENCE": "1",
        "NFL_OLLAMA_ADVICE_PATH": str(path),
    }
    tilts = load_tilt_map(slate_id="2026-09-28", environ=env, now=now)
    assert tilts == {1: 1.15, 2: 0.85}
    adjusted = apply_ollama_influence((_proj(1, 10.0), _proj(3, 4.0)), tilts=tilts)
    assert adjusted[0].conditional_mean == 11.5
    assert adjusted[0].samples[0] == 11.5
    assert "ollama_influence:mult=1.1500" in adjusted[0].provenance
    assert adjusted[1].conditional_mean == 4.0

    stale_now = now + timedelta(hours=5)
    assert load_tilt_map(slate_id="2026-09-28", environ=env, now=stale_now) == {}
    assert load_tilt_map(slate_id="2026-09-27", environ=env, now=now) == {}

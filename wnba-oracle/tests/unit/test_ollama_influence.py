"""Tests for optional WNBA Ollama influence (#574)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from wnba_oracle.picker.ollama_influence import (
    apply_ollama_influence,
    influence_enabled,
    load_tilt_map,
)


def test_influence_default_off() -> None:
    assert influence_enabled({}) is False
    assert load_tilt_map(slate_id="2026-09-27", environ={}) == {}


def test_apply_mult() -> None:
    out = apply_ollama_influence({1: 10.0, 2: 20.0}, tilts={1: 1.1})
    assert abs(out[1] - 11.0) < 1e-9
    assert abs(out[2] - 20.0) < 1e-9


def test_load_fresh_advice_file(tmp_path: Path) -> None:
    path = tmp_path / "advice.json"
    now = datetime(2026, 9, 27, 15, 0, tzinfo=UTC)
    path.write_text(
        json.dumps(
            {
                "sport": "wnba",
                "slate_id": "2026-09-27",
                "written_at": (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
                "max_age_seconds": 10800,
                "tilts": [{"player_id": 7, "mult": 0.92}],
            }
        ),
        encoding="utf-8",
    )
    tilts = load_tilt_map(
        slate_id="2026-09-27",
        environ={"WNBA_OLLAMA_INFLUENCE": "1", "WNBA_OLLAMA_ADVICE_PATH": str(path)},
        now=now,
    )
    assert tilts == {7: 0.92}

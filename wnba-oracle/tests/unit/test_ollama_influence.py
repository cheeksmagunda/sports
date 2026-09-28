"""Default-off WNBA advice influence (#574). Scheduler module, no network."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from wnba_oracle.scheduler.ollama_influence import (
    apply_ollama_influence,
    influence_enabled,
    load_tilt_map,
)


def test_influence_default_off_is_identity() -> None:
    assert influence_enabled({}) is False
    scores = {1: 20.0, 2: 10.0}
    assert apply_ollama_influence(scores, tilts={}) == scores
    assert load_tilt_map(slate_id="2026-09-28", environ={}) == {}


def test_fresh_file_scales_scores_and_stale_does_not(tmp_path) -> None:
    now = datetime(2026, 9, 28, 17, 0, tzinfo=UTC)
    path = tmp_path / "advice.json"
    path.write_text(
        json.dumps(
            {
                "sport": "wnba",
                "slate_id": "2026-09-28",
                "written_at": now.isoformat().replace("+00:00", "Z"),
                "max_age_seconds": 600,
                "tilts": [{"player_id": 7, "mult": 1.1}],
            }
        ),
        encoding="utf-8",
    )
    env = {
        "WNBA_OLLAMA_INFLUENCE": "on",
        "WNBA_OLLAMA_ADVICE_PATH": str(path),
    }
    tilts = load_tilt_map(slate_id="2026-09-28", environ=env, now=now + timedelta(seconds=30))
    assert tilts == {7: 1.1}
    assert apply_ollama_influence({7: 10.0, 8: 5.0}, tilts=tilts) == {7: 11.0, 8: 5.0}
    assert load_tilt_map(slate_id="2026-09-28", environ=env, now=now + timedelta(hours=2)) == {}

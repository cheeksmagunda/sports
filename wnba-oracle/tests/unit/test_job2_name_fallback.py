"""D50: the frozen lineup must never ship a `Player <id>` placeholder when a
real name exists anywhere in the DB.

The primary name source is `job1_enrichment.name` (Real Sports pool, D49).
When that is empty for a player, `_build_specs` fills the display name from
`slate_labels.display_name` (the independently-populated draft-stats source).
Only when both are empty does the `Player {pid}` placeholder stand.
"""

from __future__ import annotations

import json

from wnba_oracle.picker.popularity import ContrarianConfig
from wnba_oracle.scheduler import job2


def _enrich(pid: int, name: str) -> dict:
    return {
        "real_sports_player_id": str(pid),
        "name": name,
        "team": "POR",
        "opponent": "ATL",
        "position": "F-C",
        "card_boost": 3.0,
        "features_json": json.dumps({}),
    }


def test_build_specs_name_fallback_chain(monkeypatch) -> None:
    # No model artifact, no measured drafts, no player history: isolate the
    # name-resolution chain from the prediction path.
    monkeypatch.setattr(job2, "_load_model_artifact", lambda *_a, **_k: None)
    monkeypatch.setattr(job2, "_load_measured_drafts", lambda *_a, **_k: {})
    # slate_labels carries a name only for the player the pool left blank.
    monkeypatch.setattr(job2, "_load_slate_label_names", lambda *_a, **_k: {617: "Naz Hillmon"})

    enrichment = [
        _enrich(745, "Alyssa Thomas"),  # pool name present -> wins
        _enrich(617, ""),  # pool name empty -> slate_labels fallback
        _enrich(999, ""),  # empty everywhere -> placeholder
    ]

    _samps, _fields, proj = job2._build_specs(
        enrichment,
        slate_date="2026-05-30",
        contrarian_cfg=ContrarianConfig(enabled=False, strength=0.0),
        player_history=None,
    )

    assert proj[745]["display_name"] == "Alyssa Thomas"
    assert proj[617]["display_name"] == "Naz Hillmon"
    assert proj[999]["display_name"] == "Player 999"

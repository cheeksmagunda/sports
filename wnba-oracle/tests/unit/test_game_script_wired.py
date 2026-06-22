"""Game-script (blowout) minutes redistribution wired into job2._build_specs.

The mechanic itself is unit-tested in test_game_script_minutes (redistribution)
and test_picker (copula). These tests pin the INTEGRATION: the kill-switch is
off by default (live unchanged), and when on the blowout context flows into the
sampling specs and shifts predicted real_score (bench up, starters down).
"""

from __future__ import annotations

from types import SimpleNamespace

from wnba_oracle.picker.popularity import ContrarianConfig
from wnba_oracle.scheduler import job2


def _settings(*, gsm: bool) -> SimpleNamespace:
    """Minimal stand-in exposing only the attributes _build_specs reads."""
    return SimpleNamespace(
        model_artifact_sha=None,
        minutes_model_enabled=True,
        starter_signal_enabled=True,
        starter_signal_use_expected=True,
        sampling_score_offset=2.0,
        game_script_minutes_enabled=gsm,
        availability_model_enabled=False,
    )


def _enrichment() -> list[dict]:
    def mk(pid: int, boost: float, recent_min: float, spread: float) -> dict:
        return {
            "real_sports_player_id": pid,
            "team": "LVA",
            "opponent": "NYL",
            "position": "G",
            "card_boost": boost,
            "name": f"P{pid}",
            "features_json": {
                "vegas_total": 165.0,
                "vegas_spread": spread,
                "per_min_rate": 0.10,
                "recent_minutes": recent_min,
                "minutes_vol": 5.0,
                "n_min_games": 10,
                "is_starter": 1 if recent_min >= 24.0 else 0,
                "rotowire_confirmed": 1,
                "is_out": 0,
            },
        }

    # A 20-point blowout: two starters (34, 30 min), two bench (12, 8 min).
    return [
        mk(1, 0.0, 34.0, -20.0),
        mk(2, 0.0, 30.0, -20.0),
        mk(3, 3.0, 12.0, -20.0),
        mk(4, 3.0, 8.0, -20.0),
    ]


def _pred_by_pid(fields: list) -> dict[int, float]:
    return {fp.player_id: fp.pred_real_score for fp in fields}


def test_blowout_wiring_off_by_default_leaves_specs_neutral(monkeypatch) -> None:
    monkeypatch.setattr(job2, "get_settings", lambda: _settings(gsm=False))
    samps, _, _ = job2._build_specs(
        _enrichment(), slate_date="2026-06-02", contrarian_cfg=ContrarianConfig(strength=0.0)
    )
    for s in samps:
        assert s.blowout_prob == 0.0
        assert s.is_starter is False


def test_blowout_wiring_sets_role_and_prob_and_shifts_minutes(monkeypatch) -> None:
    cc = ContrarianConfig(strength=0.0)
    monkeypatch.setattr(job2, "get_settings", lambda: _settings(gsm=True))
    samps_on, fields_on, _ = job2._build_specs(
        _enrichment(), slate_date="2026-06-02", contrarian_cfg=cc
    )
    by_id = {s.player_id: s for s in samps_on}
    # spread 20 >= hard_margin 18 -> blowout_prob saturates at 1.0 for everyone.
    for s in samps_on:
        assert s.blowout_prob == 1.0
    # Role tags: 34/30-min players are starters; 12/8-min are bench.
    assert by_id[1].is_starter is True
    assert by_id[2].is_starter is True
    assert by_id[3].is_starter is False
    assert by_id[4].is_starter is False
    # Anchor flag (D57, Tier 1): the 34/30-min, 10-game players clear the floor;
    # the 12/8-min bench do not (and are not confirmed starters here).
    assert by_id[1].is_anchor is True
    assert by_id[2].is_anchor is True
    assert by_id[3].is_anchor is False
    assert by_id[4].is_anchor is False

    # Baseline with the flag off, same pool.
    monkeypatch.setattr(job2, "get_settings", lambda: _settings(gsm=False))
    _, fields_off, _ = job2._build_specs(_enrichment(), slate_date="2026-06-02", contrarian_cfg=cc)
    on = _pred_by_pid(fields_on)
    off = _pred_by_pid(fields_off)
    # Bench inherits garbage-time minutes -> up; starters trimmed -> down.
    assert on[3] > off[3]
    assert on[4] > off[4]
    assert on[1] < off[1]
    assert on[2] < off[2]
    # Deepest bench (8 min) gains at least as much as the 12-min bench.
    assert (on[4] - off[4]) >= (on[3] - off[3])

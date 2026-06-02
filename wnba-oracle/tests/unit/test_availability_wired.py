"""Availability model (D57, Tier 2) wired into job2._build_specs.

The probability itself is unit-tested in test_availability. This pins the
INTEGRATION: off by default (live unchanged), and when on it multiplies a
cold-start dart's predicted value down toward the floor while leaving an
established rotation player essentially unchanged.
"""

from __future__ import annotations

from types import SimpleNamespace

from wnba_oracle.picker.popularity import ContrarianConfig
from wnba_oracle.scheduler import job2


def _settings(*, avail: bool) -> SimpleNamespace:
    return SimpleNamespace(
        model_artifact_sha=None,
        minutes_model_enabled=True,
        starter_signal_enabled=True,
        sampling_score_offset=2.0,
        game_script_minutes_enabled=False,
        availability_model_enabled=avail,
    )


def _enrichment() -> list[dict]:
    def base(pid: int, boost: float) -> dict:
        return {
            "real_sports_player_id": pid,
            "team": "LVA",
            "opponent": "NYL",
            "position": "G",
            "card_boost": boost,
            "name": f"P{pid}",
        }

    # pid 1: established 30-min, 12-game starter (high availability).
    anchor = base(1, 0.0)
    anchor["features_json"] = {
        "vegas_total": 165.0,
        "vegas_spread": 3.0,
        "per_min_rate": 0.10,
        "recent_minutes": 30.0,
        "minutes_vol": 4.0,
        "n_min_games": 12,
        "is_starter": 1,
        "rotowire_confirmed": 0,
        "is_out": 0,
    }
    # pid 2: cold-start boost-3 dart, no nba_api history, not confirmed (the
    # 2026-06-01 shape). features_json has no minutes keys -> mf is None.
    dart = base(2, 3.0)
    dart["features_json"] = {
        "vegas_total": 165.0,
        "vegas_spread": 3.0,
        "is_starter": 0,
        "rotowire_confirmed": 0,
        "is_out": 0,
    }
    return [anchor, dart]


def _pred_by_pid(fields: list) -> dict[int, float]:
    return {fp.player_id: fp.pred_real_score for fp in fields}


def test_availability_off_by_default(monkeypatch) -> None:
    monkeypatch.setattr(job2, "get_settings", lambda: _settings(avail=False))
    _, fields, _ = job2._build_specs(
        _enrichment(), slate_date="2026-06-02", contrarian_cfg=ContrarianConfig(strength=0.0)
    )
    # Baseline captured for the on/off comparison in the next test.
    assert set(_pred_by_pid(fields)) == {1, 2}


def test_availability_collapses_cold_start_dart(monkeypatch) -> None:
    cc = ContrarianConfig(strength=0.0)
    monkeypatch.setattr(job2, "get_settings", lambda: _settings(avail=False))
    _, off_fields, _ = job2._build_specs(_enrichment(), slate_date="2026-06-02", contrarian_cfg=cc)
    monkeypatch.setattr(job2, "get_settings", lambda: _settings(avail=True))
    _, on_fields, _ = job2._build_specs(_enrichment(), slate_date="2026-06-02", contrarian_cfg=cc)

    off, on = _pred_by_pid(off_fields), _pred_by_pid(on_fields)
    # The cold-start dart is discounted hard by its low P(active)...
    assert on[2] < off[2]
    assert on[2] <= 0.5 * off[2] + 1e-9
    # ...while the established 30-min starter is essentially untouched.
    assert on[1] >= 0.85 * off[1]

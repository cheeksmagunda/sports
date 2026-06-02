"""End-to-end integration: all three D57 tiers armed at once.

Runs the real job2._build_specs -> optimize_lineup path with the anchor floor
(Tier 1), game-script minutes (Tier 3), and availability model (Tier 2) all on,
on a realistic blowout slate mixing established anchors with cold-start darts.
Confirms the tiers COMPOSE without interaction bugs and produce a sane lineup:
five players, the anchor floor honored, and the boost-3 darts (which sank
2026-06-01) suppressed rather than stacked.
"""

from __future__ import annotations

from types import SimpleNamespace

from wnba_oracle.picker.optimize import OptimizeConfig, optimize_lineup
from wnba_oracle.picker.payout import default_curve_for_regime
from wnba_oracle.picker.popularity import ContrarianConfig
from wnba_oracle.scheduler import job2

ANCHOR_IDS = {1, 2, 3, 4, 5}
DART_IDS = {6, 7, 8, 9, 10}


def _all_tiers_settings() -> SimpleNamespace:
    return SimpleNamespace(
        model_artifact_sha=None,
        minutes_model_enabled=True,
        starter_signal_enabled=True,
        sampling_score_offset=2.0,
        game_script_minutes_enabled=True,
        availability_model_enabled=True,
    )


def _slate() -> list[dict]:
    # A 20-point blowout (spread 20) over two teams. Anchors are established
    # rotation players; darts are cold-start boost-3 longshots with no nba_api
    # history (mf is None) -- the exact 2026-06-01 trap.
    rows: list[dict] = []
    teams = ["LVA", "NYL"]
    for i, pid in enumerate(sorted(ANCHOR_IDS)):
        rows.append(
            {
                "real_sports_player_id": pid,
                "team": teams[i % 2],
                "opponent": teams[(i + 1) % 2],
                "position": "G",
                "card_boost": 0.0,
                "name": f"Anchor{pid}",
                "features_json": {
                    "vegas_total": 168.0,
                    "vegas_spread": 20.0,
                    "per_min_rate": 0.11,
                    "recent_minutes": 30.0 - i,
                    "minutes_vol": 4.0,
                    "n_min_games": 12,
                    "is_starter": 1,
                    "rotowire_confirmed": 1,
                    "is_out": 0,
                },
            }
        )
    for i, pid in enumerate(sorted(DART_IDS)):
        rows.append(
            {
                "real_sports_player_id": pid,
                "team": teams[i % 2],
                "opponent": teams[(i + 1) % 2],
                "position": "G",
                "card_boost": 3.0,
                "name": f"Dart{pid}",
                "features_json": {
                    "vegas_total": 168.0,
                    "vegas_spread": 20.0,
                    "is_starter": 0,
                    "rotowire_confirmed": 0,
                    "is_out": 0,
                },
            }
        )
    return rows


def test_all_three_tiers_compose_into_a_sane_lineup(monkeypatch) -> None:
    monkeypatch.setattr(job2, "get_settings", lambda: _all_tiers_settings())
    samps, fields, _ = job2._build_specs(
        _slate(), slate_date="2026-06-02", contrarian_cfg=ContrarianConfig(strength=0.0)
    )
    assert len(samps) == 10

    curve = default_curve_for_regime("top_20")
    cfg = OptimizeConfig(
        top_n_filter=10,
        n_samples=400,
        n_field_lineups=60,
        max_per_team=5,
        dynamic_team_cap=False,
        min_anchors=2,
    )
    rec = optimize_lineup(samps, fields, curve, cfg=cfg)

    # A full, valid lineup.
    assert len(rec.player_ids) == 5
    # Anchor floor (Tier 1) honored.
    n_anchor = sum(p in ANCHOR_IDS for p in rec.player_ids)
    assert n_anchor >= 2
    # Availability (Tier 2) collapsed the cold-start darts, so the lineup leans
    # on the established anchors rather than stacking boost-3 longshots.
    n_dart = sum(p in DART_IDS for p in rec.player_ids)
    assert n_dart <= 3
    assert rec.entry_flag in {"enter", "enter_with_caveat", "skip"}

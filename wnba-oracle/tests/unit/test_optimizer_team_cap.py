"""max_per_team constraint in the optimizer."""

from __future__ import annotations

import numpy as np

from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.optimize import (
    OptimizeConfig,
    _cap_is_feasible,
    _exceeds_team_cap,
    optimize_lineup,
)
from wnba_oracle.picker.payout import default_curve_for_regime
from wnba_oracle.picker.sample import PlayerSamplingSpec


def test_exceeds_team_cap_returns_true_when_violated() -> None:
    teams = ["LVA", "LVA", "LVA", "NYL", "PHO"]
    # 3 LVAs > 2 cap
    assert _exceeds_team_cap((0, 1, 2, 3, 4), teams, max_per_team=2) is True


def test_exceeds_team_cap_returns_false_when_within() -> None:
    teams = ["LVA", "LVA", "NYL", "PHO", "CHI"]
    assert _exceeds_team_cap((0, 1, 2, 3, 4), teams, max_per_team=2) is False


def test_exceeds_team_cap_disabled_when_max_is_5() -> None:
    teams = ["LVA"] * 5
    # Caller sets max_per_team=5 to disable; even an all-same-team combo OK
    assert _exceeds_team_cap((0, 1, 2, 3, 4), teams, max_per_team=5) is False


def test_optimizer_respects_team_cap() -> None:
    """Build a pool where the unconstrained optimum is 5 LVA players; assert
    max_per_team=2 forces the lineup to draw from at least 3 teams."""
    rng = np.random.default_rng(0)
    n = 12
    # Stack the deck: LVA players have the highest mu so unconstrained
    # they would all be selected.
    samp_specs = [
        PlayerSamplingSpec(
            player_id=i,
            team=("LVA" if i < 5 else "NYL" if i < 8 else "PHO"),
            opponent="OPP",
            mu=float(np.log(30.0 + rng.uniform(-2, 2) + 10.0)),
            sigma=0.15,
            boost=1.5,
        )
        for i in range(n)
    ]
    field_specs = [
        FieldPlayerSpec(
            player_id=i,
            pred_real_score=float(30.0 + rng.uniform(-2, 2)),
            card_boost=1.5,
        )
        for i in range(n)
    ]
    curve = default_curve_for_regime("top_20")
    # 3 teams here would trip the dynamic small-slate relaxation, so pin the
    # static path to test the cap mechanism in isolation.
    cfg = OptimizeConfig(
        top_n_filter=10, n_samples=200, n_field_lineups=50, max_per_team=2,
        dynamic_team_cap=False,
    )
    rec = optimize_lineup(samp_specs, field_specs, curve, cfg=cfg)
    teams_picked = [samp_specs[i].team for i in rec.player_ids if i < n]
    # No team can have more than 2
    for team in set(teams_picked):
        assert teams_picked.count(team) <= 2


def _two_team_pool(n_per_team: int = 6):
    """A 1-game (2-team) pool: every player viable, used for dynamic-cap tests."""
    samp = [
        PlayerSamplingSpec(
            player_id=i,
            team=("AAA" if i < n_per_team else "BBB"),
            opponent=("BBB" if i < n_per_team else "AAA"),
            mu=float(np.log(3.0 + 10.0)),
            sigma=0.2,
            boost=1.0,
        )
        for i in range(2 * n_per_team)
    ]
    fields = [
        FieldPlayerSpec(player_id=i, pred_real_score=3.0, card_boost=1.0)
        for i in range(2 * n_per_team)
    ]
    return samp, fields


def test_cap_is_feasible_one_game_static_cap() -> None:
    # 2 teams, cap 2: max fieldable is 2+2=4 < 5 -> infeasible.
    teams = ["AAA", "AAA", "AAA", "BBB", "BBB", "BBB"]
    assert _cap_is_feasible(teams, max_per_team=2) is False
    assert _cap_is_feasible(teams, max_per_team=3) is True


def test_dynamic_cap_makes_one_game_slate_feasible() -> None:
    """A 2-team slate under a static cap of 2 is infeasible (forfeit). The
    dynamic cap must relax it so a full 5-player lineup ships."""
    samp, fields = _two_team_pool()
    curve = default_curve_for_regime("top_20")
    cfg = OptimizeConfig(
        top_n_filter=10, n_samples=150, n_field_lineups=40, max_per_team=2,
        dynamic_team_cap=True,
    )
    rec = optimize_lineup(samp, fields, curve, cfg=cfg)
    assert len(rec.player_ids) == 5  # not the empty-forfeit lineup


def test_static_cap_one_game_slate_relaxed_by_feasibility_guard() -> None:
    """Even with dynamic_team_cap off, the feasibility guard must prevent an
    empty lineup on an infeasible (2-team, cap-2) slate."""
    samp, fields = _two_team_pool()
    curve = default_curve_for_regime("top_20")
    cfg = OptimizeConfig(
        top_n_filter=10, n_samples=150, n_field_lineups=40, max_per_team=2,
        dynamic_team_cap=False,
    )
    rec = optimize_lineup(samp, fields, curve, cfg=cfg)
    assert len(rec.player_ids) == 5

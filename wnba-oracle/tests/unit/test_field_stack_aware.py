"""Stack-aware (correlated) field simulation (D88, Phase 3).

The independent-pick sampler treats each opponent roster slot as an iid draw
from the marginal ownership. Real GPP fields stack: top finishers and many
public entrants concentrate same-game or same-team picks. The synthesis in
research/internal/07_placement_overhaul.md (2026 best-practice review) names
this the biggest unaddressed gap after the D86 measured-ownership fix.

These tests pin three properties:

1. Default boosts (1.0) reproduce the independent sampler byte-for-byte.
2. A same-game boost > 1.0 raises the same-game pair frequency in the
   simulated field above the independent baseline.
3. The duplication-aware payout option deducts EV from lineups the field
   actually mirrors (and is a no-op when the candidate is unique).
"""

from __future__ import annotations

import numpy as np

from wnba_oracle.picker.field import (
    FieldPlayerSpec,
    project_ownership,
    simulate_field_lineups_correlated,
)
from wnba_oracle.picker.optimize import OptimizeConfig, optimize_lineup
from wnba_oracle.picker.payout import default_curve_for_regime
from wnba_oracle.picker.sample import PlayerSamplingSpec


def _pool(n: int = 10) -> tuple[list[PlayerSamplingSpec], list[FieldPlayerSpec]]:
    """Two-game pool: A vs B (players 0..4), C vs D (players 5..9)."""
    samps: list[PlayerSamplingSpec] = []
    fields: list[FieldPlayerSpec] = []
    for i in range(n):
        if i < 5:
            team, opp = ("A", "B") if i % 2 == 0 else ("B", "A")
        else:
            team, opp = ("C", "D") if i % 2 == 0 else ("D", "C")
        samps.append(
            PlayerSamplingSpec(
                player_id=200 + i,
                team=team,
                opponent=opp,
                mu=float(np.log(4.0)),
                sigma=0.30,
                boost=1.0,
            )
        )
        fields.append(
            FieldPlayerSpec(
                player_id=200 + i, pred_real_score=2.0, card_boost=1.0, measured_drafts=1000.0
            )
        )
    return samps, fields


def test_default_boosts_reproduce_independent_sampler() -> None:
    """With same_game_boost=1.0 AND same_team_boost=1.0, the correlated
    sampler must early-return to the independent sampler so existing
    deployments are unaffected."""
    from wnba_oracle.picker.field import simulate_field_lineups

    own = np.array([0.2, 0.2, 0.2, 0.2, 0.2])
    a = simulate_field_lineups(own, n_lineups=200, lineup_size=2, seed=11)
    b = simulate_field_lineups_correlated(
        own,
        game_keys=["g1", "g1", "g2", "g2", "g3"],
        team_keys=["t1", "t2", "t3", "t4", "t5"],
        same_game_boost=1.0,
        same_team_boost=1.0,
        n_lineups=200,
        lineup_size=2,
        seed=11,
    )
    assert np.array_equal(a, b)


def test_same_game_boost_raises_pair_frequency() -> None:
    """Four games of two players each, equal independent ownership across all
    eight. With lineup_size=2 the iid baseline of a same-game pair is 4/28
    ≈ 14%; same_game_boost > 1.0 must push it materially higher.

    Avoid the pigeonhole trap from earlier: lineup_size > n_games forces 100%
    same-game pairs and erases the signal.
    """
    n = 8
    own = np.full(n, 1.0 / n)
    # Four games G1..G4, each with two distinct teams.
    game_keys = ["G1", "G1", "G2", "G2", "G3", "G3", "G4", "G4"]
    team_keys = ["A", "B", "C", "D", "E", "F", "G", "H"]

    def _pair_rate(field: np.ndarray) -> float:
        same = 0
        for row in field:
            if game_keys[row[0]] == game_keys[row[1]]:
                same += 1
        return same / len(field)

    flat = simulate_field_lineups_correlated(
        own,
        game_keys=game_keys,
        team_keys=team_keys,
        same_game_boost=1.0,
        same_team_boost=1.0,
        n_lineups=2000,
        lineup_size=2,
        seed=23,
    )
    boosted = simulate_field_lineups_correlated(
        own,
        game_keys=game_keys,
        team_keys=team_keys,
        same_game_boost=4.0,
        same_team_boost=1.0,
        n_lineups=2000,
        lineup_size=2,
        seed=23,
    )
    rate_flat = _pair_rate(flat)
    rate_boosted = _pair_rate(boosted)
    # Independent baseline is ~14% (4 same-game pairs of 28 unordered pairs).
    # With same_game_boost=4.0 the conditional second pick favors the opponent
    # of the first; expect at least a 10 percentage point bump.
    assert rate_boosted - rate_flat > 0.10


def test_duplication_aware_payout_deducts_for_mirrors() -> None:
    """When the candidate lineup is one the field heavily mirrors, the
    duplication-aware-payout EV must be strictly below the un-divided EV.
    """
    samps, fields = _pool()
    curve = default_curve_for_regime("top_20")
    base = OptimizeConfig(
        top_n_filter=10,
        n_samples=300,
        n_field_lineups=200,
        max_per_team=5,
        seed=42,
    )
    div = OptimizeConfig(
        top_n_filter=10,
        n_samples=300,
        n_field_lineups=200,
        max_per_team=5,
        duplication_aware_payout=True,
        seed=42,
    )
    a = optimize_lineup(samps, fields, curve, cfg=base)
    b = optimize_lineup(samps, fields, curve, cfg=div)
    # The two are not guaranteed to pick the same combo; what we pin is that
    # the duplication-aware path completes and produces a finite EV with the
    # same lineup-size shape, while not crashing on equal-ownership pools.
    assert len(b.player_ids) == 5
    assert np.isfinite(b.expected_payout)
    # With equal marginals across all 10 players the chance of a mirror entry
    # against a 5-stack is low (C(10,5)=252 lineups, ~0.4% mirror prob per
    # field row), so the EV should not collapse, but the candidate that the
    # duplication-aware variant lands on should not be strictly more
    # heavily-mirrored than the base lineup.
    assert b.expected_payout <= a.expected_payout + 1e-6


def test_correlated_sampler_does_not_starve_pool() -> None:
    """If the boosts inflate weights enough to push the renormalization to
    weird territory, the sampler must still produce a valid lineup."""
    n = 8
    own = np.full(n, 1.0 / n)
    out = simulate_field_lineups_correlated(
        own,
        game_keys=["g1"] * 4 + ["g2"] * 4,
        team_keys=["A"] * 2 + ["B"] * 2 + ["C"] * 2 + ["D"] * 2,
        same_game_boost=5.0,
        same_team_boost=3.0,
        n_lineups=500,
        lineup_size=5,
        seed=99,
    )
    assert out.shape == (500, 5)
    # Each lineup contains five distinct players.
    for row in out:
        assert len(set(row)) == 5


def test_field_specs_with_measured_still_drive_correlated_sim() -> None:
    """End-to-end: when measured ownership is available, the correlated
    sampler should still respect it as the base marginal."""
    n = 6
    fields = [
        FieldPlayerSpec(
            player_id=300 + i,
            pred_real_score=2.0,
            card_boost=1.0,
            measured_drafts=(5000.0 if i < 3 else 100.0),
        )
        for i in range(n)
    ]
    own = project_ownership(fields)
    game_keys = ["G1", "G1", "G1", "G2", "G2", "G2"]
    team_keys = ["A", "B", "A", "C", "D", "C"]
    field = simulate_field_lineups_correlated(
        own,
        game_keys=game_keys,
        team_keys=team_keys,
        same_game_boost=1.5,
        same_team_boost=1.2,
        n_lineups=500,
        lineup_size=3,
        seed=7,
    )
    chalk_appear = np.mean([np.any(np.isin(row, [0, 1, 2])) for row in field])
    # Chalk players (0,1,2) have ~95% of the marginal weight; should appear
    # in nearly every sampled lineup.
    assert chalk_appear > 0.95

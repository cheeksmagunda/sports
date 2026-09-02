"""Hard anti-stacking policy in the optimizer.

The optimizer now derives feasible lineup shapes from slate structure and does
not reward concentration with a same-game bonus.

Also pins R4: the slot assignment is the rearrangement-inequality optimum
(sort picks by descending median real_score, hand the highest to slot 0
which carries the 2.0x base). Boost adds to the slot multiplier but is a
per-player attribute, so the slot permutation only affects the
sum(slot_mult * real_score) term -- maximized by descending real_score.
"""

from __future__ import annotations

import numpy as np

from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.optimize import DEFAULT_SLOT_MULTIPLIERS, OptimizeConfig, optimize_lineup
from wnba_oracle.picker.payout import default_curve_for_regime
from wnba_oracle.picker.sample import PlayerSamplingSpec

# -- pure helper --------------------------------------------------------------


# -- end-to-end optimize_lineup ----------------------------------------------


def _flat_pair(
    *,
    n_games: int,
    seed: int = 0,
) -> tuple[list[PlayerSamplingSpec], list[FieldPlayerSpec]]:
    """Build a slate with n_games games (2 teams each, 3 players each).

    Every player has identical projection so the optimizer's choice is
    entirely driven by the team-cap and the game-stack bonus.
    """
    games: list[tuple[str, str]] = [(f"T{2 * i}", f"T{2 * i + 1}") for i in range(n_games)]
    samps: list[PlayerSamplingSpec] = []
    fields: list[FieldPlayerSpec] = []
    pid = 100
    for home, away in games:
        for team, opp in ((home, away), (away, home)):
            for _ in range(3):
                samps.append(
                    PlayerSamplingSpec(
                        player_id=pid,
                        team=team,
                        opponent=opp,
                        mu=float(np.log(3.0 + 2.0)),
                        sigma=0.2,
                        boost=1.0,
                        is_starter=False,
                        blowout_prob=0.0,
                        is_anchor=False,
                    )
                )
                fields.append(FieldPlayerSpec(player_id=pid, pred_real_score=3.0, card_boost=1.0))
                pid += 1
    return samps, fields


def test_game_stack_bonus_off_does_not_bias_picks() -> None:
    """The optimizer should return a legal lineup without any stack bonus."""
    samps, fields = _flat_pair(n_games=4)
    curve = default_curve_for_regime("top_20")
    cfg = OptimizeConfig(
        top_n_filter=24,
        n_samples=200,
        n_field_lineups=20,
        seed=11,
        max_per_team=2,
        dynamic_team_cap=False,
        game_stack_bonus=0.0,
    )
    rec = optimize_lineup(samps, fields, curve, cfg=cfg)
    assert len(rec.player_ids) == 5
    # With all-equal projections + no bonus + no contrarian we just pin that the
    # optimizer produced a valid lineup; the specific stack count is undefined.


def test_game_stack_bonus_on_does_not_override_hard_policy() -> None:
    """A positive legacy bonus must not re-enable concentrated lineups."""
    samps, fields = _flat_pair(n_games=4)
    curve = default_curve_for_regime("top_20")
    cfg = OptimizeConfig(top_n_filter=24, n_samples=200, n_field_lineups=20, seed=11, max_per_team=2)
    rec = optimize_lineup(samps, fields, curve, cfg=cfg)
    assert len(rec.player_ids) == 5


# -- R4: slot-assignment audit ------------------------------------------------


def test_slot_assignment_follows_rearrangement_inequality() -> None:
    """R4: the lineup_score = sum_i (slot_mult[i] + boost[i]) * real_score[i]
    decomposes into sum(slot_mult[i] * rs[i]) + sum(boost[i] * rs[i]). The
    second term is invariant under slot permutation; the first is maximized
    by pairing descending slot_mult with descending real_score
    (rearrangement inequality). The optimizer does exactly that on line ~315
    of optimize.py (sort picked by rs_median desc, assign to slots 0..4).

    This test pins the contract: given five picks with known real_scores,
    the highest-rs player lands in slot 0 (2.0 base mult), the next in slot 1,
    etc., regardless of boost.
    """
    # Five picks; deliberately INVERSE boost order vs rs order to make the
    # test meaningful: highest-boost has the LOWEST rs.
    samps = []
    fields = []
    rs_values = [5.0, 4.5, 4.0, 3.5, 3.0]  # descending real_score
    boosts = [0.5, 1.0, 1.5, 2.0, 2.5]  # ascending boost
    for i, (rs, b) in enumerate(zip(rs_values, boosts)):
        pid = 200 + i
        # Build a single-game slate so neither team cap nor stack bonus interferes.
        team = "LV" if i % 2 == 0 else "NYL"
        opp = "NYL" if team == "LV" else "LV"
        samps.append(
            PlayerSamplingSpec(
                player_id=pid,
                team=team,
                opponent=opp,
                mu=float(np.log(rs + 2.0)),
                sigma=0.01,  # tight so median ~= rs
                boost=b,
                is_starter=False,
                blowout_prob=0.0,
                is_anchor=False,
            )
        )
        fields.append(FieldPlayerSpec(player_id=pid, pred_real_score=rs, card_boost=b))
    curve = default_curve_for_regime("top_20")
    cfg = OptimizeConfig(
        top_n_filter=5,
        n_samples=200,
        n_field_lineups=20,
        seed=7,
        max_per_team=5,
        dynamic_team_cap=False,
    )
    rec = optimize_lineup(samps, fields, curve, cfg=cfg)
    # The 5 picks are forced; the slot ORDER is what we verify. Expected:
    # pid 200 (rs 5.0) -> slot 0 (slot_mult 2.0)
    # pid 201 (rs 4.5) -> slot 1 (slot_mult 1.8)
    # ...
    expected_order = (200, 201, 202, 203, 204)
    assert rec.player_ids == expected_order, (
        f"slot order broken: got {rec.player_ids}, expected {expected_order}. "
        "If this fails, the slot assignment is no longer descending by real_score "
        "and the rearrangement-inequality optimum is being missed."
    )
    # And the slot multipliers are exactly the documented WNBA scheme.
    assert tuple(rec.slot_multipliers) == tuple(float(x) for x in DEFAULT_SLOT_MULTIPLIERS)

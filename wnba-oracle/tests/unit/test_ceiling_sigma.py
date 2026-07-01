"""Environment-conditioned ceiling sigma scaling.

Per-player sigma, not just mu, is the primary upper-tail signal for top-heavy
contests. These tests pin `ceiling_adjusted_sigma_log`:

  - Default boosts (0.0) leave base_sigma untouched (byte-identical).
  - blowout_prob > 0 with a non-zero blowout_boost widens sigma.
  - Low n_history_games with a non-zero low_history_boost widens sigma.
  - The sigma_log_cap prevents runaway scaling on stacked extreme inputs.
  - End-to-end: in the optimizer, widening sigma raises the candidate
    lineup's upper-tail percentile relative to the base config.
"""

from __future__ import annotations

import numpy as np

from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.optimize import OptimizeConfig, optimize_lineup
from wnba_oracle.picker.payout import default_curve_for_regime
from wnba_oracle.picker.sample import (
    PlayerSamplingSpec,
    ceiling_adjusted_sigma_log,
)


def test_default_boosts_passthrough() -> None:
    """Both boosts = 0.0 returns the base sigma unchanged."""
    base = 0.30
    out = ceiling_adjusted_sigma_log(
        base,
        blowout_prob=0.8,
        n_history_games=0,
        blowout_boost=0.0,
        low_history_boost=0.0,
    )
    assert out == base


def test_blowout_boost_widens_for_blowout_game() -> None:
    """When blowout_prob is high and blowout_boost > 0, sigma increases."""
    base = 0.30
    out_close = ceiling_adjusted_sigma_log(
        base,
        blowout_prob=0.0,
        n_history_games=25,
        blowout_boost=0.20,
    )
    out_blowout = ceiling_adjusted_sigma_log(
        base,
        blowout_prob=1.0,
        n_history_games=25,
        blowout_boost=0.20,
    )
    assert np.isclose(out_close, base)
    assert out_blowout > out_close
    # Exactly 0.30 * (1 + 0.20) = 0.36
    assert np.isclose(out_blowout, 0.36)


def test_low_history_boost_widens_for_few_games() -> None:
    """A player with 0 recent games sees sigma scaled by (1 + low_history_boost).
    A player at the high_history_target sees no scaling.
    """
    base = 0.30
    out_seen = ceiling_adjusted_sigma_log(
        base,
        blowout_prob=0.0,
        n_history_games=25,
        low_history_boost=0.30,
        high_history_target=25,
    )
    out_unseen = ceiling_adjusted_sigma_log(
        base,
        blowout_prob=0.0,
        n_history_games=0,
        low_history_boost=0.30,
        high_history_target=25,
    )
    out_partial = ceiling_adjusted_sigma_log(
        base,
        blowout_prob=0.0,
        n_history_games=12,
        low_history_boost=0.30,
        high_history_target=25,
    )
    assert np.isclose(out_seen, base)
    assert np.isclose(out_unseen, 0.30 * 1.30)
    assert out_seen < out_partial < out_unseen


def test_sigma_cap_prevents_runaway() -> None:
    """Stacking maximum blowout + zero history + huge boosts must not exceed
    the configured sigma_log_cap."""
    out = ceiling_adjusted_sigma_log(
        0.60,
        blowout_prob=1.0,
        n_history_games=0,
        blowout_boost=2.0,
        low_history_boost=2.0,
        sigma_log_cap=0.9,
    )
    assert out == 0.9


def test_combined_terms_are_additive() -> None:
    """Blowout + low-history terms combine additively within the (1 + ...) scale."""
    base = 0.20
    out = ceiling_adjusted_sigma_log(
        base,
        blowout_prob=0.5,
        n_history_games=10,
        blowout_boost=0.20,
        low_history_boost=0.30,
        high_history_target=25,
    )
    # blowout_term = 0.20 * 0.5 = 0.10
    # low_hist_term = 0.30 * (1 - 10/25) = 0.30 * 0.6 = 0.18
    # scaled = 0.20 * (1 + 0.10 + 0.18) = 0.20 * 1.28 = 0.256
    assert np.isclose(out, 0.256)


def test_optimizer_picks_higher_p90_when_sigma_widened() -> None:
    """End-to-end: a pool sampled with wider sigma should produce a candidate
    with a higher P90 lineup-score than the same pool with narrow sigma. We
    compare two manually-built spec sets that differ only in sigma."""
    n = 8
    base_samps = []
    fields = []
    for i in range(n):
        team = "A" if i % 2 == 0 else "B"
        opp = "B" if team == "A" else "A"
        base_samps.append(
            PlayerSamplingSpec(
                player_id=400 + i,
                team=team,
                opponent=opp,
                mu=float(np.log(4.0)),
                sigma=0.20,
                boost=1.0,
            )
        )
        fields.append(
            FieldPlayerSpec(
                player_id=400 + i,
                pred_real_score=2.0,
                card_boost=1.0,
                measured_drafts=1000.0,
            )
        )
    wide_samps = [
        PlayerSamplingSpec(
            player_id=s.player_id,
            team=s.team,
            opponent=s.opponent,
            mu=s.mu,
            sigma=0.55,  # widened
            boost=s.boost,
        )
        for s in base_samps
    ]
    curve = default_curve_for_regime("top_20")
    cfg = OptimizeConfig(
        top_n_filter=10, n_samples=400, n_field_lineups=80, max_per_team=5, seed=17
    )
    base = optimize_lineup(base_samps, fields, curve, cfg=cfg)
    wide = optimize_lineup(wide_samps, fields, curve, cfg=cfg)
    # Widening sigma must raise the p90 of the chosen lineup's score samples.
    assert wide.lineup_score_p90 > base.lineup_score_p90

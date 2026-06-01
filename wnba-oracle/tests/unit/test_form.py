"""predict/form.py: boost prior, recency challenger, per-player volatility."""

from __future__ import annotations

from wnba_oracle.predict.form import (
    FormConfig,
    boost_prior,
    player_volatility,
    predict_real_scores,
)


def test_boost_prior_matches_heuristic_relation() -> None:
    # D43 relation, floored at 0.5.
    assert abs(boost_prior(0.0) - 3.16) < 1e-9
    assert abs(boost_prior(2.0) - (3.16 - 0.9)) < 1e-9
    assert boost_prior(100.0) == 0.5  # floor


def test_boost_prior_decreasing() -> None:
    assert boost_prior(0.0) > boost_prior(1.5) > boost_prior(3.0)


def test_predict_falls_back_to_prior_with_no_history() -> None:
    out = predict_real_scores({}, {7: 1.0})
    assert abs(out[7] - boost_prior(1.0)) < 1e-9


def test_predict_pulls_toward_recent_form() -> None:
    # A player whose recent games (most-recent-first) are well above the boost
    # prior should land above the prior but below the raw recent mean (shrink).
    boost = 2.0
    prior_mean = boost_prior(boost)
    recent = [6.0, 6.0, 6.0, 6.0, 6.0, 6.0]
    out = predict_real_scores({7: recent}, {7: boost}, cfg=FormConfig(prior_strength=2.0))
    assert prior_mean < out[7] < 6.0


def test_volatility_default_for_low_sample() -> None:
    vol = player_volatility({7: [2.0, 2.0]}, default=1.17, min_obs=4)
    assert vol[7] == 1.17


def test_volatility_clamped_and_computed() -> None:
    # Wildly swinging player -> high vol, clamped to max.
    vol = player_volatility({7: [0.0, 10.0, 0.0, 10.0, 0.0, 10.0]}, max_sigma=1.8)
    assert vol[7] == 1.8
    # Steady player -> low vol, clamped to min.
    vol2 = player_volatility({8: [2.5, 2.5, 2.5, 2.5, 2.5]}, min_sigma=0.7)
    assert vol2[8] == 0.7

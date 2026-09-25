"""Boost-aware projection signal applied before five-card optimize.

Production predicts raw Real value; the optimizer already scores
``value * (slot + boost)``. Contest-pool replay on Corpus C (#318 / #280)
still shows the shortfall is player selection, and the gap is largest on
boosted contests (87 of 91). Provider card boosts are observed pre-lock and
carry information the raw-value model alone does not recover.

This module applies a small, explicit additive lift to each projection's
conditional samples proportional to ``card_boost`` when the slate is in the
``provider_boosts_present`` regime. Zero-boost slates are unchanged. The
lift is an evidence-gated ``PipelinePolicy`` knob (default small, not a
Railway env flip). Authority for justified knob changes: commit ``3ec2bad``
and former #37.
"""

from __future__ import annotations

from collections.abc import Sequence

from nfl_oracle.recommendations.model import Projection
from nfl_oracle.recommendations.schema import Slate

# Real-value points added to conditional_mean per card_boost point when the
# slate publishes provider boosts. Sized so a max boost (3.0) moves a player
# about 0.75 Real points before availability weighting - enough to change
# set selection on close calls without drowning the model. Unit tests pin
# the boosted-sleeper fixture; live capture ratios stay measured on the
# contest-pool harness.
DEFAULT_BOOST_SIGNAL_PER_POINT = 0.25


def apply_boost_aware_projections(
    projections: Sequence[Projection],
    slate: Slate,
    *,
    signal_per_boost_point: float = DEFAULT_BOOST_SIGNAL_PER_POINT,
) -> tuple[Projection, ...]:
    """Return projections with a boost-proportional lift, or the input unchanged.

    The optimizer still applies the scoring law ``value * (slot + boost)`` on
    these adjusted samples. The lift is a projection-side prior, not a second
    scoring pass: it only runs when ``boost_regime == provider_boosts_present``
    and ``signal_per_boost_point > 0``.
    """
    if signal_per_boost_point <= 0 or slate.boost_regime != "provider_boosts_present":
        return tuple(projections)
    candidates = {player.player_id: player for player in slate.candidates}
    adjusted: list[Projection] = []
    for projection in projections:
        player = candidates.get(projection.player_id)
        if player is None:
            raise ValueError("projection_pool_mismatch")
        boost = float(player.card_boost)
        if boost <= 0:
            adjusted.append(projection)
            continue
        lift = signal_per_boost_point * boost
        conditional = float(projection.conditional_mean) + lift
        samples = tuple(float(sample) + lift for sample in projection.samples)
        adjusted.append(
            projection.model_copy(
                update={
                    "conditional_mean": conditional,
                    "mean": conditional * float(projection.availability_probability),
                    "samples": samples,
                    "provenance": tuple(projection.provenance) + ("boost_aware_projection_signal",),
                }
            )
        )
    return tuple(adjusted)

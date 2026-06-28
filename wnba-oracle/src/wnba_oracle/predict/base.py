"""Base prediction functions: boost prior calibration and per-player volatility.

These are actively used by the production serving path (job2) and minutes
model. Extracted from form.py (D102 cleanup: removing unused recency blend).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def boost_prior(card_boost: float) -> float:
	"""Cold-start prior: the calibrated boost handicap relation (D43).

	Calibrated 2026-05-27 against the 16-slate parquet corpus:
	`real_score = 3.16 - 0.45 * card_boost` (linear fit, n=449
	player-slates from 2026-05-10 onward — the date the boost system
	rolled out). The slope is NEGATIVE because card_boost is a handicap
	the platform assigns to weaker baseline players to balance the
	multiplier contribution. A boost-3 player has lower expected
	real_score (1.8) than a boost-0 player (3.16); the boost mechanic
	compensates via the additive (slot + boost) effective multiplier.

	Floored at 0.5 because the picker uses pred_real_score as the
	log-scale mean for sampling, and a near-zero centre would explode
	the percentile band.
	"""
	return max(0.5, 3.16 - 0.45 * float(card_boost))


def player_volatility(
	prior_by_player: Mapping[int, Sequence[float]],
	*,
	default: float = 1.17,
	min_sigma: float = 0.7,
	max_sigma: float = 1.8,
	min_obs: int = 4,
) -> dict[int, float]:
	"""Per-player real_score volatility (sample std of prior scores), clamped.

	Drives per-player sampling spread so high-variance ceiling plays are priced
	as ceiling and high-floor starters as floor, instead of the flat sigma the
	sampler used before. Players with < min_obs prior games get `default` (the
	league per-player median std). Returned in REAL_SCORE units; the sampler
	converts to its log-scale sigma.
	"""
	out: dict[int, float] = {}
	for pid, scores in prior_by_player.items():
		vals = list(scores)
		if len(vals) < min_obs:
			out[int(pid)] = default
			continue
		m = sum(vals) / len(vals)
		var = sum((v - m) ** 2 for v in vals) / (len(vals) - 1)
		sd = var**0.5
		out[int(pid)] = min(max_sigma, max(min_sigma, sd))
	return out

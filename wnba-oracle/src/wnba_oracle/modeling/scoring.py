"""Pure scoring and feature-extraction helpers for the model kernel.

Split out of scheduler/job2.py to give the freeze pipeline a structural seam:
this module holds functions of ``features_json`` and dicts only. No DB,
no Redis, no filesystem, no clocks. Job 2 re-exports these names so
``job2._prop_signal_multiplier`` and ``from wnba_oracle.scheduler.job2
import _effective_confirmed`` both keep working for existing tests.
"""

from __future__ import annotations

from wnba_oracle.common.feature_payload import parse_feature_mapping
from wnba_oracle.features.injury_cascade import CascadeInput, redistribute_minutes


def _heuristic_real_score(card_boost: float) -> float:
    """Transparent fallback used when no model artifact is loaded.

    Calibrated 2026-05-27 against the 16-slate parquet corpus (D43):
    `real_score = 3.16 - 0.45 * card_boost`. Floored at 0.5 because the
    picker uses pred_real_score as the log-scale mean for sampling; a
    near-zero centre would explode the percentile band.
    """
    return max(0.5, 3.16 - 0.45 * card_boost)


def _features_dict(features_json: object) -> dict:
    """Coerce the features_json column into a dict. psycopg returns JSONB
    as parsed dicts; older test fixtures pass strings."""
    return parse_feature_mapping(features_json)[0]


def _vegas_from_features(features_json: object) -> tuple[float, float]:
    """Extract (vegas_total, vegas_spread). (0.0, 0.0) when absent so the
    game-script multiplier degrades to neutral."""
    f = _features_dict(features_json)
    return (
        float(f.get("vegas_total", 0.0) or 0.0),
        float(f.get("vegas_spread", 0.0) or 0.0),
    )


def _is_out_from_features(features_json: object) -> bool:
    """Drop signal: RotoWire confirmed OUT/IL/INJ/NA/INACTIVE. job1 writes
    ``is_out`` as an int (0/1) into features_json after matching each Real
    Sports player to the RotoWire lineup index."""
    f = _features_dict(features_json)
    return bool(int(f.get("is_out", 0) or 0))


def _effective_confirmed(f: dict, *, use_expected: bool) -> bool:
    """Whether RotoWire gives a trustworthy same-day STARTER role (D104).

    A CONFIRMED row always counts. An EXPECTED start (RotoWire-listed in the
    top five, ``is_starter=1``) counts too when ``use_expected`` is set --
    confirmed lineups for every game on a slate are not all posted by the
    T-40 freeze of the first tip, so the expected lineup from the 13:00 job1
    scrape is the operative signal. An expected NON-starter is left neutral
    (RotoWire's expected bench order is noisy); only a CONFIRMED bench is
    faded.
    """
    if int(f.get("rotowire_confirmed", 0) or 0):
        return True
    return use_expected and bool(int(f.get("is_starter", 0) or 0))


def _starter_multiplier(
    features_json: object,
    *,
    enabled: bool,
    use_expected: bool = True,
    unknown_fade: float = 1.0,
) -> float:
    """Real_score multiplier from the RotoWire starter signal (D52, D104).

    starter -> 1.10, faded (confirmed) non-starter -> 0.82. Unknown role
    stays at ``unknown_fade`` (default 1.0 = neutral, pre-2026-07-04). A
    fade < 1.0 pushes DNP-prone role players down the stage-1 rank; the
    fade is symmetric on the head's p10/p90 interval so sampling sigma
    stays proportional.

    2026-07-04 calibration (scripts/calibrate_starter_and_boost.py):
    unknowns realize 0.685x the mean real_score of expected starters and
    DNP at 5.8% vs 0.6%. STARTER_UNKNOWN_FADE=0.75 matches empirical.
    """
    if not enabled:
        return 1.0
    f = _features_dict(features_json)
    if not _effective_confirmed(f, use_expected=use_expected):
        return unknown_fade
    return 1.10 if int(f.get("is_starter", 0) or 0) else 0.82


def _starter_minutes_lift(
    features_json: object,
    *,
    enabled: bool,
    use_expected: bool = True,
    norm: float = 25.0,
    weight: float = 0.6,
    cap: float = 1.3,
) -> float:
    """Minutes-conditional lift for expected starters whose minutes history
    lags their role (2026-07-10, the Kuier/Harris class).

    The Tier-1 blended path already pulls projected minutes toward the
    starter anchor via ``project_minutes_from_base`` (confirm_weight=0.6
    toward 30), but the Tier-0 head path bypasses it entirely: the head
    predicts from game-log features, so a player promoted to the starting
    five carries pre-promotion minutes into tonight's p50 and gets only the
    flat 1.10 starter nudge. Corpus (through 2026-07-07): expected starters
    with recent_minutes < 21 realize 1.66x their naive projection at the
    median (n=37) vs ~1.02x for established starters -- the single most
    under-projected class, and exactly where large card boosts live.

    lift = blended / recent, blended = (1 - weight) * recent + weight * norm,
    clamped to [1.0, cap]. Neutral for non-starters, unknown roles, players
    at/above the norm, and players with no recent-minutes feature.
    """
    if not enabled:
        return 1.0
    f = _features_dict(features_json)
    if not int(f.get("is_starter", 0) or 0):
        return 1.0
    if not _effective_confirmed(f, use_expected=use_expected):
        return 1.0
    rmin = float(f.get("recent_minutes", 0.0) or 0.0)
    if rmin <= 0.0 or rmin >= norm:
        return 1.0
    blended = (1.0 - weight) * rmin + weight * norm
    return min(cap, max(1.0, blended / rmin))


def _floor_tilt_multiplier(
    p10: float,
    p50: float,
    boost: float,
    *,
    weight: float,
    max_boost: float = 2.0,
) -> float:
    """Floor-blended sampling/rank center for non-spike candidates
    (2026-07-10, the Ogunbowale-vs-Shepard fix).

    Winning lineups' mid slots (the 1.8/1.6/1.4 multipliers) are floor
    plays; the spike slot is where ceiling belongs. Blending the center
    toward p10 fades a candidate proportional to their downside spread:
    a locked-in starter with a tight interval is barely touched, a
    wide-interval ceiling play drops. Applies only when card_boost <
    ``max_boost`` so the boost tail (the spike tier) keeps its ceiling
    treatment. Returns the multiplier on p50 (1.0 when weight=0, p50<=0,
    or the candidate is spike-tier).
    """
    if weight <= 0.0 or boost >= max_boost or p50 <= 0.0:
        return 1.0
    blended = (1.0 - weight) * p50 + weight * min(p10, p50)
    return max(0.0, blended / p50)


def _prop_signal_multiplier(features_json: object, *, scale: float) -> float:
    """Real_score multiplier from sportsbook player-prop over/under (D78).

    Formula: multiplier = 1 + (over_prob - 0.5) * scale. Clipped to
    [0.85, 1.15]. Returns 1.0 when scale=0 or no prop data.
    """
    if scale <= 0.0:
        return 1.0
    f = _features_dict(features_json)
    line = float(f.get("prop_points_line", 0.0) or 0.0)
    if line <= 0.0:
        return 1.0
    raw_prob = f.get("prop_points_over_prob")
    over_prob = float(raw_prob) if raw_prob is not None else 0.5
    raw = 1.0 + (over_prob - 0.5) * scale
    return max(0.85, min(1.15, raw))


def _minutes_features(features_json: object) -> dict | None:
    """Pull the D55 minutes features job1 persisted, or None if absent
    (job1 couldn't reach stats.wnba.com, or no match) -> caller falls back
    to boost."""
    f = _features_dict(features_json)
    if "per_min_rate" not in f or "recent_minutes" not in f:
        return None
    return {
        "recent_minutes": float(f.get("recent_minutes", 0.0) or 0.0),
        "per_min_rate": float(f.get("per_min_rate", 0.0) or 0.0),
        "minutes_vol": float(f.get("minutes_vol", 5.0) or 5.0),
        "n_min_games": int(f.get("n_min_games", 0) or 0),
    }


def _cascade_bonuses(enrichment_raw: list[dict]) -> dict[int, float]:
    """Injury-cascade bonus minutes per player (D55). Built from the FULL
    pool (incl. OUT players, who are the donors) using each player's
    recent_minutes as minutes_l10. Empty when no OUT player has minutes
    history."""
    rows: list[CascadeInput] = []
    for r in enrichment_raw:
        mf = _minutes_features(r.get("features_json"))
        if mf is None:
            continue
        pid_raw = r.get("real_sports_player_id")
        if pid_raw is None:
            continue
        try:
            pid = int(pid_raw)
        except (TypeError, ValueError):
            continue
        rows.append(
            CascadeInput(
                player_id=pid,
                team=str(r.get("team", "") or ""),
                position=str(r.get("position", "") or ""),
                minutes_l10=mf["recent_minutes"],
                is_out=_is_out_from_features(r.get("features_json")),
            )
        )
    return redistribute_minutes(rows) if rows else {}

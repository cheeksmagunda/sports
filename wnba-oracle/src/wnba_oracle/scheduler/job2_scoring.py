"""Pure scoring/feature-extraction helpers for Job 2.

Split out of scheduler/job2.py to give the freeze pipeline a structural seam:
this module holds functions of ``features_json`` and dicts only. No DB,
no Redis, no filesystem, no clocks. Job 2 re-exports these names so
``job2._prop_signal_multiplier`` and ``from wnba_oracle.scheduler.job2
import _effective_confirmed`` both keep working for existing tests.
"""

from __future__ import annotations

import json as _json

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
    if not features_json:
        return {}
    if isinstance(features_json, str):
        try:
            return _json.loads(features_json)
        except _json.JSONDecodeError:
            return {}
    return features_json if isinstance(features_json, dict) else {}


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
    features_json: object, *, enabled: bool, use_expected: bool = True
) -> float:
    """Real_score multiplier from the RotoWire starter signal (D52, D104).

    starter -> 1.10, faded (confirmed) non-starter -> 0.82. Unknown role
    stays at 1.0.
    """
    if not enabled:
        return 1.0
    f = _features_dict(features_json)
    if not _effective_confirmed(f, use_expected=use_expected):
        return 1.0
    return 1.10 if int(f.get("is_starter", 0) or 0) else 0.82


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

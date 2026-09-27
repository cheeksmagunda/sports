"""Own-model pre-slate feature map for NHL (#535 / #523 pattern).

NHL has no LightGBM primary. The forward own-model path is historical
priors (``baselines.priors``) with room for a later NHL-owned ridge /
valuelaw head. This map classifies planned pre-slate features so they do
not silently fall through to an LGBM-shaped design matrix.
"""

from __future__ import annotations

from typing import Literal

NhlOwnStatus = Literal[
    "prior_core",
    "history_feature",
    "identity_encode",
    "boost_gated",
    "leakage_blocked",
    "lgbm_forbidden",
]

# Features the chronological prior path already consumes via ValueLabel.
PRIOR_CORE_FEATURES: frozenset[str] = frozenset(
    {
        "position",
        "player_id",
        "season",
    }
)

# Pre-slate history features intended for a future NHL ridge / valuelaw head
# (public box / role evidence). Not same-slate finals.
HISTORY_FEATURES: frozenset[str] = frozenset(
    {
        "toi_l5",
        "toi_l10",
        "shots_l5",
        "shots_l10",
        "pp_toi_share_l5",
        "even_strength_toi_l5",
        "days_rest",
        "is_home",
        "opponent_team_id",
        "goalie_start_prob",
        "team_goals_for_l10",
        "opp_goals_against_l10",
    }
)

IDENTITY_ENCODE_FEATURES: frozenset[str] = frozenset(
    {
        "team_id",
        "game_id",
        "contest_id",
        "slate_date",
    }
)

# Live card boost is gated to 0 until all teams have played (#501 / #517).
BOOST_GATED_FEATURES: frozenset[str] = frozenset(
    {
        "card_boost",
        "multiplier_bonus",
    }
)

LEAKAGE_BLOCKED_FEATURES: frozenset[str] = frozenset(
    {
        "same_slate_final_value",
        "same_slate_bonus",
        "same_slate_ranks",
        "same_slate_ownership",
        "post_lock_boxes",
        "winning_draft_appearance",
    }
)

# Explicit: do not route NHL own-model through LightGBM as primary.
LGBM_FORBIDDEN_FEATURES: frozenset[str] = frozenset(
    {
        "lgbm_primary_score",
        "lightgbm_head",
    }
)

ALL_PRE_SLATE_FEATURES: frozenset[str] = (
    PRIOR_CORE_FEATURES | HISTORY_FEATURES | IDENTITY_ENCODE_FEATURES | BOOST_GATED_FEATURES
)


def classify_feature(name: str) -> NhlOwnStatus:
    if name in LEAKAGE_BLOCKED_FEATURES or name in LGBM_FORBIDDEN_FEATURES:
        if name in LGBM_FORBIDDEN_FEATURES:
            return "lgbm_forbidden"
        return "leakage_blocked"
    if name in BOOST_GATED_FEATURES:
        return "boost_gated"
    if name in PRIOR_CORE_FEATURES:
        return "prior_core"
    if name in HISTORY_FEATURES:
        return "history_feature"
    if name in IDENTITY_ENCODE_FEATURES:
        return "identity_encode"
    return "identity_encode"


def _surface(status: NhlOwnStatus) -> str:
    if status == "prior_core":
        return "baselines.priors HistoricalPriorBaseline"
    if status == "history_feature":
        return "future NHL ridge/valuelaw head (not LightGBM primary)"
    if status == "identity_encode":
        return "schema.org identifier / categorical encode"
    if status == "boost_gated":
        return "contract.boost_gate (forced 0 until all teams played)"
    if status == "leakage_blocked":
        return "train_label_only / live blacklist"
    return "forbidden (no LightGBM primary)"


def own_model_gap_matrix() -> list[dict[str, str]]:
    """One row per planned pre-slate feature plus leakage / LGBM guards."""

    rows: list[dict[str, str]] = []
    for name in sorted(ALL_PRE_SLATE_FEATURES):
        status = classify_feature(name)
        rows.append({"feature": name, "status": status, "surface": _surface(status)})
    for name in sorted(LEAKAGE_BLOCKED_FEATURES | LGBM_FORBIDDEN_FEATURES):
        status = classify_feature(name)
        rows.append({"feature": name, "status": status, "surface": _surface(status)})
    return rows


def map_pre_slate_features(
    raw: dict[str, float | int | str | None],
) -> dict[str, float | int | str]:
    """Filter a pre-slate feature dict onto the own-model path.

    Drops leakage / LGBM-forbidden keys. Omits ``None`` values rather than
    coercing them to 0.0 (no silent None pollution). Boost-gated keys are
    kept only when explicitly numeric so freeze code can still zero them
    via ``boost_gate``.
    """

    out: dict[str, float | int | str] = {}
    for key, value in raw.items():
        status = classify_feature(key)
        if status in {"leakage_blocked", "lgbm_forbidden"}:
            continue
        if value is None:
            continue
        if isinstance(value, bool):
            out[key] = int(value)
            continue
        if isinstance(value, (int, float, str)):
            out[key] = value
            continue
        raise TypeError(f"unsupported_feature_type:{key}")
    return out

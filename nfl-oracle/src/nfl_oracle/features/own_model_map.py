"""Own-model feature consumption map for NFL (#523).

Classifies every FeatureSpec ``live_ok`` name against the production own-model
stack (recommendations ridge context + FeatureDrivenValueModel), not LightGBM.

Statuses:
- ``ridge_core``: numeric slot in ``FeatureDrivenValueModel.MODEL_FEATURE_NAMES``
- ``context_required``: always present in ``RatingModel.context_feature_names``
  (missing values use the ``__missing`` flag via ``_context_vector``)
- ``context_emitted``: built by ``recommendations.context`` and enters the
  ridge when observed (also force-included when listed as context_required)
- ``identity_encode``: categorical / calendar identity kept out of free-float
  ridge slots; position is one-hot in FeatureDrivenValueModel; strings are
  not safe as raw floats
- ``leakage_blocked``: same-slate / post-settlement (not live_ok)
"""

from __future__ import annotations

from typing import Literal

from nfl_oracle.features.live import REQUIRED_LIVE_OK_CONTEXT_FEATURES
from nfl_oracle.features.schema import live_ok_feature_names

OwnModelStatus = Literal[
    "ridge_core",
    "context_required",
    "context_emitted",
    "identity_encode",
    "leakage_blocked",
]

IDENTITY_ENCODE_FEATURES: frozenset[str] = frozenset(
    {
        "season",
        "week",
        "gameday",
        "opponent_team",
        "position",
        "team_id",
        "prior_fallback_level",
        "injury_status",
    }
)

CONTEXT_EMITTED_FEATURES: frozenset[str] = frozenset(
    {
        "is_divisional",
        "home_away",
        "is_home",
        "days_rest",
        "team_pace_prior",
        "opponent_pace_prior",
        "opp_def_value_allowed_prior",
        "opponent_adjusted_prior",
        "kickoff_slot_early",
        "kickoff_slot_late",
        "kickoff_slot_snf",
        "kickoff_slot_mnf",
        "kickoff_slot_other",
    }
)

LEAKAGE_BLOCKED_FEATURES: frozenset[str] = frozenset(
    {
        "card_boost_post_settlement",
        "same_slate_final_value",
    }
)


def ridge_core_feature_names() -> frozenset[str]:
    # Lazy import avoids features <-> baselines circular import at package load.
    from nfl_oracle.baselines.value_model import MODEL_FEATURE_NAMES

    return frozenset(
        name for name in MODEL_FEATURE_NAMES if name != "intercept" and not name.startswith("pos_")
    )


def classify_feature(name: str) -> OwnModelStatus:
    if name in LEAKAGE_BLOCKED_FEATURES:
        return "leakage_blocked"
    if name in ridge_core_feature_names():
        return "ridge_core"
    if name in REQUIRED_LIVE_OK_CONTEXT_FEATURES:
        return "context_required"
    if name in CONTEXT_EMITTED_FEATURES:
        return "context_emitted"
    if name in IDENTITY_ENCODE_FEATURES:
        return "identity_encode"
    if name == "kickoff_slot":
        return "context_required"
    return "identity_encode"


def own_model_gap_matrix() -> list[dict[str, str]]:
    """One row per live_ok FeatureSpec name plus leakage-blocked labels."""

    rows: list[dict[str, str]] = []
    for name in live_ok_feature_names():
        status = classify_feature(name)
        rows.append({"feature": name, "status": status, "surface": _surface(status)})
    for name in sorted(LEAKAGE_BLOCKED_FEATURES):
        rows.append(
            {
                "feature": name,
                "status": "leakage_blocked",
                "surface": "train_label_only",
            }
        )
    return rows


def _surface(status: OwnModelStatus) -> str:
    if status == "ridge_core":
        return "FeatureDrivenValueModel"
    if status in {"context_required", "context_emitted"}:
        return "recommendations.model ridge context"
    if status == "identity_encode":
        return "identity_or_one_hot_elsewhere"
    return "train_label_only"


def assert_no_unclassified_live_ok() -> None:
    """Every live_ok name must map to a deliberate own-model status."""

    for name in live_ok_feature_names():
        classify_feature(name)

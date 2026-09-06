"""FeatureSpec v1 — availability clocks + train/live flags."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from nfl_oracle.labels.schema import LIVE_FEATURE_BLACKLIST

DType = Literal["float", "int", "str", "bool", "categorical"]


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    dtype: DType
    train_ok: bool
    live_ok: bool
    availability_rule: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def feature_registry() -> tuple[FeatureSpec, ...]:
    """Small honest registry — placeholders until denser Corpus G priors land."""

    return (
        FeatureSpec(
            name="season",
            dtype="int",
            train_ok=True,
            live_ok=True,
            availability_rule="known_at_slate_construction",
            description="NFL season year for the game/slate.",
        ),
        FeatureSpec(
            name="player_prior_mean",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule="fit_on_seasons_strictly_earlier_than_decision_season",
            description="Walk-forward player mean prior; falls back to position/global.",
        ),
        FeatureSpec(
            name="position_prior_mean",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule="fit_on_seasons_strictly_earlier_than_decision_season",
            description="Walk-forward position mean Real value prior.",
        ),
        FeatureSpec(
            name="global_prior_mean",
            dtype="float",
            train_ok=True,
            live_ok=True,
            availability_rule="fit_on_seasons_strictly_earlier_than_decision_season",
            description="Walk-forward global mean Real value prior.",
        ),
        FeatureSpec(
            name="same_slate_final_value",
            dtype="float",
            train_ok=True,
            live_ok=False,
            availability_rule="post_finalization_label_only",
            description="Realized Real value — train label; live forbidden.",
        ),
    )


def features_document() -> dict[str, Any]:
    specs = feature_registry()
    return {
        "name": "nfl_feature_schema",
        "version": 1,
        "features": [s.to_dict() for s in specs],
        "live_blacklist": list(LIVE_FEATURE_BLACKLIST),
        "observation_only": True,
    }


def live_ok_feature_names() -> tuple[str, ...]:
    """Names marked live_ok and not on the same-slate blacklist."""

    return tuple(
        spec.name
        for spec in feature_registry()
        if spec.live_ok and spec.name not in LIVE_FEATURE_BLACKLIST
    )

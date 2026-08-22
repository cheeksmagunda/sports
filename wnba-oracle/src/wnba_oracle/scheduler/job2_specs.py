"""Call-compatible exports for the historical Job 2 prediction module."""

from __future__ import annotations

from typing import Any

from wnba_oracle.common.settings import Settings
from wnba_oracle.modeling.artifact import PickerArtifactLike
from wnba_oracle.modeling.policy import ModelPolicy
from wnba_oracle.modeling.prediction import (
    ANCHOR_MIN_GAMES,
    ANCHOR_MIN_MINUTES,
    PlayerPredictions,
    _compute_popularity_scores,
    attach_archetypes,
)
from wnba_oracle.modeling.prediction import materialize_specs as _materialize_specs
from wnba_oracle.modeling.prediction import predict_players as _predict_players
from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.sample import PlayerSamplingSpec


def _policy(settings: Settings) -> ModelPolicy:
    from wnba_oracle.scheduler.job2 import build_model_policy

    return build_model_policy(settings)


def predict_players(
    enrichment: list[dict],
    *,
    settings: Settings,
    art: PickerArtifactLike | None,
    head_predictions: dict[int, dict[str, float]],
    player_history: dict[int, float] | None,
    bonus: dict[int, float],
) -> PlayerPredictions:
    """Preserve the former ``settings=`` API while using the pure kernel."""
    return _predict_players(
        enrichment,
        policy=_policy(settings),
        art=art,
        head_predictions=head_predictions,
        player_history=player_history,
        bonus=bonus,
    )


def materialize_specs(
    adjusted: dict[int, float],
    *,
    preds: PlayerPredictions,
    settings: Settings,
    measured_drafts: dict[int, int],
    label_names: dict[int, str],
    K: float,
    volatility: dict[int, float],
) -> tuple[list[PlayerSamplingSpec], list[FieldPlayerSpec], dict[int, dict[str, Any]]]:
    """Preserve the former ``settings=`` materialization API."""
    return _materialize_specs(
        adjusted,
        preds=preds,
        policy=_policy(settings),
        measured_drafts=measured_drafts,
        label_names=label_names,
        K=K,
        volatility=volatility,
    )


__all__ = [
    "ANCHOR_MIN_GAMES",
    "ANCHOR_MIN_MINUTES",
    "PlayerPredictions",
    "_compute_popularity_scores",
    "attach_archetypes",
    "materialize_specs",
    "predict_players",
]

"""Map leakage-safe feature value model outputs into shadow value maps.

Observation only: produces ``values_by_player`` for shadow scoring / ranking.
Does not submit contests or call Real Sports.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from nfl_oracle.baselines.value_model import FeatureDrivenValueModel, fit_feature_value_model
from nfl_oracle.labels.schema import ValueLabel
from nfl_oracle.strategy.schema import FiveCardAction
from nfl_oracle.strategy.scoring import ShadowScore, shadow_weighted_score


def predict_values_by_player(
    train_labels: Sequence[ValueLabel],
    players: Sequence[tuple[int, str]],
    *,
    decision_season: int,
    team_ids: dict[int, int] | None = None,
    alpha: float = 1.0,
) -> dict[int, float]:
    """Fit on seasons strictly earlier than ``decision_season``; predict player values."""

    train = [row for row in train_labels if row.season < decision_season]
    model = fit_feature_value_model(train, alpha=alpha)
    return values_from_model(model, players, decision_season=decision_season, team_ids=team_ids)


def values_from_model(
    model: FeatureDrivenValueModel,
    players: Sequence[tuple[int, str]],
    *,
    decision_season: int,
    team_ids: dict[int, int] | None = None,
) -> dict[int, float]:
    """Predict a player_id -> value map using an already-fit model."""

    teams = team_ids or {}
    labels = [
        ValueLabel(
            player_id=pid,
            game_id=0,
            season=decision_season,
            position=position,
            value=0.0,
            team_id=teams.get(pid),
        )
        for pid, position in players
    ]
    preds = model.predict(labels)
    return {pid: float(pred) for (pid, _), pred in zip(players, preds, strict=True)}


def shadow_score_with_feature_model(
    action: FiveCardAction,
    train_labels: Sequence[ValueLabel],
    player_positions: dict[int, str],
    *,
    decision_season: int,
    team_ids: dict[int, int] | None = None,
    alpha: float = 1.0,
) -> tuple[ShadowScore, dict[int, float]]:
    """Convenience: feature-model values → shadow weighted score."""

    players = [(pid, player_positions[pid]) for pid in action.player_ids if pid in player_positions]
    missing = [pid for pid in action.player_ids if pid not in player_positions]
    values = predict_values_by_player(
        train_labels,
        players,
        decision_season=decision_season,
        team_ids=team_ids,
        alpha=alpha,
    )
    for pid in missing:
        values.setdefault(pid, 0.0)
    return shadow_weighted_score(action, values), values


def value_model_strategy_note() -> dict[str, Any]:
    return {
        "method": "feature_ridge",
        "optional": True,
        "default_offline_path": "mean_median_baselines",
        "shadow_flag": "use_feature_value_model",
        "shadow_flag_default": False,
        "leakage_rule": "train seasons strictly earlier than decision_season",
        "observation_only": True,
        "contest_entry": False,
    }


def resolve_shadow_values(
    *,
    player_ids: Sequence[int],
    values_by_player: dict[int, float] | None,
    use_feature_value_model: bool = False,
    player_positions: dict[int, str] | None = None,
    decision_season: int | None = None,
    train_labels: Sequence[ValueLabel] | None = None,
    team_ids: dict[int, int] | None = None,
    alpha: float = 1.0,
) -> tuple[dict[int, float], dict[str, Any]]:
    """Resolve values for shadow preview / rank-orderings.

    Default path (``use_feature_value_model=False``) is offline-safe: callers
    must supply ``values_by_player`` explicitly. Opting into
    ``feature_ridge`` requires positions, decision_season, and train labels
    from earlier seasons only.
    """

    explicit = dict(values_by_player or {})
    meta: dict[str, Any] = {
        "use_feature_value_model": use_feature_value_model,
        "value_source": "explicit",
        "contest_entry": False,
        "observation_only": True,
    }
    if not use_feature_value_model:
        meta.update(value_model_strategy_note())
        meta["value_source"] = "explicit"
        meta["default_offline_safe"] = True
        return explicit, meta

    if decision_season is None:
        raise ValueError("decision_season_required_for_feature_value_model")
    positions = player_positions or {}
    missing_pos = [pid for pid in player_ids if pid not in positions]
    if missing_pos:
        raise ValueError(f"player_positions_required_for_ids:{missing_pos}")
    if not train_labels:
        raise ValueError("train_labels_required_for_feature_value_model")

    players = [(pid, positions[pid]) for pid in player_ids]
    predicted = predict_values_by_player(
        train_labels,
        players,
        decision_season=decision_season,
        team_ids=team_ids,
        alpha=alpha,
    )
    # Explicit map wins on overlap (operator override); predicted fills gaps.
    merged = dict(predicted)
    merged.update(explicit)
    meta.update(value_model_strategy_note())
    meta["value_source"] = "feature_ridge"
    meta["decision_season"] = decision_season
    meta["n_train_labels"] = sum(1 for row in train_labels if row.season < decision_season)
    meta["default_offline_safe"] = False
    meta["alpha"] = alpha
    return merged, meta

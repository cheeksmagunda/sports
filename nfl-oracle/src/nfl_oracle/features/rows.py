"""Build observation-only feature rows from walk-forward priors."""

from __future__ import annotations

from typing import Any

from nfl_oracle.baselines.player_priors import (
    PlayerPrior,
    fit_player_means,
    predict_player_prior,
)
from nfl_oracle.labels.schema import ValueLabel


def prior_feature_row(
    *,
    player_id: int,
    position: str,
    season: int,
    prior: PlayerPrior,
    week: int | None = None,
) -> dict[str, Any]:
    """One live-safe prior feature row (no same-slate finals)."""

    row: dict[str, Any] = {
        "player_id": player_id,
        "position": position,
        "season": season,
        "player_prior_mean": prior.mean_value,
        "prior_fallback": prior.fallback,
        "prior_fallback_level": prior.fallback,
        "prior_n_games": prior.n_games,
        "same_slate_final_value": None,  # never populate for live/shadow
        "live_ok": True,
        "contest_entry": False,
    }
    if week is not None:
        row["week"] = week
    return row


def build_prior_rows_for_players(
    *,
    train_labels: list[ValueLabel],
    players: list[tuple[int, str]],
    decision_season: int,
    week: int | None = None,
    min_games: int = 1,
) -> list[dict[str, Any]]:
    """Fit priors on labels with season < decision_season; emit live-ok rows."""

    train = [lab for lab in train_labels if lab.season < decision_season]
    player_mean, pos_mean, global_mean = fit_player_means(train)
    player_n: dict[int, int] = {}
    for lab in train:
        player_n[lab.player_id] = player_n.get(lab.player_id, 0) + 1

    rows: list[dict[str, Any]] = []
    for player_id, position in players:
        prior = predict_player_prior(
            player_id=player_id,
            position=position,
            player_mean=player_mean,
            pos_mean=pos_mean,
            global_mean=global_mean,
            min_games=min_games,
            player_n=player_n,
        )
        rows.append(
            prior_feature_row(
                player_id=player_id,
                position=position,
                season=decision_season,
                prior=prior,
                week=week,
            )
        )
    return rows

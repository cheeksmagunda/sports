"""Player priors + shadow scoring scaffolds."""

from __future__ import annotations

from nfl_oracle.baselines.player_priors import fit_player_means, predict_player_prior
from nfl_oracle.labels.schema import ValueLabel
from nfl_oracle.strategy.schema import FiveCardAction
from nfl_oracle.strategy.scoring import shadow_weighted_score


def _lab(pid: int, season: int, pos: str, value: float) -> ValueLabel:
    return ValueLabel(
        player_id=pid,
        game_id=season * 1000 + pid,
        season=season,
        position=pos,
        value=value,
    )


def test_player_prior_falls_back_to_position() -> None:
    train = [
        _lab(1, 2022, "QB", 10.0),
        _lab(1, 2022, "QB", 14.0),
        _lab(2, 2022, "RB", 8.0),
    ]
    player_mean, pos_mean, global_mean = fit_player_means(train)
    assert player_mean[1] == 12.0
    known = predict_player_prior(
        player_id=1,
        position="QB",
        player_mean=player_mean,
        pos_mean=pos_mean,
        global_mean=global_mean,
        player_n={1: 2},
    )
    assert known.fallback == "player"
    unknown = predict_player_prior(
        player_id=99,
        position="QB",
        player_mean=player_mean,
        pos_mean=pos_mean,
        global_mean=global_mean,
    )
    assert unknown.fallback == "position"
    assert unknown.mean_value == 12.0


def test_shadow_weighted_score() -> None:
    action = FiveCardAction(player_ids=(1, 2, 3, 4, 5), slot_multipliers=(3, 2, 1, 1, 1))
    score = shadow_weighted_score(action, {1: 10.0, 2: 5.0, 3: 4.0, 4: 3.0, 5: 2.0})
    assert score.structural_ok
    assert score.total == 3 * 10 + 2 * 5 + 4 + 3 + 2

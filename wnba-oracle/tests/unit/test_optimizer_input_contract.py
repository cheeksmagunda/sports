"""The optimizer's two player views form one ID-keyed model contract."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.optimize import OptimizeConfig, optimize_lineup
from wnba_oracle.picker.payout import default_curve_for_regime
from wnba_oracle.picker.sample import PlayerSamplingSpec


def _specs() -> tuple[list[PlayerSamplingSpec], list[FieldPlayerSpec]]:
    sampling: list[PlayerSamplingSpec] = []
    field: list[FieldPlayerSpec] = []
    for offset in range(8):
        player_id = 100 + offset
        team = "LVA" if offset % 2 == 0 else "NYL"
        opponent = "NYL" if team == "LVA" else "LVA"
        boost = float(offset % 4) / 2.0
        score = 2.5 + offset / 10.0
        sampling.append(
            PlayerSamplingSpec(
                player_id=player_id,
                team=team,
                opponent=opponent,
                mu=float(np.log(score + 2.0)),
                sigma=0.2,
                boost=boost,
            )
        )
        field.append(
            FieldPlayerSpec(
                player_id=player_id,
                pred_real_score=score,
                card_boost=boost,
            )
        )
    return sampling, field


def _optimize(sampling: list[PlayerSamplingSpec], field: list[FieldPlayerSpec]):
    return optimize_lineup(
        sampling,
        field,
        default_curve_for_regime("top_20"),
        cfg=OptimizeConfig(
            top_n_filter=8,
            n_samples=160,
            n_field_lineups=30,
            seed=73,
            max_per_team=5,
            dynamic_team_cap=False,
        ),
    )


def test_optimizer_aligns_independently_ordered_specs_by_player_id() -> None:
    sampling, field = _specs()
    expected = _optimize(sampling, field)

    assert _optimize(sampling, list(reversed(field))) == expected


@pytest.mark.parametrize("side", ["sampling", "field"])
def test_optimizer_rejects_duplicate_player_ids(side: str) -> None:
    sampling, field = _specs()
    if side == "sampling":
        sampling[-1] = replace(sampling[-1], player_id=sampling[0].player_id)
    else:
        field[-1] = replace(field[-1], player_id=field[0].player_id)

    with pytest.raises(ValueError, match=f"duplicate {side} player_id"):
        _optimize(sampling, field)


def test_optimizer_rejects_mismatched_player_id_sets() -> None:
    sampling, field = _specs()
    field[-1] = replace(field[-1], player_id=999)

    with pytest.raises(ValueError, match="sampling/field player_id mismatch"):
        _optimize(sampling, field)


def test_optimizer_rejects_mismatched_boost_views() -> None:
    sampling, field = _specs()
    field[-1] = replace(field[-1], card_boost=99.0)

    with pytest.raises(ValueError, match="boost mismatch"):
        _optimize(sampling, field)

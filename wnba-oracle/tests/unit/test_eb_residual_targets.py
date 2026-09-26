"""EB residual target wiring (#350)."""

from __future__ import annotations

import polars as pl

from wnba_oracle.features.game_features import TARGET_COLUMNS, add_targets
from wnba_oracle.train.eb_baseline import EBHierarchicalBaseline, attach_eb_residual_targets
from wnba_oracle.train.pipeline import train_picker


def _labeled_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "player_id": [1, 1, 2],
            "position": ["F", "F", "F"],
            "real_score": [10.0, 12.0, 8.0],
            "game_date": ["2026-08-01", "2026-08-02", "2026-08-01"],
            "team_pace": [95.0, 96.0, 94.0],
            "mins_l5": [20.0, 21.0, 18.0],
            "mins_l10": [19.0, 20.0, 17.0],
        }
    )


def test_add_targets_includes_real_score_residual_column() -> None:
    logs = pl.DataFrame(
        {
            "game_date": ["2026-08-01"],
            "player_id": [1],
            "season": "2026",
            "min": 30.0,
            "pts": 15.0,
            "reb": 6.0,
            "oreb": 2.0,
            "dreb": 4.0,
            "ast": 4.0,
            "stl": 1.0,
            "blk": 1.0,
            "tov": 2.0,
            "fgm": 6.0,
            "fga": 12.0,
            "fg3m": 1.0,
            "ftm": 2.0,
            "fta": 3.0,
        }
    )
    df = add_targets(logs)
    assert "real_score_residual" in df.columns
    assert df.get_column("real_score_residual").null_count() == len(df)
    for col in TARGET_COLUMNS:
        assert col in df.columns


def test_attach_eb_residual_targets_matches_predict() -> None:
    df = _labeled_frame().with_columns(pl.lit("F").alias("cohort"))
    eb = EBHierarchicalBaseline()
    eb.fit(df, target="real_score")
    out = attach_eb_residual_targets(df, eb)
    preds = eb.predict(out)
    observed = out.get_column("real_score").to_numpy()
    residual = out.get_column("real_score_residual").to_numpy()
    assert abs(residual - (observed - preds)).max() < 1e-9


def test_train_picker_trains_real_score_residual_head() -> None:
    import test_model_validity_audit as audit

    train_df, valid_df = audit._tiny_train_valid_frames()
    art = train_picker(train_df, valid_df)
    assert ("real_score_residual", "F") in art.heads
    assert art.eb_baseline is not None

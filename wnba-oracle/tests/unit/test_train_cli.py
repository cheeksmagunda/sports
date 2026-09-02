from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from wnba_oracle.train.cli import _load_gamelog_corpus, _write_metrics


def test_write_metrics_honors_explicit_destination(tmp_path: Path) -> None:
    destination = tmp_path / "metrics.json"

    written = _write_metrics({"training_rows": 12}, str(destination))

    assert written == destination
    assert json.loads(destination.read_text()) == {"training_rows": 12}


def test_write_metrics_uses_unique_temporary_destination() -> None:
    first = _write_metrics({"run": 1}, None)
    second = _write_metrics({"run": 2}, None)
    try:
        assert first != second
        assert first.name.startswith("wnba_train_metrics_")
        assert json.loads(first.read_text()) == {"run": 1}
        assert json.loads(second.read_text()) == {"run": 2}
    finally:
        first.unlink(missing_ok=True)
        second.unlink(missing_ok=True)


def test_prepared_heads_corpus_is_loaded_without_rebuilding(tmp_path: Path) -> None:
    destination = tmp_path / "heads.parquet"
    expected = {"game_date": ["2026-08-20"], "minutes_played": [30.0]}
    pl.DataFrame(expected).write_parquet(destination)

    loaded = _load_gamelog_corpus(None, str(destination))

    assert loaded.to_dict(as_series=False) == expected


def test_train_picker_refit_full_flag() -> None:
    from wnba_oracle.train.pipeline import train_picker

    # Dummy small frames with required player_id column
    df_train = pl.DataFrame(
        {
            "player_id": [1, 2],
            "position": ["F", "G"],
            "real_score": [10.0, 20.0],
            "game_date": ["2026-08-01", "2026-08-02"],
        }
    )
    df_valid = pl.DataFrame(
        {
            "player_id": [1],
            "position": ["F"],
            "real_score": [15.0],
            "game_date": ["2026-08-03"],
        }
    )

    art_default = train_picker(df_train, df_valid, refit_full=False)
    assert art_default.refit_full is False
    assert art_default.calibrators_consumed_at_serving is False

    art_refit = train_picker(df_train, df_valid, refit_full=True)
    assert art_refit.refit_full is True
    assert art_refit.calibrators_consumed_at_serving is False

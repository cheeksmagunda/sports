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

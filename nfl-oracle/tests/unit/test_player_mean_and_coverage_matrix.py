"""player_mean baseline + coverage matrix document helpers."""

from __future__ import annotations

import json
from pathlib import Path

from nfl_oracle.baselines.cli import main as baselines_main
from nfl_oracle.baselines.priors import HistoricalPriorBaseline
from nfl_oracle.data.coverage_matrix import (
    CoverageMatrixDocument,
    load_coverage_matrix_doc,
    save_coverage_matrix_doc,
)
from nfl_oracle.labels.schema import ValueLabel


def _lab(pid: int, season: int, pos: str, value: float) -> ValueLabel:
    return ValueLabel(
        player_id=pid,
        game_id=season * 1000 + pid,
        season=season,
        position=pos,
        value=value,
    )


def test_player_mean_prefers_player_then_position() -> None:
    train = [_lab(1, 2022, "QB", 10.0), _lab(1, 2022, "QB", 14.0), _lab(2, 2022, "RB", 8.0)]
    model = HistoricalPriorBaseline(kind="player_mean").fit(train)
    assert model.predict_one("QB", 1) == 12.0
    assert model.predict_one("QB", 99) == 12.0  # position fallback
    assert model.predict_one("TE", 99) == model.global_prior


def test_cli_methods_player_mean(capsys) -> None:
    root = Path(__file__).resolve().parents[1] / "fixtures" / "value_labels"
    code = baselines_main(["--root", str(root), "--methods", "player_mean", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "player_mean" in payload["methods"]
    assert "player_mean" in payload["report"]["pooled"]


def test_coverage_matrix_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "coverage_matrix.json"
    doc = CoverageMatrixDocument(
        generated_at="2026-09-06T00:00:00+00:00",
        seasons={
            "2024": {"status": "known", "games": {"1001": {"game_id": 1001}}, "value_note": "ok"}
        },
        gaps=[],
    )
    save_coverage_matrix_doc(doc, path)
    loaded = load_coverage_matrix_doc(path)
    rows = loaded.season_rows()
    assert len(rows) == 1
    assert rows[0].season == 2024
    assert rows[0].status == "known"
    assert rows[0].game_ids == (1001,)

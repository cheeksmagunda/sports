"""Tests for offline walk-forward eval report (baselines vs feature_ridge)."""

from __future__ import annotations

import json
from pathlib import Path

from nfl_oracle.baselines.eval_cli import main as eval_main
from nfl_oracle.baselines.eval_report import (
    COMPARISON_METHODS,
    build_eval_report,
    render_markdown,
    write_eval_report,
)
from nfl_oracle.labels import load_labels_from_corpus_root

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "value_labels"


def _labels():
    return load_labels_from_corpus_root(FIXTURE_ROOT)


def test_build_eval_report_ranks_baselines_and_feature_ridge() -> None:
    report = build_eval_report(
        _labels(),
        methods=COMPARISON_METHODS,
        root=FIXTURE_ROOT,
        fixture_mode=True,
    )
    assert report.fixture_mode is True
    assert report.report.n_labels == 21
    assert set(report.methods) == set(COMPARISON_METHODS)
    kinds = [row.kind for row in report.ranking_by_mae]
    assert "feature_ridge" in kinds
    assert "global_mean" in kinds
    assert "position_mean" in kinds
    # Ranking is sorted by MAE ascending when present.
    maes = [row.mae for row in report.ranking_by_mae if row.mae is not None]
    assert maes == sorted(maes)
    payload = report.to_dict()
    assert payload["observation_only"] is True
    assert payload["contest_entry"] is False
    assert payload["mode"] == "walk_forward_eval"
    assert "feature_ridge" in payload["walk_forward"]["pooled"]
    cmp_ = payload["feature_ridge_vs_best_baseline"]
    assert cmp_["feature_ridge_present"] is True
    assert cmp_["best_baseline"] in set(COMPARISON_METHODS) - {"feature_ridge"}
    assert isinstance(cmp_["delta_mae"], float)


def test_render_markdown_contains_table() -> None:
    report = build_eval_report(_labels(), root=FIXTURE_ROOT, fixture_mode=True)
    md = render_markdown(report)
    assert "# Walk-forward evaluation report" in md
    assert "`feature_ridge`" in md
    assert "feature_ridge vs best baseline" in md
    assert "no contest entry" in md.lower()


def test_write_eval_report_creates_json_and_md(tmp_path: Path) -> None:
    report = build_eval_report(_labels(), root=FIXTURE_ROOT, fixture_mode=True)
    paths = write_eval_report(report, tmp_path, stem="unit_eval", also_latest=True)
    assert paths.json_path.is_file()
    assert paths.md_path.is_file()
    assert paths.latest_json is not None and paths.latest_json.is_file()
    assert paths.latest_md is not None and paths.latest_md.is_file()
    payload = json.loads(paths.json_path.read_text(encoding="utf-8"))
    assert payload["contest_entry"] is False
    assert payload["n_labels"] == 21
    assert "feature_ridge" in payload["methods"]


def test_eval_cli_writes_fixture_report(tmp_path: Path, capsys) -> None:
    code = eval_main(
        [
            "--root",
            str(FIXTURE_ROOT),
            "--out-dir",
            str(tmp_path),
            "--stem",
            "cli_eval",
            "--no-latest",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "observation only" in out
    json_path = tmp_path / "cli_eval.json"
    md_path = tmp_path / "cli_eval.md"
    assert json_path.is_file()
    assert md_path.is_file()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["fixture_mode"] is True
    assert payload["contest_entry"] is False
    assert set(payload["methods"]) == set(COMPARISON_METHODS)


def test_eval_cli_methods_subset(tmp_path: Path) -> None:
    code = eval_main(
        [
            "--root",
            str(FIXTURE_ROOT),
            "--out-dir",
            str(tmp_path),
            "--stem",
            "subset",
            "--methods",
            "global_mean",
            "feature_ridge",
            "--no-latest",
        ]
    )
    assert code == 0
    payload = json.loads((tmp_path / "subset.json").read_text(encoding="utf-8"))
    assert payload["methods"] == ["global_mean", "feature_ridge"]
    assert payload["feature_ridge_vs_best_baseline"]["best_baseline"] == "global_mean"

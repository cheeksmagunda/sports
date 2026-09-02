from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "model_tournament.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("model_tournament", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_row(
    slate_date: str, *, score: float, payout: float, placement: int | None
) -> dict[str, Any]:
    return {
        "slate_date": slate_date,
        "player_ids": [1, 2, 3, 4, 5],
        "committed_order_score": score,
        "our_score": score,
        "placement": placement,
        "placement_lower_bound": placement if placement is not None else 21,
        "censored": placement is None,
        "field_size": 100,
        "captured_depth": 20,
        "gap": 5.0,
        "payout": payout,
        "payout_capture": payout / 10.0,
        "top_k_player_capture": {
            "5": {
                "hits": 3,
                "requested_k": 5,
                "available_players": 50,
                "reference_size": 5,
                "boundary_tie_expanded": False,
            },
            "8": {
                "hits": 4,
                "requested_k": 8,
                "available_players": 50,
                "reference_size": 8,
                "boundary_tie_expanded": False,
            },
            "10": {
                "hits": 5,
                "requested_k": 10,
                "available_players": 50,
                "reference_size": 10,
                "boundary_tie_expanded": False,
            },
        },
        "beat_median": 1,
    }


def test_tournament_computes_real_paired_metrics(tmp_path: Path, monkeypatch) -> None:
    """Exercises the harness's own comparison/sign-test/bootstrap/report
    logic against synthetic but internally consistent per-slate rows,
    without requiring a live DATABASE_URL or a real trained artifact --
    those are stubbed at run_variant, the boundary between this script's
    logic and the expensive DB+optimizer replay build_model_research_benchmark.py
    performs."""
    module = _load_module()

    baseline_rows = [
        _fake_row(f"2026-06-0{i}", score=10.0, payout=1.0, placement=5) for i in range(1, 5)
    ]
    # Challenger beats baseline on every paired slate: a real sign test should
    # therefore report a small (significant) p-value, not a placeholder.
    challenger_rows = [
        _fake_row(f"2026-06-0{i}", score=12.0, payout=1.5, placement=3) for i in range(1, 5)
    ]

    def fake_run_variant(name, artifact_path, **kwargs):
        rows = baseline_rows if name == "baseline" else challenger_rows
        return {
            "name": name,
            "artifact_path": str(artifact_path),
            "artifact_feature_module_sha": "deadbeef",
            "artifact_training_rows": 1234,
            "n_eligible_slates": len(rows),
            "drop_reasons": {"too_few_scored_labels": 0},
            "n_optimizer_error": 0,
            "n_optimizer_infeasible": 0,
            "summary": module.benchmark.summarize_variant(rows),
            "slates": rows,
        }

    monkeypatch.setattr(module, "run_variant", fake_run_variant)
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake/for-test-gate-only")

    out = tmp_path / "results"
    monkeypatch.setattr(
        "sys.argv",
        [
            "model_tournament.py",
            "--output-dir",
            str(out),
            "--baseline-artifact",
            str(tmp_path / "baseline.pkl"),
            "--challenger-artifacts",
            str(tmp_path / "challenger.pkl"),
        ],
    )

    assert module.main() == 0
    payload = json.loads((out / "tournament_results.json").read_text())

    assert len(payload["variants"]) == 2
    assert payload["variants"][0]["name"] == "baseline"
    assert payload["variants"][1]["name"] == "challenger_1"

    assert len(payload["comparisons"]) == 1
    comparison = payload["comparisons"][0]
    assert comparison["n_common_slates"] == 4

    # Real metrics, not boilerplate: challenger wins every paired slate on
    # score and payout, and the sign test / bootstrap CI reflect that.
    score = comparison["committed_order_score"]
    assert score["wins"] == 4
    assert score["losses"] == 0
    assert score["mean_delta"] == 2.0
    assert score["sign_test_p_value"] is not None
    assert score["sign_test_p_value"] < 0.2
    ci = score["bootstrap_ci_mean_delta"]
    assert ci is not None
    assert ci["ci_low"] <= ci["mean"] <= ci["ci_high"]
    assert ci["mean"] == 2.0

    payout = comparison["payout"]
    assert payout["wins"] == 4
    assert payout["mean_delta"] == 0.5

    placement = comparison["placement"]
    assert placement["wins"] == 4  # lower placement number is better
    assert placement["n_exact_pairs"] == 4

    top10 = payload["variants"][0]["summary"]["top_k_player_capture"]["10"]
    assert top10["hit_distribution"]["5"] == 4  # all 4 baseline rows hit 5/5

    report = (out / "TOURNAMENT_REPORT.md").read_text()
    assert "Model Tournament Report" in report
    assert "challenger_1 vs baseline" in report
    assert "boilerplate" not in report.lower()


def test_sign_test_and_bootstrap_are_real_statistics() -> None:
    module = _load_module()

    # All-wins should be far more significant than a near-even split.
    assert module.sign_test_p_value(10, 0) < 0.01
    assert module.sign_test_p_value(6, 4) > 0.5
    assert module.sign_test_p_value(0, 0) is None

    ci = module.bootstrap_ci_mean([1.0, 2.0, 3.0, 4.0, 5.0], n_boot=500, seed=1)
    assert ci is not None
    assert ci["mean"] == 3.0
    assert ci["ci_low"] < 3.0 < ci["ci_high"]
    assert module.bootstrap_ci_mean([]) is None


def test_missing_database_url_fails_closed_without_csvs(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    out = tmp_path / "results"
    monkeypatch.setattr(
        "sys.argv",
        [
            "model_tournament.py",
            "--output-dir",
            str(out),
            "--baseline-artifact",
            str(tmp_path / "baseline.pkl"),
        ],
    )
    assert module.main() == 2
    assert not (out / "tournament_results.json").exists()

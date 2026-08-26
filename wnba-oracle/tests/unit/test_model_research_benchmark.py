"""Pure helper tests for the model research benchmark script."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import pathlib
import sys
from types import ModuleType

import pytest

SCRIPT = (
    pathlib.Path(__file__).resolve().parents[2] / "scripts" / "build_model_research_benchmark.py"
)


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_model_research_benchmark", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod() -> ModuleType:
    return _load_script()


@dataclasses.dataclass
class _Spec:
    player_id: int
    sigma: float


class TestTemperatureValues:
    def test_zero_and_negative_are_empty(self, mod):
        assert mod.temperature_values(0) == []
        assert mod.temperature_values(-3) == []

    def test_single_variant_is_production_scale(self, mod):
        assert mod.temperature_values(1) == [1.0]

    def test_deterministic_monotonic_span(self, mod):
        vals = mod.temperature_values(4)
        assert vals == mod.temperature_values(4)
        assert vals == sorted(vals)
        assert vals[0] == pytest.approx(0.7)
        assert vals[-1] == pytest.approx(1.5)


class TestVariantGrid:
    def test_baseline_first_then_knobs_then_temps(self, mod):
        grid = mod.build_variant_grid(2)
        names = [v["name"] for v in grid]
        assert names[0] == "baseline"
        assert grid[0]["overrides"] == {}
        assert grid[0]["sigma_scale"] == 1.0
        knob_names = [n for n in names if n.startswith("knob:")]
        temp_names = [n for n in names if n.startswith("temp:")]
        assert set(knob_names) == set(mod.KNOB_ABLATIONS)
        assert len(temp_names) == 2
        assert len(grid) == 1 + len(mod.KNOB_ABLATIONS) + 2

    def test_each_ablation_flips_exactly_one_knob(self, mod):
        for overrides in mod.KNOB_ABLATIONS.values():
            assert len(overrides) == 1
            (key,) = overrides
            assert key in mod.BASELINE_OVERRIDES
            assert overrides[key] != mod.BASELINE_OVERRIDES[key]


class TestScaleSigma:
    def test_identity_scale_returns_equal_specs(self, mod):
        specs = [_Spec(1, 0.25), _Spec(2, 0.4)]
        out = mod.scale_sigma(specs, 1.0)
        assert out == specs
        assert out is not specs

    def test_scaling_does_not_mutate_input(self, mod):
        specs = [_Spec(1, 0.25), _Spec(2, 0.4)]
        out = mod.scale_sigma(specs, 2.0)
        assert [s.sigma for s in out] == [0.5, 0.8]
        assert [s.sigma for s in specs] == [0.25, 0.4]


class TestScoring:
    def test_score_lineup_orders_by_realized_score(self, mod):
        # Best realized score takes the 2.0x slot; boosts add to the slot.
        rs = {1: 10.0, 2: 5.0}
        boost = {1: 0.5, 2: 0.0}
        got = mod.score_lineup([2, 1], boost, rs)
        assert got == pytest.approx((2.0 + 0.5) * 10.0 + 1.8 * 5.0)

    def test_score_lineup_missing_player_scores_zero(self, mod):
        assert mod.score_lineup([99], {}, {}) == 0.0

    def test_placement_is_one_based(self, mod):
        lb = [50.0, 40.0, 30.0]
        assert mod.placement_for_score(60.0, lb) == 1
        assert mod.placement_for_score(45.0, lb) == 2
        assert mod.placement_for_score(30.0, lb) == 3  # ties do not outrank us
        assert mod.placement_for_score(1.0, lb) == 4


class TestSummarize:
    def test_empty_rows(self, mod):
        assert mod.summarize_variant([]) == {"n_slates": 0}

    def test_metrics(self, mod):
        rows = [
            {"placement": 1, "gap": 0.0, "beat_median": 1, "payout_capture": 1.0},
            {"placement": 5, "gap": 2.0, "beat_median": 1, "payout_capture": 0.5},
            {"placement": 30, "gap": 8.0, "beat_median": 0, "payout_capture": 0.0},
        ]
        s = mod.summarize_variant(rows)
        assert s["n_slates"] == 3
        assert s["beat_median_pct"] == pytest.approx(66.7)
        assert s["top5_pct"] == pytest.approx(66.7)
        assert s["top1_pct"] == pytest.approx(33.3)
        assert s["mean_placement"] == pytest.approx(12.0)
        assert s["mean_gap_vs_top1"] == pytest.approx(3.333)
        assert s["mean_payout_capture"] == pytest.approx(0.5)


class TestRenderMarkdown:
    def _result(self, mod):
        rows = [{"placement": 1, "gap": 0.0, "beat_median": 1, "payout_capture": 1.0}]
        return {
            "meta": {
                "generated_at": "2026-08-26T00:00:00+00:00",
                "seed": 2026,
                "n_samples": 80,
                "n_slates": 1,
                "temperature_variants": 1,
            },
            "variants": [
                {"name": "baseline", "summary": mod.summarize_variant(rows)},
                {"name": "temp:sigma_x1.5", "summary": {"n_slates": 0}},
            ],
        }

    def test_contains_header_and_rows(self, mod):
        text = mod.render_markdown(self._result(mod))
        assert text.startswith("# Model research benchmark")
        assert "| baseline | 1 |" in text
        assert "| temp:sigma_x1.5 | 0 | - |" in text
        assert "generated artifact" in text


class TestAtomicWrite:
    def test_writes_content_and_creates_parents(self, mod, tmp_path):
        target = tmp_path / "nested" / "out.md"
        mod.atomic_write_text(target, "hello")
        assert target.read_text(encoding="utf-8") == "hello"

    def test_replaces_existing_and_leaves_no_temp_files(self, mod, tmp_path):
        target = tmp_path / "out.json"
        mod.atomic_write_text(target, json.dumps({"a": 1}))
        mod.atomic_write_text(target, json.dumps({"a": 2}))
        assert json.loads(target.read_text(encoding="utf-8")) == {"a": 2}
        assert [p.name for p in tmp_path.iterdir()] == ["out.json"]

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


class TestSelectShard:
    def test_partition_is_exact_and_disjoint(self, mod):
        items = [f"2026-06-{i:02d}" for i in range(1, 11)]
        shards = [mod.select_shard(items, i, 3) for i in range(3)]
        flat = sorted(x for s in shards for x in s)
        assert flat == sorted(items)
        assert all(len(set(a) & set(b)) == 0 for a in shards for b in shards if a is not b)

    def test_single_shard_is_identity(self, mod):
        assert mod.select_shard([1, 2, 3], 0, 1) == [1, 2, 3]

    def test_invalid_shard_raises(self, mod):
        with pytest.raises(ValueError, match="shard index"):
            mod.select_shard([1], 2, 2)
        with pytest.raises(ValueError, match="shard index"):
            mod.select_shard([1], 0, 0)


class TestCsvLoading:
    def test_labels_csv_casts_float_drafts(self, mod, tmp_path):
        p = tmp_path / "slate_labels.csv"
        p.write_text(
            "contest_id,slate_date,section,platform_player_id,display_name,"
            "team_key,card_boost,drafts,real_score,ingested_at\n"
            "1,2026-06-01,main,10,A Player,MIN,0.5,91.0,12.5,2026-06-02\n"
            "1,2026-06-01,main,11,B Player,LVA,0.0,,3.0,2026-06-02\n"
        )
        sl = mod.load_labels_csv(p)
        assert sl["drafts"].to_list() == [91, None]
        assert sl["slate_date"].to_list() == ["2026-06-01", "2026-06-01"]

    def test_leaderboards_csv_renames_lineup(self, mod, tmp_path):
        p = tmp_path / "contest_leaderboards.csv"
        p.write_text(
            "contest_id,slate_date,entry_id,rank,paged_rank,user_id,score,"
            "lineup,num_brawlers,ingested_at\n"
            '1,2026-06-01,5,1,1,u1,99.5,"[]",5,2026-06-02\n'
        )
        lb = mod.load_leaderboards_csv(p)
        assert "lineup_json" in lb.columns
        assert lb["score"].to_list() == [99.5]

    def test_drafts_by_slate_takes_max_and_skips_null(self, mod, tmp_path):
        p = tmp_path / "slate_labels.csv"
        p.write_text(
            "contest_id,slate_date,section,platform_player_id,display_name,"
            "team_key,card_boost,drafts,real_score,ingested_at\n"
            "1,2026-06-01,main,10,A,MIN,0.5,7.0,1.0,x\n"
            "2,2026-06-01,alt,10,A,MIN,0.5,9.0,1.0,x\n"
            "1,2026-06-01,main,11,B,LVA,0.0,,1.0,x\n"
            "1,2026-06-02,main,12,C,NYL,0.0,3.0,1.0,x\n"
        )
        out = mod.drafts_by_slate(mod.load_labels_csv(p))
        assert out == {"2026-06-01": {10: 9}, "2026-06-02": {12: 3}}


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

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
        from wnba_oracle.picker.optimize import OptimizeConfig

        valid_fields = {f.name for f in dataclasses.fields(OptimizeConfig)}
        for overrides in mod.KNOB_ABLATIONS.values():
            assert len(overrides) == 1
            (key,) = overrides
            assert key in valid_fields


class TestExtraVariants:
    def test_parses_multi_knob_bundle_with_coercion(self, mod):
        variant = mod.parse_extra_variant(
            "bundle:leverage_weight=0.2,duplication_aware_payout=True,top_n_filter=20"
        )
        assert variant["name"] == "bundle"
        assert variant["overrides"] == {
            "leverage_weight": 0.2,
            "duplication_aware_payout": True,
            "top_n_filter": 20,
        }

    def test_coerces_scientific_notation_as_float(self, mod):
        variant = mod.parse_extra_variant("bundle:leverage_weight=1e-3")
        assert variant["overrides"] == {"leverage_weight": pytest.approx(0.001)}

    def test_rejects_malformed_specs(self, mod):
        with pytest.raises(ValueError, match="name:key=value"):
            mod.parse_extra_variant("no_colon_here")
        with pytest.raises(ValueError, match="bad override pair"):
            mod.parse_extra_variant("x:leverage_weight")
        with pytest.raises(ValueError, match="no overrides"):
            mod.parse_extra_variant("x:")
        with pytest.raises(ValueError, match="empty value"):
            mod.parse_extra_variant("x:leverage_weight=")

    def test_rejects_duplicate_keys_and_names(self, mod):
        with pytest.raises(ValueError, match="repeats override key"):
            mod.parse_extra_variant("x:leverage_weight=0.2,leverage_weight=0.3")
        grid = mod.build_variant_grid(0)
        with pytest.raises(ValueError, match="collides"):
            mod.extend_grid_with_extras(grid, ["baseline:leverage_weight=0.1"])
        with pytest.raises(ValueError, match="collides"):
            mod.extend_grid_with_extras(grid, ["sweep:a=1", "sweep:a=2"])

    def test_resolve_validates_and_filters_extras(self, mod):
        out = mod.resolve_variant_grid(
            n_temperature_variants=0,
            extra_specs=["bundle:leverage_weight=0.2"],
            variant_names=["bundle"],
        )
        assert [variant["name"] for variant in out] == ["bundle"]
        with pytest.raises(ValueError, match="unknown OptimizeConfig"):
            mod.resolve_variant_grid(
                n_temperature_variants=0,
                extra_specs=["bad:not_an_optimize_field=1"],
            )
        with pytest.raises(ValueError, match="unknown variant"):
            mod.resolve_variant_grid(
                n_temperature_variants=0,
                extra_specs=["bundle:leverage_weight=0.2"],
                variant_names=["missing"],
            )


class TestProductionEnvOverrides:
    def test_translates_every_expected_prod_config_key_to_its_alias(self, mod):
        from wnba_oracle.common.settings import EXPECTED_PROD_CONFIG, Settings

        out = mod.production_env_overrides()
        assert len(out) == len(EXPECTED_PROD_CONFIG)
        for name, value in EXPECTED_PROD_CONFIG.items():
            alias = str(Settings.model_fields[name].alias)
            assert alias in out
            if value is True:
                assert out[alias] == "true"
            elif value is False:
                assert out[alias] == "false"
            else:
                assert out[alias] == str(value)


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
    def test_score_lineup_uses_committed_order_not_realized_score(self, mod):
        # Player 2 is committed to the 2.0x slot even though player 1 realizes
        # the higher score -- no hindsight re-sort by outcome.
        rs = {1: 10.0, 2: 5.0}
        boost = {1: 0.5, 2: 0.0}
        got = mod.score_lineup([2, 1], [2.0, 1.8], boost, rs)
        assert got == pytest.approx(5.0 * 2.0 + 10.0 * (1.8 + 0.5))

    def test_score_lineup_missing_player_scores_zero(self, mod):
        assert mod.score_lineup([99], [2.0], {}, {}) == 0.0

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
            {
                "placement": 1,
                "placement_lower_bound": 1,
                "censored": False,
                "gap": 0.0,
                "beat_median": 1,
                "payout_capture": 1.0,
            },
            {
                "placement": 5,
                "placement_lower_bound": 5,
                "censored": False,
                "gap": 2.0,
                "beat_median": 1,
                "payout_capture": 0.5,
            },
            {
                # Right-censored: score never reached the captured leaderboard
                # depth, so the exact placement is unknown -- only a lower
                # bound, and it never enters beat_median (median unobserved).
                "placement": None,
                "placement_lower_bound": 21,
                "censored": True,
                "gap": 8.0,
                "payout_capture": 0.0,
            },
        ]
        s = mod.summarize_variant(rows)
        assert s["n_slates"] == 3
        assert s["n_censored"] == 1
        assert s["top20_pct"] == pytest.approx(66.7)
        assert s["top5_pct"] == pytest.approx(66.7)
        assert s["top1_pct"] == pytest.approx(33.3)
        assert s["mean_gap_vs_top1"] == pytest.approx(3.333)
        assert s["mean_payout_capture"] == pytest.approx(0.5)
        assert s["beat_median_pct"] == pytest.approx(100.0)
        assert s["n_median_observed"] == 2

    def test_beat_median_omitted_when_never_observed(self, mod):
        rows = [
            {
                "placement": None,
                "placement_lower_bound": 21,
                "censored": True,
                "gap": 8.0,
                "payout_capture": 0.0,
            }
        ]
        s = mod.summarize_variant(rows)
        assert "beat_median_pct" not in s


class TestRenderMarkdown:
    def _result(self, mod):
        rows = [
            {
                "placement": 1,
                "placement_lower_bound": 1,
                "censored": False,
                "gap": 0.0,
                "beat_median": 1,
                "payout_capture": 1.0,
            }
        ]
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

    def test_game_identity_csv_indexes_per_player_with_game_id(self, mod, tmp_path):
        p = tmp_path / "game_identity.csv"
        p.write_text(
            "slate_date,real_sports_player_id,team,opponent,game_id\n"
            "2026-06-01,10,MIN,LVA,g1\n"
            "2026-06-01,11,LVA,MIN,g1\n"
            "2026-06-02,12,NYL,CHI,\n"
        )
        by_slate = mod.index_game_identity(mod.load_game_identity_csv(p))
        assert by_slate == {
            "2026-06-01": {
                10: {"team": "MIN", "opponent": "LVA", "game_id": "g1"},
                11: {"team": "LVA", "opponent": "MIN", "game_id": "g1"},
            },
            "2026-06-02": {12: {"team": "NYL", "opponent": "CHI", "game_id": ""}},
        }

    def test_game_identity_keeps_first_row_on_duplicate_player(self, mod, tmp_path):
        # A conflicting re-capture must not be resolved silently by row order.
        p = tmp_path / "game_identity.csv"
        p.write_text(
            "slate_date,real_sports_player_id,team,opponent,game_id\n"
            "2026-06-01,10,MIN,LVA,g1\n"
            "2026-06-01,10,MIN,NYL,g2\n"
        )
        by_slate = mod.index_game_identity(mod.load_game_identity_csv(p))
        assert by_slate["2026-06-01"][10]["opponent"] == "LVA"

    def test_game_identity_skips_rows_without_a_player_id(self, mod, tmp_path):
        p = tmp_path / "game_identity.csv"
        p.write_text(
            "slate_date,real_sports_player_id,team,opponent,game_id\n"
            "2026-06-01,,MIN,LVA,g1\n"
            "2026-06-01,11,LVA,MIN,g1\n"
        )
        by_slate = mod.index_game_identity(mod.load_game_identity_csv(p))
        assert list(by_slate["2026-06-01"]) == [11]


class TestCoverageNote:
    def test_states_the_denominator_when_slates_were_dropped(self, mod):
        note = mod._coverage_note(
            {"n_slates": 35, "drop_reasons": {"no_identity_rows": 22, "too_few_specs": 0}}
        )
        assert "35 slates benchmarked, 22 dropped" in note
        assert "no_identity_rows=22" in note
        assert "too_few_specs" not in note  # zero-count reasons stay out of the note

    def test_flags_a_degraded_game_identity_path(self, mod):
        note = mod._coverage_note(
            {"n_slates": 10, "game_key_method": {"provider_game_id": 8, "incomplete": 2}}
        )
        assert "provider_game_id` on 8 slate(s)" in note
        assert "degraded identity path" in note

    def test_shouts_when_shards_are_missing(self, mod):
        note = mod._coverage_note({"n_slates": 10, "shards_missing": [3, 7]})
        assert "INCOMPLETE" in note
        assert "[3, 7]" in note


class TestMergeShards:
    def _shard(self, mod, variant_name, slates):
        rows = [
            {
                "slate_date": sd,
                "our_score": 10.0,
                "placement": p,
                "placement_lower_bound": p,
                "censored": False,
                "field_size": 20,
                "captured_depth": 20,
                "gap": 1.0,
                "beat_median": 1,
                "payout": 1.0,
                "payout_capture": 0.5,
            }
            for sd, p in slates
        ]
        return {
            "meta": {
                "generated_at": "x",
                "seed": 2026,
                "n_samples": 3500,
                "n_slates": len(rows),
                "n_slates_dropped_no_identity": 0,
                "temperature_variants": 4,
                "shard_index": 0,
                "shard_count": 2,
            },
            "variants": [
                {
                    "name": variant_name,
                    "overrides": {},
                    "sigma_scale": 1.0,
                    "n_optimizer_error": 0,
                    "n_optimizer_infeasible": 0,
                    "summary": mod.summarize_variant(rows),
                    "slates": rows,
                }
            ],
        }

    def test_merge_unions_slates_and_recomputes(self, mod):
        s0 = self._shard(mod, "baseline", [("2026-06-01", 1), ("2026-06-03", 3)])
        s1 = self._shard(mod, "baseline", [("2026-06-02", 5)])
        merged = mod.merge_shard_results([s0, s1])
        assert merged["meta"]["n_slates"] == 3
        assert merged["meta"]["merged_shards"] == 2
        v = merged["variants"][0]
        assert [r["slate_date"] for r in v["slates"]] == [
            "2026-06-01",
            "2026-06-02",
            "2026-06-03",
        ]
        assert v["summary"]["n_slates"] == 3
        assert v["summary"]["top5_pct"] == pytest.approx(100.0)

    def test_duplicate_slates_dedupe(self, mod):
        s0 = self._shard(mod, "baseline", [("2026-06-01", 1)])
        merged = mod.merge_shard_results([s0, s0])
        assert merged["variants"][0]["summary"]["n_slates"] == 1

    def test_drop_reasons_sum_across_shards(self, mod):
        s0 = self._shard(mod, "baseline", [("2026-06-01", 1)])
        s0["meta"]["drop_reasons"] = {"no_identity_rows": 2, "too_few_specs": 1}
        s1 = self._shard(mod, "baseline", [("2026-06-02", 5)])
        s1["meta"]["drop_reasons"] = {"no_identity_rows": 3}
        merged = mod.merge_shard_results([s0, s1])
        assert merged["meta"]["drop_reasons"] == {"no_identity_rows": 5, "too_few_specs": 1}

    def test_merge_records_which_shards_contributed(self, mod):
        s0 = self._shard(mod, "baseline", [("2026-06-01", 1)])
        s0["meta"]["shard_index"], s0["meta"]["shard_count"] = 0, 3
        s2 = self._shard(mod, "baseline", [("2026-06-03", 2)])
        s2["meta"]["shard_index"], s2["meta"]["shard_count"] = 2, 3
        merged = mod.merge_shard_results([s0, s2])
        # Shard 1 never reported: the artifact must say so rather than read as complete.
        assert merged["meta"]["shards_contributed"] == [0, 2]
        assert merged["meta"]["shards_missing"] == [1]
        assert merged["meta"]["complete"] is False
        assert "INCOMPLETE" in mod.render_markdown(merged)

    def test_merge_marks_a_full_shard_set_complete(self, mod):
        shards = []
        for i in range(2):
            s = self._shard(mod, "baseline", [(f"2026-06-0{i + 1}", 1)])
            s["meta"]["shard_index"], s["meta"]["shard_count"] = i, 2
            shards.append(s)
        merged = mod.merge_shard_results(shards)
        assert merged["meta"]["shards_missing"] == []
        assert merged["meta"]["complete"] is True
        assert "INCOMPLETE" not in mod.render_markdown(merged)

    def test_optimizer_error_and_infeasible_counts_sum_per_variant(self, mod):
        s0 = self._shard(mod, "baseline", [("2026-06-01", 1)])
        s0["variants"][0]["n_optimizer_error"] = 2
        s0["variants"][0]["n_optimizer_infeasible"] = 1
        s1 = self._shard(mod, "baseline", [("2026-06-02", 5)])
        s1["variants"][0]["n_optimizer_error"] = 3
        s1["variants"][0]["n_optimizer_infeasible"] = 4
        merged = mod.merge_shard_results([s0, s1])
        v = merged["variants"][0]
        assert v["n_optimizer_error"] == 5
        assert v["n_optimizer_infeasible"] == 5

    def test_empty_raises(self, mod):
        with pytest.raises(ValueError, match="no shard results"):
            mod.merge_shard_results([])


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

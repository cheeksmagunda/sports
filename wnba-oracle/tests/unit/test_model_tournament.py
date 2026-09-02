from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

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

    # Challenger genuinely diverges on every slate here, so no false-tie
    # warning should fire.
    assert payload["identical_predictions_warning"] is False

    report = (out / "TOURNAMENT_REPORT.md").read_text()
    assert "Model Tournament Report" in report
    assert "challenger_1 vs baseline" in report
    assert "boilerplate" not in report.lower()
    assert "WARNING" not in report


def test_identical_predictions_warning_flags_all_tied_slates() -> None:
    module = _load_module()

    tied_comparison = [
        {
            "challenger": "challenger_1",
            "baseline": "baseline",
            "slates": [
                {"slate_date": "2026-06-01", "committed_order_score_delta": 0.0},
                {"slate_date": "2026-06-02", "committed_order_score_delta": 0.0},
            ],
        }
    ]
    assert module.identical_predictions_warning(tied_comparison) is True

    mixed_comparison = [
        {
            "challenger": "challenger_1",
            "baseline": "baseline",
            "slates": [
                {"slate_date": "2026-06-01", "committed_order_score_delta": 0.0},
                {"slate_date": "2026-06-02", "committed_order_score_delta": 2.5},
            ],
        }
    ]
    assert module.identical_predictions_warning(mixed_comparison) is False

    assert module.identical_predictions_warning([]) is False
    assert module.identical_predictions_warning([{"slates": []}]) is False


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


_POOL_PLAYER_IDS = (10, 11, 12, 13, 14, 15)


class _FakeArtifact:
    """Minimal duck-typed stand-in for a trained ``PickerArtifact``.

    ``model_tournament.py``'s offline CSV corpus (``_precompute_slates``)
    builds ``enrichment`` rows with no ``head_features``, so
    ``job2_model._predict_heads_for_pool`` always returns ``{}`` in this
    harness regardless of which artifact is loaded (the D63/D69 head tier
    only ever fires against live ``job1_enrichment`` feature rows). The next
    tier down the prediction ladder, the EB baseline
    (``modeling.artifact.eb_predict_one``), IS driven by
    ``artifact.eb_baseline`` and is exactly as artifact-specific -- so this
    fake carries a distinct ``eb_baseline`` per instance to prove the same
    ``job2._load_model_artifact`` swap this harness performs actually
    changes which model answers the per-player prediction, end to end
    through ``precompute_pool_for_artifact`` and ``_run_variant``.
    """

    def __init__(self, prediction: float) -> None:
        self.heads: dict[Any, Any] = {}
        self.feature_module_sha = f"fake-{prediction}"
        self.training_rows = 1
        self.eb_baseline = SimpleNamespace(
            cohort_means={"F": prediction},
            player_alpha=dict.fromkeys(_POOL_PLAYER_IDS, 0.0),
        )

    def predict_real_score(self, frame: Any) -> dict[str, np.ndarray] | None:
        return None


def _write_divergence_csv_fixtures(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A single slate, 6 players split across two teams -- enough for
    ``_build_specs`` to produce >=5 sampling specs and for the optimizer to
    have a real choice to make."""
    labels = tmp_path / "slate_labels.csv"
    leaderboards = tmp_path / "contest_leaderboards.csv"
    identity = tmp_path / "game_identity.csv"

    label_rows = [
        "1,2026-06-01,main,10,Player Ten,MIN,0.1,50.0,8.0,2026-06-02",
        "1,2026-06-01,main,11,Player Eleven,MIN,0.1,50.0,9.0,2026-06-02",
        "1,2026-06-01,main,12,Player Twelve,MIN,0.1,50.0,10.0,2026-06-02",
        "1,2026-06-01,main,13,Player Thirteen,LVA,0.1,50.0,11.0,2026-06-02",
        "1,2026-06-01,main,14,Player Fourteen,LVA,0.1,50.0,12.0,2026-06-02",
        "1,2026-06-01,main,15,Player Fifteen,LVA,0.1,50.0,13.0,2026-06-02",
    ]
    labels.write_text(
        "contest_id,slate_date,section,platform_player_id,display_name,"
        "team_key,card_boost,drafts,real_score,ingested_at\n" + "\n".join(label_rows) + "\n"
    )

    lb_rows = [
        f"1,2026-06-01,{100 + i},{i},{i},u{i},{60.0 - i},[],20,2026-06-02" for i in range(1, 6)
    ]
    leaderboards.write_text(
        "contest_id,slate_date,entry_id,rank,paged_rank,user_id,score,"
        "lineup,num_brawlers,ingested_at\n" + "\n".join(lb_rows) + "\n"
    )

    id_rows = [
        "2026-06-01,10,MIN,LVA,g1",
        "2026-06-01,11,MIN,LVA,g1",
        "2026-06-01,12,MIN,LVA,g1",
        "2026-06-01,13,LVA,MIN,g1",
        "2026-06-01,14,LVA,MIN,g1",
        "2026-06-01,15,LVA,MIN,g1",
    ]
    identity.write_text(
        "slate_date,real_sports_player_id,team,opponent,game_id\n" + "\n".join(id_rows) + "\n"
    )
    return labels, leaderboards, identity


def test_artifact_swap_produces_divergent_predictions(tmp_path: Path, monkeypatch) -> None:
    """Regression test for the real artifact-swap mechanism.

    Unlike ``test_tournament_computes_real_paired_metrics`` (which
    monkeypatches ``run_variant`` itself and never touches the artifact
    swap), this drives two genuinely different fake ``PickerArtifact``
    objects through the REAL ``precompute_pool_for_artifact`` -> ``_build_specs``
    -> ``job2_model._predict_heads_for_pool`` -> ``_run_variant`` path,
    exactly as ``run_variant`` composes them (minus the disk load of the
    .pkl, which is a separate, already-covered concern). If the
    ``job2._load_model_artifact`` monkeypatch in ``precompute_pool_for_artifact``
    were broken -- e.g. patched the wrong module reference, or leaked the
    same artifact into both variants -- this test would see byte-identical
    predicted scores across every paired slate and fail.
    """
    module = _load_module()
    # Offline CSV mode: no DATABASE_URL at all (a set-but-unreachable URL
    # still gets dialed by best-effort DB lookups like slate label names).
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("PAYOUT_REGIME", "top_20")
    monkeypatch.setenv("OPTIMIZER_MAX_PER_TEAM", "2")
    monkeypatch.setenv("FIELD_MEASURED_OWNERSHIP_ENABLED", "true")
    for alias, value in module.benchmark.production_env_overrides().items():
        monkeypatch.setenv(alias, value)

    from wnba_oracle.common.settings import get_settings
    from wnba_oracle.scheduler.job2 import build_model_policy

    policy = build_model_policy(get_settings())

    labels_csv, leaderboards_csv, game_identity_csv = _write_divergence_csv_fixtures(tmp_path)

    baseline_art = _FakeArtifact(prediction=10.0)
    challenger_art = _FakeArtifact(prediction=40.0)

    kwargs = {
        "max_slates": None,
        "labels_csv": labels_csv,
        "leaderboards_csv": leaderboards_csv,
        "game_identity_csv": game_identity_csv,
        "policy": policy,
    }
    baseline_pool, baseline_drops = module.precompute_pool_for_artifact(baseline_art, **kwargs)
    challenger_pool, challenger_drops = module.precompute_pool_for_artifact(
        challenger_art, **kwargs
    )

    assert baseline_pool, f"no eligible slates in baseline pool (drops={baseline_drops})"
    assert challenger_pool, f"no eligible slates in challenger pool (drops={challenger_drops})"
    assert set(baseline_pool) == set(challenger_pool)

    # The swap must actually change which model answered the per-player
    # prediction: the projected real_score for each player must differ
    # between pools (this is what would silently converge if both variants
    # fell through to the same heuristic).
    for sd in baseline_pool:
        base_rs = baseline_pool[sd]["rs_by"]
        chal_rs = challenger_pool[sd]["rs_by"]
        # rs_by carries the ACTUAL labeled real_score (ground truth), which
        # is identical for both pools by construction -- the divergence we
        # care about lives in the sampling specs (what each artifact
        # predicted), not the labels.
        assert base_rs == chal_rs
        base_specs = {s.player_id: s.mu for s in baseline_pool[sd]["samps"]}
        chal_specs = {s.player_id: s.mu for s in challenger_pool[sd]["samps"]}
        assert set(base_specs) == set(chal_specs)
        assert base_specs != chal_specs, (
            "baseline and challenger artifacts produced byte-identical "
            "sampling means -- the artifact swap did not take effect"
        )

    baseline_rows, _, _ = module.benchmark._run_variant(
        {"name": "baseline", "overrides": {}, "sigma_scale": 1.0},
        baseline_pool,
        80,
        policy.optimizer,
    )
    challenger_rows, _, _ = module.benchmark._run_variant(
        {"name": "challenger_1", "overrides": {}, "sigma_scale": 1.0},
        challenger_pool,
        80,
        policy.optimizer,
    )
    assert baseline_rows and challenger_rows
    base_scores = {r["slate_date"]: r["committed_order_score"] for r in baseline_rows}
    chal_scores = {r["slate_date"]: r["committed_order_score"] for r in challenger_rows}
    assert set(base_scores) == set(chal_scores)
    assert base_scores != chal_scores, (
        "baseline and challenger produced byte-identical committed_order_score "
        "across every paired slate -- indistinguishable from a broken "
        "artifact swap silently converging on the same heuristic fallback"
    )


def _write_game_logs_csv_fixture(tmp_path: Path) -> Path:
    """A minimal ``wnba_game_logs`` export (see scripts/export_game_logs.py)
    giving each of the six divergence-fixture players one game strictly
    before the 2026-06-01 slate date, so ``build_rolling_features`` produces
    a non-null ``mins_l5`` for every one of them (one prior game is enough --
    the rolling window means over whatever history exists, see rolling.py).
    Team/opponent match ``_write_divergence_csv_fixtures`` so the name+team
    join key (``features.serving_features._key``) actually matches.
    """
    path = tmp_path / "game_logs.csv"
    header = (
        "game_date,player_id,player_name,first_initial,last_name,team,opponent,"
        "home_away,game_id,min,season,pts,reb,oreb,dreb,ast,stl,blk,tov,fgm,fga,"
        "fg3m,ftm,fta\n"
    )
    players = [
        (9010, "Player Ten", "P", "Ten", "MIN", "LVA"),
        (9011, "Player Eleven", "P", "Eleven", "MIN", "LVA"),
        (9012, "Player Twelve", "P", "Twelve", "MIN", "LVA"),
        (9013, "Player Thirteen", "P", "Thirteen", "LVA", "MIN"),
        (9014, "Player Fourteen", "P", "Fourteen", "LVA", "MIN"),
        (9015, "Player Fifteen", "P", "Fifteen", "LVA", "MIN"),
    ]
    rows = [
        f"2026-05-25,{pid},{name},{initial},{last},{team},{opp},home,g0,"
        f"20.0,2026,10.0,4.0,1.0,3.0,2.0,1.0,0.0,1.0,4.0,8.0,1.0,2.0,2.0"
        for pid, name, initial, last, team, opp in players
    ]
    path.write_text(header + "\n".join(rows) + "\n")
    return path


def test_offline_head_features_drive_genuine_divergence(tmp_path: Path, monkeypatch) -> None:
    """Regression test for #53's root cause fix.

    Unlike ``test_artifact_swap_produces_divergent_predictions`` (which uses
    ``_FakeArtifact.heads == {}`` on purpose and proves divergence through
    the artifact-independent-in-name-only ``eb_baseline`` tier, per its own
    docstring), this test proves the D69/Phase-2b HEADS tier itself --
    ``job2_model._predict_heads_for_pool`` reading ``art.heads`` -- actually
    fires through the offline benchmark path once ``--game-logs-csv`` is
    given. Before the #53 fix, ``_precompute_slates`` never put
    ``head_features`` into ``enrichment``, so ``_predict_heads_for_pool``
    always returned ``{}`` regardless of what ``art.heads`` contained, and
    two artifacts with genuinely different trained heads were
    indistinguishable through this path. This test would fail on the
    pre-fix code: ``captured`` would show ``n == 0`` for every call.
    """
    module = _load_module()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("PAYOUT_REGIME", "top_20")
    monkeypatch.setenv("OPTIMIZER_MAX_PER_TEAM", "2")
    monkeypatch.setenv("FIELD_MEASURED_OWNERSHIP_ENABLED", "true")
    for alias, value in module.benchmark.production_env_overrides().items():
        monkeypatch.setenv(alias, value)

    from wnba_oracle.common.settings import get_settings
    from wnba_oracle.scheduler.job2 import build_model_policy

    policy = build_model_policy(get_settings())

    labels_csv, leaderboards_csv, game_identity_csv = _write_divergence_csv_fixtures(tmp_path)
    game_logs_csv = _write_game_logs_csv_fixture(tmp_path)

    import wnba_oracle.scheduler.job2 as job2_mod
    from wnba_oracle.scheduler.job2_model import _predict_heads_for_pool as real_predict_heads

    captured: list[dict[str, Any]] = []

    def spy(art, enrichment):
        out = real_predict_heads(art, enrichment)
        captured.append({"weight": getattr(art, "_weight", None), "n": len(out)})
        return out

    monkeypatch.setattr(job2_mod, "_predict_heads_for_pool", spy)

    class _HeadsArtifact:
        """Duck-typed PickerArtifact with REAL (non-empty) heads, so
        job2_model._predict_heads_for_pool does not early-return {} the way
        test_artifact_swap_produces_divergent_predictions's ``_FakeArtifact``
        does. ``predict_real_score`` reads the ``mins_l5`` column that only
        ``head_features`` (built from the gamelog corpus) can populate --
        proving the prediction is driven by that feature row, not a
        static per-artifact constant.
        """

        def __init__(self, weight: float) -> None:
            self.heads = {
                ("minutes", "F"): SimpleNamespace(feature_columns=("mins_l5",)),
                ("real_score_per_min", "F"): SimpleNamespace(feature_columns=("mins_l5",)),
            }
            self.feature_module_sha = f"heads-{weight}"
            self.training_rows = 1
            self.eb_baseline = None
            self._weight = weight

        def predict_real_score(self, frame: Any) -> dict[str, np.ndarray] | None:
            mins = (
                frame["mins_l5"].to_numpy()
                if "mins_l5" in frame.columns
                else np.zeros(frame.height)
            )
            p50 = mins * self._weight
            return {"p10": p50 * 0.8, "p50": p50, "p90": p50 * 1.2}

    baseline_art = _HeadsArtifact(weight=0.5)
    challenger_art = _HeadsArtifact(weight=2.0)

    kwargs = {
        "max_slates": None,
        "labels_csv": labels_csv,
        "leaderboards_csv": leaderboards_csv,
        "game_identity_csv": game_identity_csv,
        "policy": policy,
        "game_logs_csv": game_logs_csv,
    }
    baseline_pool, baseline_drops = module.precompute_pool_for_artifact(baseline_art, **kwargs)
    challenger_pool, challenger_drops = module.precompute_pool_for_artifact(
        challenger_art, **kwargs
    )

    assert baseline_pool, f"no eligible slates in baseline pool (drops={baseline_drops})"
    assert challenger_pool, f"no eligible slates in challenger pool (drops={challenger_drops})"
    assert set(baseline_pool) == set(challenger_pool)

    # The heads tier must have actually run (non-empty predictions), not
    # merely been reachable in principle.
    assert captured, "job2_model._predict_heads_for_pool was never called"
    assert any(c["n"] > 0 for c in captured), (
        f"_predict_heads_for_pool always returned {{}} -- head_features never "
        f"reached art.heads (captured={captured})"
    )

    for sd in baseline_pool:
        base_specs = {s.player_id: s.mu for s in baseline_pool[sd]["samps"]}
        chal_specs = {s.player_id: s.mu for s in challenger_pool[sd]["samps"]}
        assert set(base_specs) == set(chal_specs)
        assert base_specs != chal_specs, (
            "baseline and challenger heads produced byte-identical sampling "
            "means through the offline benchmark path -- the heads tier did "
            "not genuinely fire on head_features"
        )


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

"""Model tournament: real paired comparison of trained picker artifacts.

Loads each of ``--baseline-artifact`` and ``--challenger-artifacts`` as an
actual ``PickerArtifact`` (via ``wnba_oracle.train.pipeline.load_artifact``),
replays the *same* production-identity slate pool through
``build_model_research_benchmark._build_specs`` once per artifact (swapping
only which trained model answers the per-player prediction, everything else
-- optimizer config, sampling seed, payout curve -- held fixed at the
compiled production policy), and reports honest paired metrics: top-5/8/10
player capture (including the full 0..5 hit distribution), committed-order
contest score and payout deltas, placement win/tie/loss with right-censoring,
a sign test on the paired win/loss record, and a percentile bootstrap CI on
the mean delta. This is a strict superset of what
``build_model_research_benchmark.py`` computes for a single policy: here the
*model* varies across variants, not the optimizer knobs.

Configuration is identical to ``build_model_research_benchmark.py``:
DATABASE_URL in the process environment, or --labels-csv/--leaderboards-csv/
--game-identity-csv pointing at a verified corpus-backup snapshot for offline
runs. Output files (tournament_results.json, TOURNAMENT_REPORT.md) are
written atomically into --output-dir.

Usage:
  DATABASE_URL=$DATABASE_PUBLIC_URL uv run python scripts/model_tournament.py \
      --output-dir ./tournament \
      --baseline-artifact models/picker_bf3c8996_1780752059.pkl \
      --challenger-artifacts models/picker_e2ced9ec_1780873338.pkl
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import math
import os
import random
import sys
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).resolve().with_name("build_model_research_benchmark.py")
spec = importlib.util.spec_from_file_location("build_model_research_benchmark", SCRIPT)
assert spec is not None
assert spec.loader is not None
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 2026


def load_variant_artifact(path: str) -> Any:
    """Load one trained PickerArtifact from an on-disk .pkl (+ .sha256
    sidecar, verified if present). Raises on a missing/corrupt/mistyped
    artifact -- a tournament comparing a model that failed to load would
    silently compare against nothing, which is worse than failing loudly."""
    from wnba_oracle.train.pipeline import load_artifact

    return load_artifact(Path(path))


def precompute_pool_for_artifact(
    art: Any,
    *,
    max_slates: int | None,
    labels_csv: Path | None,
    leaderboards_csv: Path | None,
    game_identity_csv: Path | None,
    policy: Any,
    game_logs_csv: Path | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """Build the per-slate optimizer inputs for one artifact.

    Monkeypatches ``job2._load_model_artifact`` for the duration of the call
    so ``_build_specs`` (invoked inside ``benchmark._precompute_slates``)
    predicts with THIS artifact regardless of ``policy.artifact_sha`` --
    the same function production's freeze path calls, just handed a
    tournament-selected model instead of resolving one by SHA off disk.
    """
    import wnba_oracle.scheduler.job2 as job2_mod

    original = job2_mod._load_model_artifact
    job2_mod._load_model_artifact = lambda _sha: art
    try:
        return benchmark._precompute_slates(
            max_slates,
            labels_csv,
            leaderboards_csv,
            game_identity_csv,
            policy=policy,
            game_logs_csv=game_logs_csv,
        )
    finally:
        job2_mod._load_model_artifact = original


def run_variant(
    name: str,
    artifact_path: str,
    *,
    n_samples: int,
    max_slates: int | None,
    labels_csv: Path | None,
    leaderboards_csv: Path | None,
    game_identity_csv: Path | None,
    policy: Any,
    game_logs_csv: Path | None = None,
) -> dict[str, Any]:
    """Load one artifact and replay the full eligible slate pool under it."""
    art = load_variant_artifact(artifact_path)
    precomputed, drops = precompute_pool_for_artifact(
        art,
        max_slates=max_slates,
        labels_csv=labels_csv,
        leaderboards_csv=leaderboards_csv,
        game_identity_csv=game_identity_csv,
        policy=policy,
        game_logs_csv=game_logs_csv,
    )
    rows, n_optimizer_error, n_optimizer_infeasible = benchmark._run_variant(
        {"name": name, "overrides": {}, "sigma_scale": 1.0},
        precomputed,
        n_samples,
        policy.optimizer,
    )
    return {
        "name": name,
        "artifact_path": str(artifact_path),
        "artifact_feature_module_sha": getattr(art, "feature_module_sha", None),
        "artifact_training_rows": getattr(art, "training_rows", None),
        "n_eligible_slates": len(precomputed),
        "drop_reasons": drops,
        "n_optimizer_error": n_optimizer_error,
        "n_optimizer_infeasible": n_optimizer_infeasible,
        "summary": benchmark.summarize_variant(rows),
        "slates": rows,
    }


def sign_test_p_value(wins: int, losses: int) -> float | None:
    """Two-sided exact binomial sign test over wins vs. losses (ties
    excluded), testing H0: challenger and baseline are equally likely to
    win a given slate. None when there is no decided pair to test."""
    n = wins + losses
    if n == 0:
        return None
    k = min(wins, losses)
    cumulative = sum(math.comb(n, i) for i in range(k + 1)) / (2**n)
    return round(min(1.0, 2.0 * cumulative), 6)


def bootstrap_ci_mean(
    deltas: list[float], *, n_boot: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED
) -> dict[str, Any] | None:
    """Percentile bootstrap 95% CI on the mean of paired deltas.
    Deterministic (seeded) so a rerun over the same corpus reproduces the
    same interval. None when there are no pairs to resample."""
    n = len(deltas)
    if n == 0:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(n_boot):
        resample = [deltas[rng.randrange(n)] for _ in range(n)]
        means.append(sum(resample) / n)
    means.sort()
    lo_idx = int(0.025 * n_boot)
    hi_idx = min(n_boot - 1, int(0.975 * n_boot))
    return {
        "mean": round(sum(deltas) / n, 4),
        "ci_low": round(means[lo_idx], 4),
        "ci_high": round(means[hi_idx], 4),
        "n_boot": n_boot,
        "n_pairs": n,
    }


def identical_predictions_warning(comparisons: list[dict[str, Any]]) -> bool:
    """True when a challenger's committed-order score is byte-identical to
    baseline's on every paired slate.

    A real challenger artifact can legitimately tie baseline occasionally,
    but tying on EVERY slate is far more consistent with a broken
    artifact-swap (e.g. both variants silently falling through to the same
    heuristic prediction, see job2_model._predict_heads_for_pool) than with
    a genuine no-difference result. This does not fail the tournament --
    it flags the result for a human to check the artifact-loading path
    rather than trust a "no difference" conclusion at face value.
    """
    for comparison in comparisons:
        slates = comparison.get("slates") or []
        if not slates:
            continue
        if all(s["committed_order_score_delta"] == 0.0 for s in slates):
            return True
    return False


def build_comparisons(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Paired baseline-vs-challenger comparisons with a sign test and
    bootstrap CI layered on top of ``build_model_research_benchmark``'s
    exact-pair win/tie/loss counts."""
    comparisons = benchmark.build_paired_comparisons(variants, baseline_name="baseline")
    for comparison in comparisons:
        score_deltas = [s["committed_order_score_delta"] for s in comparison["slates"]]
        payout_deltas = [s["payout_delta"] for s in comparison["slates"]]
        placement_deltas = [
            s["placement_delta"] for s in comparison["slates"] if s["placement_delta"] is not None
        ]
        comparison["committed_order_score"]["sign_test_p_value"] = sign_test_p_value(
            comparison["committed_order_score"]["wins"],
            comparison["committed_order_score"]["losses"],
        )
        comparison["committed_order_score"]["bootstrap_ci_mean_delta"] = bootstrap_ci_mean(
            score_deltas
        )
        comparison["payout"]["sign_test_p_value"] = sign_test_p_value(
            comparison["payout"]["wins"], comparison["payout"]["losses"]
        )
        comparison["payout"]["bootstrap_ci_mean_delta"] = bootstrap_ci_mean(payout_deltas)
        comparison["placement"]["sign_test_p_value"] = sign_test_p_value(
            comparison["placement"]["wins"], comparison["placement"]["losses"]
        )
        comparison["placement"]["bootstrap_ci_mean_delta"] = bootstrap_ci_mean(placement_deltas)
    return comparisons


def render_report(result: dict[str, Any]) -> str:
    """Render TOURNAMENT_REPORT.md from the actual computed result -- no
    boilerplate placeholder text."""
    meta = result["meta"]
    lines = [
        "# Model Tournament Report",
        "",
        f"Generated {meta['generated_at']} by `scripts/model_tournament.py`. "
        f"Seed {meta['seed']}, n_samples {meta['n_samples']}"
        + (", offline CSV corpus" if meta.get("offline_csv") else ", live DATABASE_URL corpus")
        + ".",
        "",
    ]
    if result.get("identical_predictions_warning"):
        lines.extend(
            [
                "**WARNING**: at least one challenger produced byte-identical "
                "committed-order scores to baseline on every paired slate. "
                "This can be a genuine tie, but is also the signature of a "
                "broken artifact swap (both variants silently falling "
                "through to the same heuristic prediction) -- verify the "
                "artifact-loading path before trusting this as a real "
                "no-difference result.",
                "",
            ]
        )
    lines.append(
        "| variant | artifact | eligible slates | dropped | top 20 | top 5 | top 1 "
        "| mean gap vs top 1 | payout capture |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for v in result["variants"]:
        s = v["summary"]
        dropped = sum(v.get("drop_reasons", {}).values())
        artifact_name = Path(v["artifact_path"]).name
        if s.get("n_slates", 0) == 0:
            lines.append(f"| {v['name']} | {artifact_name} | 0 | {dropped} | - | - | - | - | - |")
            continue
        lines.append(
            f"| {v['name']} | {artifact_name} | {s['n_slates']} | {dropped} "
            f"| {s['top20_pct']}% | {s['top5_pct']}% | {s['top1_pct']}% "
            f"| {s['mean_gap_vs_top1']} | {s['mean_payout_capture']} |"
        )
    capture_variants = [v for v in result["variants"] if v["summary"].get("top_k_player_capture")]
    if capture_variants:
        lines.extend(
            [
                "",
                "## Top-k player capture",
                "",
                "| variant | top5 mean hits | top5 0/1/2/3/4/5 distribution "
                "| top8 mean hits | top10 mean hits | top10 0/1/2/3/4/5 distribution |",
                "|---|---|---|---|---|---|",
            ]
        )
        for v in capture_variants:
            capture = v["summary"]["top_k_player_capture"]
            top5 = capture["5"]
            top10 = capture["10"]
            dist5 = "/".join(str(top5["hit_distribution"][str(h)]) for h in range(6))
            dist10 = "/".join(str(top10["hit_distribution"][str(h)]) for h in range(6))
            lines.append(
                f"| {v['name']} | {top5['mean_hits']} | {dist5} "
                f"| {capture['8']['mean_hits']} | {top10['mean_hits']} | {dist10} |"
            )
    if result.get("comparisons"):
        lines.extend(
            [
                "",
                "## Paired comparisons vs. baseline",
                "",
                "Placement W/T/L excludes any pair where either side's placement is "
                "right-censored (below the corpus's captured leaderboard depth). "
                "Sign test p-value is the two-sided exact binomial test on the "
                "decided (non-tied) pairs; bootstrap CI is a 2000-resample "
                "percentile 95% CI on the mean paired delta.",
                "",
                "| challenger vs baseline | paired slates | score W/T/L | score p "
                "| mean score delta (95% CI) | payout W/T/L | payout p "
                "| mean payout delta (95% CI) | placement exact/censored "
                "| placement W/T/L | placement p |",
                "|---|---|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for c in result["comparisons"]:
            score = c["committed_order_score"]
            payout = c["payout"]
            placement = c["placement"]
            score_ci = score.get("bootstrap_ci_mean_delta")
            payout_ci = payout.get("bootstrap_ci_mean_delta")
            score_ci_str = f"[{score_ci['ci_low']}, {score_ci['ci_high']}]" if score_ci else "-"
            payout_ci_str = f"[{payout_ci['ci_low']}, {payout_ci['ci_high']}]" if payout_ci else "-"
            lines.append(
                f"| {c['challenger']} vs {c['baseline']} | {c['n_common_slates']} "
                f"| {score['wins']}/{score['ties']}/{score['losses']} "
                f"| {score.get('sign_test_p_value')} "
                f"| {score['mean_delta']} {score_ci_str} "
                f"| {payout['wins']}/{payout['ties']}/{payout['losses']} "
                f"| {payout.get('sign_test_p_value')} "
                f"| {payout['mean_delta']} {payout_ci_str} "
                f"| {placement['n_exact_pairs']}/{placement['n_censored_pairs']} "
                f"| {placement['wins']}/{placement['ties']}/{placement['losses']} "
                f"| {placement.get('sign_test_p_value')} |"
            )
    else:
        lines.extend(["", "No challenger artifacts were compared."])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--labels-csv")
    parser.add_argument("--leaderboards-csv")
    parser.add_argument("--game-identity-csv")
    parser.add_argument(
        "--game-logs-csv",
        help=(
            "Offline wnba_game_logs export (scripts/export_game_logs.py). Without "
            "this, offline runs never populate head_features and every variant "
            "falls through to the artifact-independent eb_baseline tier (#53)."
        ),
    )
    parser.add_argument("--n-samples", type=int)
    parser.add_argument("--max-slates", type=int)
    parser.add_argument("--baseline-artifact", required=True)
    parser.add_argument("--challenger-artifacts", action="append", default=[])
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    labels_csv = Path(args.labels_csv) if args.labels_csv else None
    leaderboards_csv = Path(args.leaderboards_csv) if args.leaderboards_csv else None
    game_identity_csv = Path(args.game_identity_csv) if args.game_identity_csv else None
    game_logs_csv = Path(args.game_logs_csv) if args.game_logs_csv else None
    offline = labels_csv is not None and leaderboards_csv is not None
    if (labels_csv is None) != (leaderboards_csv is None):
        print("--labels-csv and --leaderboards-csv must be given together", file=sys.stderr)
        return 2
    if not offline and not os.environ.get("DATABASE_URL"):
        print(
            "DATABASE_URL is required in the process environment "
            "(or pass --labels-csv/--leaderboards-csv for offline mode)",
            file=sys.stderr,
        )
        return 2
    if offline and game_logs_csv is None:
        print(
            "WARNING: offline mode without --game-logs-csv; head_features will "
            "never be populated, so job2_model._predict_heads_for_pool always "
            "returns {} and every variant falls through to the "
            "artifact-independent eb_baseline tier -- baseline and challenger "
            "will be structurally incapable of diverging (#53).",
            file=sys.stderr,
        )

    os.environ.setdefault("PAYOUT_REGIME", "top_20")
    os.environ.setdefault("OPTIMIZER_MAX_PER_TEAM", "2")
    os.environ.setdefault("FIELD_MEASURED_OWNERSHIP_ENABLED", "true")
    for alias, value in benchmark.production_env_overrides().items():
        os.environ.setdefault(alias, value)

    from wnba_oracle.common.settings import get_settings
    from wnba_oracle.scheduler.job2 import build_model_policy

    policy = build_model_policy(get_settings())
    n_samples = args.n_samples or 80

    variant_specs: list[tuple[str, str]] = [("baseline", args.baseline_artifact)]
    variant_specs.extend(
        (f"challenger_{index}", path)
        for index, path in enumerate(args.challenger_artifacts, start=1)
    )

    variants: list[dict[str, Any]] = []
    for name, artifact_path in variant_specs:
        print(
            f"[{len(variants) + 1}/{len(variant_specs)}] {name}: {artifact_path}", file=sys.stderr
        )
        variants.append(
            run_variant(
                name,
                artifact_path,
                n_samples=n_samples,
                max_slates=args.max_slates,
                labels_csv=labels_csv,
                leaderboards_csv=leaderboards_csv,
                game_identity_csv=game_identity_csv,
                policy=policy,
                game_logs_csv=game_logs_csv,
            )
        )

    comparisons = build_comparisons(variants)
    identical_warning = identical_predictions_warning(comparisons)
    if identical_warning:
        print(
            "WARNING: at least one challenger produced byte-identical "
            "committed_order_score to baseline on every paired slate. This "
            "can be a genuine tie, but is also the signature of a broken "
            "artifact swap (both variants falling through to the same "
            "heuristic prediction) -- verify the artifact-loading path "
            "before trusting a no-difference conclusion.",
            file=sys.stderr,
        )
    result = {
        "meta": {
            "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
            "seed": benchmark.SEED,
            "n_samples": n_samples,
            "max_slates": args.max_slates,
            "offline_csv": offline,
            "baseline_artifact": args.baseline_artifact,
            "challenger_artifacts": list(args.challenger_artifacts),
        },
        "variants": variants,
        "comparisons": comparisons,
        "identical_predictions_warning": identical_warning,
    }

    benchmark.atomic_write_text(
        output_dir / "tournament_results.json", json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    benchmark.atomic_write_text(output_dir / "TOURNAMENT_REPORT.md", render_report(result))
    print(f"Wrote {output_dir / 'tournament_results.json'}")
    print(f"Wrote {output_dir / 'TOURNAMENT_REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

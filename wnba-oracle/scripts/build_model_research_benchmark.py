"""Model research benchmark: walk-forward variant sweep over stored slates.

Replays every 2026 slate that has labels, leaderboard data, and validated
game identity through the production optimizer, once per variant, and
records honest realized metrics against the real leaderboard (placement,
right-censored below the corpus's captured depth; gap to the winner; and
payout capture under the top-20 curve), player capture against the realized
top-5/top-8/top-10 pool, and paired slate comparisons against baseline. See
score_lineup, top_k_player_capture, summarize_variant, and
build_paired_comparisons.
Variants are:

  baseline     -- the compiled production policy (EXPECTED_PROD_CONFIG applied
                  over Settings, compiled the same way job2.build_model_policy
                  does -- see production_env_overrides)
  knob:*       -- one registered knob flipped away from production at a time,
                  so each row is a marginal ablation, not a confounded bundle
  temp:*       -- sampling-temperature variants: every player's log-space sigma
                  is scaled by a deterministic factor, sweeping how much
                  variance the copula sampler assumes

Like scripts/backtest_walkforward.py, predictions for each slate come only
from the production spec builder as of that slate, so results measure the live
path. Configuration comes from the process environment (DATABASE_URL is
required, or pass --labels-csv/--leaderboards-csv/--game-identity-csv
pointing at a verified corpus-backup / prefetch snapshot for offline runs);
no .env files are loaded. A slate whose teams lack validated reciprocal
opponent identity is dropped rather than assigned a fabricated opponent.
Output files are written atomically (temp file + os.replace) into
--output-dir:

  benchmark_results.json       -- per-variant per-slate rows plus summaries
  MODEL_RESEARCH_BENCHMARK.md  -- rendered summary table

Usage:
  DATABASE_URL=$DATABASE_PUBLIC_URL uv run python \
      scripts/build_model_research_benchmark.py --output-dir /tmp/bench \
      [--temperature-variants 4] [--n-samples 80] [--max-slates N]
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

SEED = 2026
CAPTURE_THRESHOLDS: tuple[int, ...] = (5, 8, 10)

# One OptimizeConfig override per registered knob, flipped away from the
# validated production value so each variant isolates one knob's effect.
# committed_order_objective is on in the validated production config, so the
# benchmark now measures the off-ablation explicitly.
KNOB_ABLATIONS: dict[str, dict[str, Any]] = {
    "knob:field_same_game_boost_off": {"field_same_game_boost": 1.0},
    "knob:field_same_team_boost_off": {"field_same_team_boost": 1.0},
    "knob:dynamic_team_cap_off": {"dynamic_team_cap": False},
    "knob:duplication_aware_payout_on": {"duplication_aware_payout": True},
    "knob:leverage_weight_0.2": {"leverage_weight": 0.2},
    "knob:ceiling_weight_0.2": {"ceiling_weight": 0.2},
    "knob:committed_order_objective_off": {"committed_order_objective": False},
}


def production_env_overrides() -> dict[str, str]:
    """Translate EXPECTED_PROD_CONFIG -- the validated production knobs
    ``Settings.config_drift`` checks live config against -- into the
    environment variables ``Settings`` reads them from.

    Settings field defaults are deliberately safe-off library values, not the
    production config (see settings.py's ``config_drift`` docstring), so
    compiling ``OptimizeConfig``/``ModelPolicy`` from a bare ``get_settings()``
    silently reverts every knob to its library default instead of what job2
    actually runs (e.g. ``optimizer_boost_sum_cap`` 9.0 -> 0.0). Applying
    these as env vars before the first ``get_settings()`` call makes the
    benchmark's baseline the same compiled policy job2 serves.
    """
    from wnba_oracle.common.settings import EXPECTED_PROD_CONFIG, Settings

    out: dict[str, str] = {}
    for name, value in EXPECTED_PROD_CONFIG.items():
        alias = Settings.model_fields[name].alias
        out[str(alias)] = "true" if value is True else "false" if value is False else str(value)
    return out


def temperature_values(n: int) -> list[float]:
    """Deterministic sigma scale factors, geometrically spread over
    [0.7, 1.5] around the production value 1.0. Returns [] for n <= 0."""
    if n <= 0:
        return []
    if n == 1:
        return [1.0]
    lo, hi = 0.7, 1.5
    ratio = (hi / lo) ** (1.0 / (n - 1))
    return [round(lo * ratio**i, 4) for i in range(n)]


def build_variant_grid(n_temperature_variants: int) -> list[dict[str, Any]]:
    """The full deterministic variant grid: baseline first, then per-knob
    ablations in registration order, then sigma-temperature variants."""
    grid: list[dict[str, Any]] = [
        {"name": "baseline", "overrides": {}, "sigma_scale": 1.0},
    ]
    for name, overrides in KNOB_ABLATIONS.items():
        grid.append({"name": name, "overrides": dict(overrides), "sigma_scale": 1.0})
    grid.extend(
        {"name": f"temp:sigma_x{t}", "overrides": {}, "sigma_scale": t}
        for t in temperature_values(n_temperature_variants)
    )
    return grid


def _coerce_override_value(raw: str) -> Any:
    """Coerce a local variant value to bool, int, float, or string."""
    low = raw.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(raw)
    except ValueError:
        try:
            return float(raw)
        except ValueError:
            return raw


def parse_extra_variant(spec: str) -> dict[str, Any]:
    """Parse ``name:key=value,key=value`` for a local calibration point."""
    name, separator, rest = spec.partition(":")
    if not separator or not name.strip():
        raise ValueError(f"--extra-variant expects name:key=value,...; got {spec!r}")
    name = name.strip()
    if not rest.strip():
        raise ValueError(f"--extra-variant {name!r} carries no overrides")
    overrides: dict[str, Any] = {}
    seen: set[str] = set()
    for pair in rest.split(","):
        key, equals, value = pair.partition("=")
        if not equals or not key.strip():
            raise ValueError(f"--extra-variant {name!r} has a bad override pair: {pair!r}")
        key = key.strip()
        value = value.strip()
        if not value:
            raise ValueError(f"--extra-variant {name!r} has an empty value for {key!r}")
        if key in seen:
            raise ValueError(f"--extra-variant {name!r} repeats override key {key!r}")
        seen.add(key)
        overrides[key] = _coerce_override_value(value)
    return {"name": name, "overrides": overrides, "sigma_scale": 1.0}


def extend_grid_with_extras(
    grid: list[dict[str, Any]], extra_specs: list[str]
) -> list[dict[str, Any]]:
    """Append uniquely named local calibration variants to the grid."""
    known = {variant["name"] for variant in grid}
    extras: list[dict[str, Any]] = []
    for spec in extra_specs:
        variant = parse_extra_variant(spec)
        if variant["name"] in known:
            raise ValueError(
                f"--extra-variant name {variant['name']!r} collides with the registered grid"
            )
        known.add(variant["name"])
        extras.append(variant)
    return grid + extras


def resolve_variant_grid(
    *,
    n_temperature_variants: int,
    extra_specs: list[str] | None = None,
    variant_names: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Build, validate, and optionally filter the registered plus local grid."""
    from wnba_oracle.picker.optimize import OptimizeConfig

    grid = build_variant_grid(n_temperature_variants)
    if extra_specs:
        grid = extend_grid_with_extras(grid, extra_specs)
    valid_fields = {field.name for field in dataclasses.fields(OptimizeConfig)}
    for variant in grid:
        unknown = sorted(set(variant["overrides"]) - valid_fields)
        if unknown:
            raise ValueError(
                f"variant {variant['name']!r} overrides unknown OptimizeConfig field(s): {unknown}"
            )
    if variant_names:
        wanted = set(variant_names)
        unknown = wanted - {variant["name"] for variant in grid}
        if unknown:
            raise ValueError(f"unknown variant name(s): {sorted(unknown)}")
        grid = [variant for variant in grid if variant["name"] in wanted]
    return grid


def select_shard(items: list[Any], index: int, count: int) -> list[Any]:
    """Deterministic strided shard: element i goes to shard i % count.
    Shards partition ``items`` exactly and each spans the full date range."""
    if count < 1 or not 0 <= index < count:
        raise ValueError("shard index must satisfy 0 <= index < count")
    return [x for i, x in enumerate(items) if i % count == index]


def scale_sigma(specs: list[Any], factor: float) -> list[Any]:
    """Return copies of sampling specs with sigma scaled by ``factor``.
    Specs must be dataclasses with a ``sigma`` field; input is not mutated."""
    if factor == 1.0:
        return list(specs)
    return [dataclasses.replace(s, sigma=float(s.sigma) * factor) for s in specs]


def score_lineup(
    player_ids: Sequence[int],
    slot_multipliers: Sequence[float],
    boost_by: dict[int, float],
    rs_by: dict[int, float],
) -> float:
    """Realized contest score for the lineup AS COMMITTED: ``player_ids[i]``
    sits in the slot with base ``slot_multipliers[i]``, unaffected by realized
    outcome. Delegates to the canonical eval helper (no re-sorting by realized
    value) so an optimizer slot-assignment bug shows up here instead of being
    hidden by hindsight scoring -- see ``wnba_oracle.eval.contest_score``."""
    from wnba_oracle.eval.contest_score import committed_order_score

    values = [rs_by.get(int(pid), 0.0) for pid in player_ids]
    boosts = [boost_by.get(int(pid), 0.0) for pid in player_ids]
    return committed_order_score(values, boosts, slot_multipliers)


def placement_for_score(our_score: float, lb_scores: list[float]) -> int:
    """1-based placement of ``our_score`` against a real leaderboard."""
    return sum(1 for s in lb_scores if s > our_score) + 1


def top_k_player_capture(
    player_ids: Sequence[int],
    rs_by: dict[int, float],
    thresholds: Sequence[int] = CAPTURE_THRESHOLDS,
) -> dict[str, dict[str, Any]]:
    """Count selected players in each realized top-k set.

    The reference pool is the same identified, draftable pool sent to the
    optimizer. A tie at the kth score expands the reference set instead of
    arbitrarily breaking the tie by player ID. ``hits`` still ranges from 0
    through 5 because the evaluated lineup always has five players.
    """
    if not rs_by:
        raise ValueError("realized-score pool is empty")
    selected = {int(player_id) for player_id in player_ids}
    scores = sorted((float(score) for score in rs_by.values()), reverse=True)
    out: dict[str, dict[str, Any]] = {}
    for raw_k in thresholds:
        k = int(raw_k)
        if k < 1:
            raise ValueError(f"capture threshold must be positive, got {k}")
        bounded_k = min(k, len(scores))
        cutoff = scores[bounded_k - 1]
        reference = {int(player_id) for player_id, score in rs_by.items() if float(score) >= cutoff}
        out[str(k)] = {
            "hits": len(selected & reference),
            "requested_k": k,
            "available_players": len(scores),
            "reference_size": len(reference),
            "boundary_tie_expanded": len(reference) > bounded_k,
        }
    return out


def summarize_variant(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-slate rows into the summary metrics reported per variant.

    Placement is right-censored below the leaderboard's captured depth (see
    each row's ``censored`` flag): the corpus only captures the top ~20
    leaderboard rows, so a score that doesn't reach that depth has an unknown
    exact rank, only a lower bound (``placement_lower_bound``).
    ``mean_placement`` is therefore not reportable, but top20/top5/top1 stay
    exact even under censoring: a censored row is *guaranteed* to miss every
    one of those thresholds (its lower bound already exceeds 20), so
    ``placement_lower_bound`` is compared directly against each cutoff with
    no need to special-case or drop censored rows.
    ``beat_median`` is reported only over rows where the field's true median
    rank fell within the captured depth -- for real field sizes that is rare,
    so it may be entirely absent rather than silently computed from a
    non-median row."""
    n = len(rows)
    if n == 0:
        return {"n_slates": 0}
    out: dict[str, Any] = {
        "n_slates": n,
        "n_censored": sum(1 for r in rows if r["censored"]),
        "top20_pct": round(100.0 * sum(1 for r in rows if r["placement_lower_bound"] <= 20) / n, 1),
        "top5_pct": round(100.0 * sum(1 for r in rows if r["placement_lower_bound"] <= 5) / n, 1),
        "top1_pct": round(100.0 * sum(1 for r in rows if r["placement_lower_bound"] <= 1) / n, 1),
        "mean_gap_vs_top1": round(sum(r["gap"] for r in rows) / n, 3),
        "mean_payout_capture": round(sum(r["payout_capture"] for r in rows) / n, 4),
    }
    median_rows = [r for r in rows if "beat_median" in r]
    if median_rows:
        out["beat_median_pct"] = round(
            100.0 * sum(r["beat_median"] for r in median_rows) / len(median_rows), 1
        )
        out["n_median_observed"] = len(median_rows)
    capture_summary: dict[str, Any] = {}
    for k in CAPTURE_THRESHOLDS:
        capture_rows = [
            r["top_k_player_capture"][str(k)]
            for r in rows
            if str(k) in r.get("top_k_player_capture", {})
        ]
        if not capture_rows:
            continue
        distribution = {str(hits): 0 for hits in range(6)}
        for capture in capture_rows:
            distribution[str(int(capture["hits"]))] += 1
        mean_hits = sum(int(capture["hits"]) for capture in capture_rows) / len(capture_rows)
        capture_summary[str(k)] = {
            "n_observed": len(capture_rows),
            "mean_hits": round(mean_hits, 3),
            "mean_lineup_capture_pct": round(100.0 * mean_hits / 5.0, 1),
            "hit_distribution": distribution,
            "n_tie_expanded": sum(
                1 for capture in capture_rows if capture["boundary_tie_expanded"]
            ),
        }
    if capture_summary:
        out["top_k_player_capture"] = capture_summary
    return out


def _comparison_counts(deltas: list[float], *, lower_is_better: bool = False) -> dict[str, Any]:
    """Summarize challenger-minus-baseline deltas."""
    wins = sum(delta < 0 if lower_is_better else delta > 0 for delta in deltas)
    losses = sum(delta > 0 if lower_is_better else delta < 0 for delta in deltas)
    return {
        "wins": wins,
        "ties": len(deltas) - wins - losses,
        "losses": losses,
        "mean_delta": round(sum(deltas) / len(deltas), 4) if deltas else None,
    }


def build_paired_comparisons(
    variants: list[dict[str, Any]],
    baseline_name: str = "baseline",
) -> list[dict[str, Any]]:
    """Compare each variant with baseline on identical slate dates.

    Score and payout pairs are exact. Placement deltas are emitted only when
    both ranks are observed; a pair touching a right-censored rank is counted
    but never assigned a guessed placement delta.
    """
    by_name = {variant["name"]: variant for variant in variants}
    baseline = by_name.get(baseline_name)
    if baseline is None:
        return []
    baseline_rows = {row["slate_date"]: row for row in baseline["slates"]}
    comparisons: list[dict[str, Any]] = []
    for variant in variants:
        if variant["name"] == baseline_name:
            continue
        challenger_rows = {row["slate_date"]: row for row in variant["slates"]}
        common = sorted(set(baseline_rows) & set(challenger_rows))
        slate_pairs: list[dict[str, Any]] = []
        score_deltas: list[float] = []
        payout_deltas: list[float] = []
        placement_deltas: list[float] = []
        capture_deltas: dict[str, list[float]] = {str(k): [] for k in CAPTURE_THRESHOLDS}
        for slate_date in common:
            base = baseline_rows[slate_date]
            challenger = challenger_rows[slate_date]
            base_score = float(base.get("committed_order_score", base["our_score"]))
            challenger_score = float(
                challenger.get("committed_order_score", challenger["our_score"])
            )
            score_delta = round(challenger_score - base_score, 3)
            payout_delta = round(
                float(challenger["payout"]) - float(base["payout"]),
                4,
            )
            score_deltas.append(score_delta)
            payout_deltas.append(payout_delta)
            base_placement = base.get("placement")
            challenger_placement = challenger.get("placement")
            placement_delta = None
            if base_placement is not None and challenger_placement is not None:
                placement_delta = int(challenger_placement) - int(base_placement)
                placement_deltas.append(float(placement_delta))
            per_k: dict[str, int] = {}
            for k in CAPTURE_THRESHOLDS:
                key = str(k)
                base_capture = base.get("top_k_player_capture", {}).get(key)
                challenger_capture = challenger.get("top_k_player_capture", {}).get(key)
                if base_capture is None or challenger_capture is None:
                    continue
                delta = int(challenger_capture["hits"]) - int(base_capture["hits"])
                per_k[key] = delta
                capture_deltas[key].append(float(delta))
            slate_pairs.append(
                {
                    "slate_date": slate_date,
                    "baseline_committed_order_score": base_score,
                    "challenger_committed_order_score": challenger_score,
                    "committed_order_score_delta": score_delta,
                    "baseline_payout": float(base["payout"]),
                    "challenger_payout": float(challenger["payout"]),
                    "payout_delta": payout_delta,
                    "baseline_placement": base_placement,
                    "challenger_placement": challenger_placement,
                    "placement_delta": placement_delta,
                    "placement_censored": placement_delta is None,
                    "top_k_player_capture_delta": per_k,
                }
            )
        placement_summary = _comparison_counts(placement_deltas, lower_is_better=True)
        placement_summary.update(
            {
                "n_exact_pairs": len(placement_deltas),
                "n_censored_pairs": len(common) - len(placement_deltas),
            }
        )
        comparisons.append(
            {
                "baseline": baseline_name,
                "challenger": variant["name"],
                "n_common_slates": len(common),
                "n_baseline_only": len(set(baseline_rows) - set(challenger_rows)),
                "n_challenger_only": len(set(challenger_rows) - set(baseline_rows)),
                "committed_order_score": _comparison_counts(score_deltas),
                "payout": _comparison_counts(payout_deltas),
                "placement": placement_summary,
                "top_k_player_capture": {
                    key: _comparison_counts(deltas)
                    for key, deltas in capture_deltas.items()
                    if deltas
                },
                "slates": slate_pairs,
            }
        )
    return comparisons


def _coverage_note(meta: dict[str, Any]) -> str:
    """The denominator, stated up front. A reader must be able to tell from the
    report alone whether the run covered the corpus or a biased slice of it --
    the numerator alone reads as full coverage even when most slates dropped."""
    parts: list[str] = []
    dropped = sum((meta.get("drop_reasons") or {}).values())
    if dropped:
        reasons = ", ".join(
            f"{k}={v}" for k, v in sorted((meta.get("drop_reasons") or {}).items()) if v
        )
        parts.append(
            f"**Coverage: {meta.get('n_slates', 0)} slates benchmarked, "
            f"{dropped} dropped** ({reasons}). Dropped slates are excluded, "
            "never reconstructed from inferred matchups."
        )
    methods = meta.get("game_key_method") or {}
    if methods:
        parts.append(
            "Game identity resolved via "
            + ", ".join(f"`{k}` on {v} slate(s)" for k, v in sorted(methods.items()))
            + ". `provider_game_id` is the path production serves on; "
            "`team_opponent_fallback` and `incomplete` mean the same-game and "
            "same-team variants were measured on a degraded identity path."
        )
    if meta.get("shards_missing"):
        parts.append(
            f"**INCOMPLETE: shards {meta['shards_missing']} are missing from this "
            "merge.** Treat every number below as a partial result."
        )
    return " ".join(parts)


def render_markdown(result: dict[str, Any]) -> str:
    """Render the benchmark summary as the MODEL_RESEARCH_BENCHMARK.md text."""
    meta = result["meta"]
    lines = [
        "# Model research benchmark",
        "",
        f"Generated {meta['generated_at']} by "
        "`scripts/build_model_research_benchmark.py`. Walk-forward replay of "
        f"{meta['n_slates']} stored 2026 slates through the production "
        f"optimizer (seed {meta['seed']}, n_samples {meta['n_samples']}). "
        "This file is a generated artifact; regenerate it rather than editing.",
        "",
        "Placement is exact only when our score beats the lowest leaderboard "
        "row the corpus captured (top ~20 of the real field); below that it "
        "is right-censored (counted as a top-20 miss, excluded from "
        "top5/top1/beat median). `payout_capture` stays exact under the "
        "top-20 curve, since a censored score pays 0 -- reported as realized "
        "payout divided by the rank-1 payout.",
        "",
        _coverage_note(meta),
        "",
        "| variant | slates | censored | top 20 | top 5 | top 1 | beat median "
        "| mean gap vs top 1 | payout capture |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for v in result["variants"]:
        s = v["summary"]
        if s.get("n_slates", 0) == 0:
            lines.append(f"| {v['name']} | 0 | - | - | - | - | - | - | - |")
            continue
        beat_median = f"{s['beat_median_pct']}%" if "beat_median_pct" in s else "-"
        lines.append(
            f"| {v['name']} | {s['n_slates']} | {s['n_censored']} "
            f"| {s['top20_pct']}% | {s['top5_pct']}% | {s['top1_pct']}% "
            f"| {beat_median} | {s['mean_gap_vs_top1']} | {s['mean_payout_capture']} |"
        )
    capture_variants = [
        variant for variant in result["variants"] if variant["summary"].get("top_k_player_capture")
    ]
    if capture_variants:
        lines.extend(
            [
                "",
                "Player capture is measured against realized scores inside the "
                "same identified draftable pool the optimizer received. Ties at "
                "a top-k boundary expand the reference set rather than being "
                "broken arbitrarily.",
                "",
                "| variant | top 5 mean hits | top 5 distribution (0..5) "
                "| top 8 mean hits | top 10 mean hits |",
                "|---|---|---|---|---|",
            ]
        )
        for variant in capture_variants:
            capture = variant["summary"]["top_k_player_capture"]
            top5 = capture["5"]
            distribution = "/".join(str(top5["hit_distribution"][str(hits)]) for hits in range(6))
            lines.append(
                f"| {variant['name']} | {top5['mean_hits']} "
                f"| {distribution} | {capture['8']['mean_hits']} "
                f"| {capture['10']['mean_hits']} |"
            )
    if result.get("paired_comparisons"):
        lines.extend(
            [
                "",
                "Paired comparisons use only common slate dates. Placement "
                "win/tie/loss counts exclude any pair where either placement is "
                "right-censored.",
                "",
                "| challenger vs baseline | paired slates | score W/T/L "
                "| mean score delta | payout W/T/L | mean payout delta "
                "| placement exact/censored | placement W/T/L |",
                "|---|---|---|---|---|---|---|---|",
            ]
        )
        for comparison in result["paired_comparisons"]:
            score = comparison["committed_order_score"]
            payout = comparison["payout"]
            placement = comparison["placement"]
            lines.append(
                f"| {comparison['challenger']} vs {comparison['baseline']} "
                f"| {comparison['n_common_slates']} "
                f"| {score['wins']}/{score['ties']}/{score['losses']} "
                f"| {score['mean_delta']} "
                f"| {payout['wins']}/{payout['ties']}/{payout['losses']} "
                f"| {payout['mean_delta']} "
                f"| {placement['n_exact_pairs']}/{placement['n_censored_pairs']} "
                f"| {placement['wins']}/{placement['ties']}/{placement['losses']} |"
            )
    lines.append("")
    return "\n".join(lines)


def atomic_write_text(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` atomically via a same-directory temp
    file and os.replace, so readers never observe a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def load_labels_csv(path: Path) -> Any:
    """Load a corpus-backup ``slate_labels.csv`` into the same frame shape
    ``read_slate_labels`` returns. The file comes from the verified backups
    branch (see .github/workflows/corpus-backup.yml)."""
    import polars as pl

    sl = pl.read_csv(
        path,
        schema_overrides={
            "slate_date": pl.Utf8,
            "platform_player_id": pl.Int64,
            "display_name": pl.Utf8,
            "team_key": pl.Utf8,
            "card_boost": pl.Float64,
            "drafts": pl.Float64,  # CSV serializes counts as floats
            "real_score": pl.Float64,
        },
    )
    return sl.with_columns(pl.col("drafts").cast(pl.Int64))


def load_leaderboards_csv(path: Path) -> Any:
    """Load a corpus-backup ``contest_leaderboards.csv`` into the same frame
    shape ``read_leaderboards`` returns (``lineup`` renamed ``lineup_json``)."""
    import polars as pl

    lb = pl.read_csv(
        path,
        schema_overrides={"slate_date": pl.Utf8, "rank": pl.Int64, "score": pl.Float64},
    )
    if "lineup" in lb.columns and "lineup_json" not in lb.columns:
        lb = lb.rename({"lineup": "lineup_json"})
    return lb


def drafts_by_slate(sl: Any) -> dict[str, dict[int, int]]:
    """Measured draft counts per slate from the labels frame, matching the
    shape of job2's ``_load_measured_drafts`` for one slate."""
    out: dict[str, dict[int, int]] = {}
    for r in sl.iter_rows(named=True):
        d = r.get("drafts")
        if d is None:
            continue
        sd = str(r["slate_date"])
        pid = int(r["platform_player_id"])
        cur = out.setdefault(sd, {})
        cur[pid] = max(int(d), cur.get(pid, 0))
    return out


def load_game_identity_csv(path: Path) -> Any:
    """Load the prefetched PER-PLAYER identity CSV (slate_date,
    real_sports_player_id, team, opponent, game_id), sourced from
    ``job1_enrichment`` -- the same Real Sports platform corpus that produces
    ``slate_labels``, so no cross-provider team crosswalk is needed (see
    wnba-oracle/AGENTS.md: do not join the gamelog and label corpora without
    an explicit identity map; this sidesteps that by staying inside one
    corpus)."""
    import polars as pl

    return pl.read_csv(
        path,
        schema_overrides={
            "slate_date": pl.Utf8,
            "real_sports_player_id": pl.Utf8,
            "team": pl.Utf8,
            "opponent": pl.Utf8,
            "game_id": pl.Utf8,
        },
    )


def index_game_identity(identity: Any) -> dict[str, dict[int, dict[str, str]]]:
    """Per-player identity rows -> {slate_date: {player_id: {team, opponent, game_id}}}.

    Keyed per player rather than per team on purpose. ``job1_enrichment`` IS
    the pool job2 optimizes over, so this reproduces production's actual pool
    and carries the provider ``game_id`` that
    ``picker.stacking.resolve_game_keys`` prefers -- instead of rebuilding a
    per-team map from ``slate_labels.team_key`` and validating reciprocity,
    which only ever fed the FALLBACK path production takes when the provider
    id is absent.

    A duplicate (slate_date, player_id) keeps the first row and is reported by
    the caller rather than silently overwritten, so a conflicting re-capture
    can never be resolved by row order.
    """
    out: dict[str, dict[int, dict[str, str]]] = {}
    for r in identity.iter_rows(named=True):
        raw_pid = r.get("real_sports_player_id")
        if raw_pid is None or str(raw_pid).strip() == "":
            continue
        try:
            pid = int(str(raw_pid).strip())
        except ValueError:
            continue
        day = out.setdefault(str(r["slate_date"]), {})
        if pid in day:
            continue
        day[pid] = {
            "team": str(r.get("team") or "").strip(),
            "opponent": str(r.get("opponent") or "").strip(),
            "game_id": str(r.get("game_id") or "").strip(),
        }
    return out


# slate_labels rows harvested from finisher lineups rather than from the
# draftable pool. contest_stats.labels_from_leaderboard_entries writes
# team_key='UNK' for these because the leaderboard payload carries no teamKey;
# verified over the 2026 corpus, section=='leaderboard_lineup' and
# team_key=='UNK' are the same 114 rows. They are NOT pool entries -- job2
# optimizes over job1_enrichment, where team/opponent are NOT NULL -- so
# treating 'UNK' as a real team that needs an opponent dropped 29 otherwise
# healthy slates outright.
SUPPLEMENTAL_LABEL_SECTION = "leaderboard_lineup"


def _precompute_slates(
    max_slates: int | None,
    labels_csv: Path | None = None,
    leaderboards_csv: Path | None = None,
    game_identity_csv: Path | None = None,
    shard: tuple[int, int] | None = None,
    policy: Any = None,
) -> tuple[dict[str, dict[str, Any]], int]:
    """Load labels, leaderboards, and validated game identity (database, or
    offline corpus-backup / prefetch CSVs) and build the production sampling
    and field specs once per eligible 2026 slate. ``shard=(index, count)``
    keeps every count-th slate starting at index, so parallel shards
    partition the slate set exactly.

    The pool for each slate is the INTERSECTION of the label corpus and the
    persisted ``job1_enrichment`` identity, joined per player. That is exactly
    the pool job2 optimizes over, and it carries the provider ``game_id`` that
    ``picker.stacking.resolve_game_keys`` prefers over the reciprocal
    team/opponent fallback -- so the benchmark exercises the same game-identity
    path production serves on, rather than being pinned to the fallback by a
    blank ``features_json``. Identity is never fabricated: a player without a
    persisted identity row is excluded from the pool, and a slate left with
    too few players is dropped.

    Returns ``(precomputed, drops)`` where ``drops`` counts each exclusion
    reason, so a shrinking corpus is visible in the artifact instead of
    silently biasing the variant ranking."""
    import polars as pl

    from wnba_oracle.scheduler.job2 import _build_specs

    if labels_csv is not None and leaderboards_csv is not None:
        sl = load_labels_csv(labels_csv)
        lb = load_leaderboards_csv(leaderboards_csv)
        identity = load_game_identity_csv(game_identity_csv) if game_identity_csv else None
        # Offline mode has no engine: serve measured drafts from the CSV so
        # the D86 measured-ownership path matches the live path.
        import wnba_oracle.scheduler.job2 as _job2

        measured = drafts_by_slate(sl)
        _job2._load_measured_drafts = lambda sd: measured.get(str(sd), {})
    else:
        from wnba_oracle.db.reads import read_game_identity, read_leaderboards, read_slate_labels

        sl = read_slate_labels()
        lb = read_leaderboards()
        identity = read_game_identity()
    identity_by_slate = index_game_identity(identity) if identity is not None else {}

    slates_2026 = {d for d in sl["slate_date"].unique().to_list() if str(d).startswith("2026-")}
    valid = sorted(slates_2026 & set(lb["slate_date"].unique().to_list()))
    if shard is not None:
        valid = select_shard(valid, shard[0], shard[1])
    if max_slates is not None:
        valid = valid[:max_slates]

    precomputed: dict[str, dict[str, Any]] = {}
    drops: dict[str, int] = {
        "too_few_scored_labels": 0,
        "too_few_leaderboard_rows": 0,
        "no_identity_rows": 0,
        "too_few_identified_players": 0,
        "too_few_specs": 0,
    }
    for sd in valid:
        slate = sl.filter(pl.col("slate_date") == sd)
        if slate.filter(pl.col("real_score").is_not_null()).height < 5:
            drops["too_few_scored_labels"] += 1
            continue
        slate_lb = lb.filter(pl.col("slate_date") == sd)
        lb_scores = slate_lb["score"].to_list()
        if len(lb_scores) < 5:
            drops["too_few_leaderboard_rows"] += 1
            continue
        # num_brawlers is the true field size; captured rows are only the
        # leaderboard's top slice. max() covers a slate spanning more than
        # one contest without understating the field.
        brawlers = (
            slate_lb["num_brawlers"].drop_nulls() if "num_brawlers" in slate_lb.columns else None
        )
        field_size = (
            int(brawlers.max()) if brawlers is not None and len(brawlers) else len(lb_scores)
        )
        field_size = max(field_size, len(lb_scores))
        day_identity = identity_by_slate.get(str(sd), {})
        if not day_identity:
            drops["no_identity_rows"] += 1
            continue
        boost_by: dict[int, float] = {}
        rs_by: dict[int, float] = {}
        enrichment = []
        n_with_game_id = 0
        for r in slate.iter_rows(named=True):
            # Supplemental finisher-lineup labels are not draftable pool
            # entries and carry the 'UNK' team sentinel; production's pool
            # never contains them. Excluding them here is a provenance filter,
            # not a workaround for the sentinel string.
            if str(r.get("section") or "") == SUPPLEMENTAL_LABEL_SECTION:
                continue
            pid = int(r["platform_player_id"])
            ident = day_identity.get(pid)
            if ident is None or not ident["team"]:
                # No persisted identity for this player on this slate. Excluded
                # rather than invented; production could not have drafted a
                # player absent from job1_enrichment either.
                continue
            boost_by[pid] = float(r["card_boost"])
            rs_by[pid] = float(r["real_score"]) if r["real_score"] is not None else 0.0
            features: dict[str, Any] = {}
            if ident["game_id"]:
                features["game_id"] = ident["game_id"]
                n_with_game_id += 1
            enrichment.append(
                {
                    "real_sports_player_id": str(pid),
                    "name": r["display_name"],
                    "team": ident["team"],
                    "opponent": ident["opponent"],
                    "position": "F",
                    "card_boost": boost_by[pid],
                    "features_json": json.dumps(features),
                }
            )
        if len(enrichment) < 5:
            drops["too_few_identified_players"] += 1
            continue
        samps, fields, _ = _build_specs(enrichment, slate_date=sd, policy=policy)
        if len(samps) < 5:
            drops["too_few_specs"] += 1
            continue
        # Record which identity path this slate will actually resolve on, so
        # the artifact shows whether the stacking variants were measured on
        # production's provider path or the corruptible fallback.
        from wnba_oracle.picker.stacking import resolve_game_keys

        _, game_key_method, n_games = resolve_game_keys(samps)
        precomputed[sd] = {
            "samps": samps,
            "fields": fields,
            "boost_by": boost_by,
            "rs_by": rs_by,
            "lb_scores": sorted(lb_scores, reverse=True),
            "field_size": field_size,
            "pool_size": len(enrichment),
            "n_with_game_id": n_with_game_id,
            "game_key_method": game_key_method,
            "n_games": n_games,
        }
    return precomputed, drops


def _run_variant(
    variant: dict[str, Any],
    precomputed: dict[str, dict[str, Any]],
    n_samples: int,
    baseline_cfg: Any,
) -> tuple[list[dict[str, Any]], int, int]:
    """Replay every precomputed slate under one variant's configuration.

    ``baseline_cfg`` is the compiled production OptimizeConfig (see
    ``production_env_overrides``); each variant's override applies on top of
    it via ``dataclasses.replace``, alongside the benchmark's own
    compute-budget knobs (n_samples, n_field_lineups, top_n_filter, seed),
    which are research parameters, not policy.

    Returns ``(rows, n_optimizer_error, n_optimizer_infeasible)``. A slate
    the optimizer raises on, or returns no feasible 5-player lineup for
    (e.g. a 2-team slate under knob:dynamic_team_cap_off, which caps at
    2*2=4 players -- optimize_lineup's own fallback for that case returns an
    empty ``player_ids``, not an exception), is dropped and counted rather
    than silently excluded: an uncounted drop biases top1/top5/top20 toward
    whichever slates happened to survive, and letting the empty-lineup case
    reach score_lineup would raise (0 values against 5 slot bases) and
    silently discard the whole shard's in-memory results."""
    from wnba_oracle.picker.optimize import optimize_lineup
    from wnba_oracle.picker.payout import default_curve_for_regime

    curve = default_curve_for_regime("top_20")
    rows: list[dict[str, Any]] = []
    n_optimizer_error = 0
    n_optimizer_infeasible = 0
    for sd in sorted(precomputed):
        d = precomputed[sd]
        cfg = dataclasses.replace(
            baseline_cfg,
            top_n_filter=min(20, len(d["samps"])),
            n_samples=n_samples,
            n_field_lineups=40,
            seed=SEED,
            **variant["overrides"],
        )
        samps = scale_sigma(d["samps"], variant["sigma_scale"])
        try:
            rec = optimize_lineup(samps, d["fields"], curve, cfg=cfg)
        except Exception as exc:
            n_optimizer_error += 1
            print(f"optimizer error: {variant['name']} {sd} {type(exc).__name__}", file=sys.stderr)
            continue
        if not rec.player_ids:
            n_optimizer_infeasible += 1
            print(f"optimizer infeasible: {variant['name']} {sd}", file=sys.stderr)
            continue
        our = score_lineup(rec.player_ids, rec.slot_multipliers, d["boost_by"], d["rs_by"])
        lb_scores = d["lb_scores"]
        field_size = d["field_size"]
        captured_depth = len(lb_scores)
        # Below the lowest captured row, the real rank is unknown -- only a
        # lower bound. A score tying the lowest captured row is still exact:
        # nothing captured beats it, and nothing outside the top-N capture
        # could either (it would have been captured). Not censored at all
        # when the leaderboard captured the whole field (field_size <=
        # captured_depth): nothing is missing then.
        censored = field_size > captured_depth and our < lb_scores[-1]
        if censored:
            placement = None
            placement_lower_bound = captured_depth + 1
            payout = 0.0
        else:
            placement = placement_for_score(our, lb_scores)
            placement_lower_bound = placement
            payout = curve.payout_for_rank(placement, field_size)
        top1_payout = curve.payout_for_rank(1, field_size)
        row: dict[str, Any] = {
            "slate_date": str(sd),
            "player_ids": [int(player_id) for player_id in rec.player_ids],
            "committed_order_score": round(our, 3),
            "our_score": round(our, 3),
            "placement": placement,
            "placement_lower_bound": placement_lower_bound,
            "censored": censored,
            "field_size": field_size,
            "captured_depth": captured_depth,
            "gap": round(lb_scores[0] - our, 3),
            "payout": round(payout, 4),
            "payout_capture": round(payout / top1_payout, 4) if top1_payout > 0 else 0.0,
            "top_k_player_capture": top_k_player_capture(rec.player_ids, d["rs_by"]),
        }
        # beat_median is only meaningful when the true field median rank was
        # actually captured; for real field sizes (num_brawlers far exceeds
        # the ~20-row capture) it almost never is, so the key is omitted
        # rather than computed against a row that isn't the real median.
        median_rank = (field_size + 1) // 2
        if median_rank <= captured_depth:
            median = lb_scores[median_rank - 1]
            row["beat_median"] = 1 if our > median else 0
        rows.append(row)
    return rows, n_optimizer_error, n_optimizer_infeasible


def merge_shard_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Combine per-shard benchmark_results.json payloads into one result:
    per-variant slate rows are concatenated (deduplicated by slate_date,
    sorted) and summaries recomputed over the union."""
    if not results:
        raise ValueError("no shard results to merge")
    by_variant: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    total_slates: set[str] = set()
    for res in results:
        for v in res["variants"]:
            if v["name"] not in by_variant:
                by_variant[v["name"]] = {
                    "name": v["name"],
                    "overrides": v.get("overrides", {}),
                    "sigma_scale": v.get("sigma_scale", 1.0),
                    "n_optimizer_error": 0,
                    "n_optimizer_infeasible": 0,
                    "rows_by_slate": {},
                }
                order.append(v["name"])
            entry = by_variant[v["name"]]
            entry["n_optimizer_error"] += int(v.get("n_optimizer_error", 0))
            entry["n_optimizer_infeasible"] += int(v.get("n_optimizer_infeasible", 0))
            rows = entry["rows_by_slate"]
            for row in v["slates"]:
                rows[row["slate_date"]] = row
                total_slates.add(row["slate_date"])
    variants = []
    for name in order:
        entry = by_variant[name]
        rows = [entry["rows_by_slate"][sd] for sd in sorted(entry["rows_by_slate"])]
        variants.append(
            {
                "name": name,
                "overrides": entry["overrides"],
                "sigma_scale": entry["sigma_scale"],
                "n_optimizer_error": entry["n_optimizer_error"],
                "n_optimizer_infeasible": entry["n_optimizer_infeasible"],
                "summary": summarize_variant(rows),
                "slates": rows,
            }
        )
    # Which shards actually contributed, and which are missing. Without this a
    # merged artifact from a partial matrix is indistinguishable from a
    # complete one -- silent truncation that reads as full coverage.
    contributed = sorted(
        {
            int(res["meta"]["shard_index"])
            for res in results
            if res["meta"].get("shard_index") is not None
        }
    )
    expected = max(
        (int(res["meta"].get("shard_count") or 0) for res in results),
        default=0,
    )
    missing = [i for i in range(expected) if i not in contributed] if expected else []

    merged_drops: dict[str, int] = {}
    for res in results:
        for reason, n in (res["meta"].get("drop_reasons") or {}).items():
            merged_drops[reason] = merged_drops.get(reason, 0) + int(n)

    base_meta = dict(results[0]["meta"])
    base_meta.update(
        {
            "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
            "n_slates": len(total_slates),
            "drop_reasons": merged_drops,
            "merged_shards": len(results),
            "shards_contributed": contributed,
            "shards_missing": missing,
            "complete": not missing,
            "shard_index": None,
            "shard_count": expected or None,
        }
    )
    return {
        "meta": base_meta,
        "variants": variants,
        "paired_comparisons": build_paired_comparisons(variants),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--temperature-variants", type=int, default=4)
    parser.add_argument("--n-samples", type=int, default=80)
    parser.add_argument("--max-slates", type=int, default=None)
    parser.add_argument("--labels-csv", type=Path, default=None)
    parser.add_argument("--leaderboards-csv", type=Path, default=None)
    parser.add_argument("--game-identity-csv", type=Path, default=None)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument(
        "--merge-shards",
        nargs="+",
        type=Path,
        default=None,
        help="Merge existing shard benchmark_results.json files instead of running.",
    )
    parser.add_argument(
        "--variant",
        action="append",
        default=None,
        help="Run only the named variant(s); repeatable. Default: full grid.",
    )
    parser.add_argument(
        "--extra-variant",
        action="append",
        default=None,
        metavar="NAME:KEY=VALUE,...",
        help=(
            "Append a local multi-knob variant without expanding the registered grid. "
            "Extras are added before --variant filtering."
        ),
    )
    parser.add_argument(
        "--report-coverage",
        action="store_true",
        help=(
            "Pre-flight only: report how many slates are eligible and why the "
            "rest were dropped, then exit without running the optimizer. "
            "Costs under a second; run this before spending shard compute."
        ),
    )
    parser.add_argument(
        "--min-eligible-slates",
        type=int,
        default=0,
        help=(
            "With --report-coverage, exit non-zero if fewer slates are "
            "eligible. Guards against certifying a corpus too small or too "
            "biased to separate variants from noise."
        ),
    )
    args = parser.parse_args()

    if args.merge_shards:
        payloads = [json.loads(p.read_text(encoding="utf-8")) for p in args.merge_shards]
        merged = merge_shard_results(payloads)
        atomic_write_text(
            args.output_dir / "benchmark_results.json", json.dumps(merged, indent=2) + "\n"
        )
        atomic_write_text(args.output_dir / "MODEL_RESEARCH_BENCHMARK.md", render_markdown(merged))
        print(f"Merged {len(payloads)} shard files into {args.output_dir}")
        return 0

    offline = args.labels_csv is not None and args.leaderboards_csv is not None
    if (args.labels_csv is None) != (args.leaderboards_csv is None):
        print("--labels-csv and --leaderboards-csv must be given together", file=sys.stderr)
        return 2
    if not offline and not os.environ.get("DATABASE_URL"):
        print(
            "DATABASE_URL is required in the process environment "
            "(or pass --labels-csv/--leaderboards-csv for offline mode)",
            file=sys.stderr,
        )
        return 2
    if offline and args.game_identity_csv is None:
        print(
            "WARNING: offline mode without --game-identity-csv; every slate "
            "will be dropped as ineligible (real game identity unavailable) "
            "rather than assigned a fabricated opponent.",
            file=sys.stderr,
        )

    os.environ.setdefault(
        "WNBA_ORACLE_MODEL_ARTIFACT_SHA",
        "94f8e8606dab4d48652929bb3884fb9152e1abc766eeb2c2d86559f4318676cd",
    )
    os.environ.setdefault("PAYOUT_REGIME", "top_20")
    os.environ.setdefault("OPTIMIZER_MAX_PER_TEAM", "2")
    os.environ.setdefault("FIELD_MEASURED_OWNERSHIP_ENABLED", "true")
    for alias, value in production_env_overrides().items():
        os.environ.setdefault(alias, value)

    import structlog

    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    from wnba_oracle.common.settings import get_settings
    from wnba_oracle.scheduler.job2 import build_model_policy

    policy = build_model_policy(get_settings())

    print("Precomputing production specs per slate...")
    precomputed, drops = _precompute_slates(
        args.max_slates,
        args.labels_csv,
        args.leaderboards_csv,
        args.game_identity_csv,
        shard=(args.shard_index, args.shard_count),
        policy=policy,
    )
    # Full accounting to stderr: every exclusion reason, not just one of them.
    # A silently shrinking corpus biases variant ranking toward whichever
    # slates happened to survive, so the denominator has to be legible.
    by_method: dict[str, int] = {}
    for d in precomputed.values():
        by_method[d["game_key_method"]] = by_method.get(d["game_key_method"], 0) + 1
    print(
        f"eligible={len(precomputed)} dropped={sum(drops.values())} "
        f"reasons={ {k: v for k, v in drops.items() if v} } "
        f"game_key_method={by_method}",
        file=sys.stderr,
    )

    if args.report_coverage:
        # Pre-flight gate: the whole eligibility cascade costs well under a
        # second, versus ~86 CPU-hours for the sharded matrix. Running this
        # first is what turns "we discovered 65% of the corpus was dropped
        # from a failed CI run" into a cheap, loud, pre-dispatch check.
        payload = {
            "eligible": len(precomputed),
            "dropped": sum(drops.values()),
            "drop_reasons": drops,
            "game_key_method": by_method,
            "slates": sorted(precomputed),
        }
        print(json.dumps(payload, indent=2))
        if args.min_eligible_slates and len(precomputed) < args.min_eligible_slates:
            print(
                f"FAIL: {len(precomputed)} eligible slates is below "
                f"--min-eligible-slates {args.min_eligible_slates}. Refusing to "
                "certify a benchmark whose corpus is too small or too biased to "
                "separate variants from noise.",
                file=sys.stderr,
            )
            return 1
        return 0

    if not precomputed:
        # An empty shard is a correct partition outcome, not an error: with a
        # small eligible set strided over many shards, some shards legitimately
        # get zero slates. Exiting non-zero here failed the whole matrix job,
        # which skipped `merge` and discarded every SUCCESSFUL shard's work.
        # Write an empty-but-valid artifact so the upload step's
        # if-no-files-found:error still guards genuine breakage.
        print("No eligible slates in this shard; writing empty result.", file=sys.stderr)
        empty = {
            "meta": {
                "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
                "seed": SEED,
                "n_samples": args.n_samples,
                "n_slates": 0,
                "drop_reasons": drops,
                "temperature_variants": args.temperature_variants,
                "shard_index": args.shard_index,
                "shard_count": args.shard_count,
                "offline_csv": bool(offline),
            },
            "variants": [],
            "paired_comparisons": [],
        }
        atomic_write_text(
            args.output_dir / "benchmark_results.json", json.dumps(empty, indent=2) + "\n"
        )
        atomic_write_text(args.output_dir / "MODEL_RESEARCH_BENCHMARK.md", render_markdown(empty))
        return 0

    try:
        grid = resolve_variant_grid(
            n_temperature_variants=args.temperature_variants,
            extra_specs=args.extra_variant,
            variant_names=args.variant,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    variants: list[dict[str, Any]] = []
    for i, variant in enumerate(grid, 1):
        print(f"[{i}/{len(grid)}] {variant['name']}")
        rows, n_optimizer_error, n_optimizer_infeasible = _run_variant(
            variant, precomputed, args.n_samples, policy.optimizer
        )
        variants.append(
            {
                "name": variant["name"],
                "overrides": variant["overrides"],
                "sigma_scale": variant["sigma_scale"],
                "n_optimizer_error": n_optimizer_error,
                "n_optimizer_infeasible": n_optimizer_infeasible,
                "summary": summarize_variant(rows),
                "slates": rows,
            }
        )

    result = {
        "meta": {
            "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
            "seed": SEED,
            "n_samples": args.n_samples,
            "n_slates": len(precomputed),
            "drop_reasons": drops,
            "game_key_method": by_method,
            "temperature_variants": args.temperature_variants,
            "shard_index": args.shard_index,
            "shard_count": args.shard_count,
            "offline_csv": bool(offline),
            "baseline_policy": dataclasses.asdict(policy),
        },
        "variants": variants,
        "paired_comparisons": build_paired_comparisons(variants),
    }
    out = args.output_dir
    atomic_write_text(out / "benchmark_results.json", json.dumps(result, indent=2) + "\n")
    atomic_write_text(out / "MODEL_RESEARCH_BENCHMARK.md", render_markdown(result))
    print(f"Wrote {out / 'benchmark_results.json'}")
    print(f"Wrote {out / 'MODEL_RESEARCH_BENCHMARK.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

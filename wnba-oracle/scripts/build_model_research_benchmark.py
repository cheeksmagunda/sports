"""Model research benchmark: walk-forward variant sweep over stored slates.

Replays every 2026 slate that has both labels and leaderboard data through the
production optimizer, once per variant, and records honest realized metrics
(placement against the actual leaderboard, gap to the winner, and payout
capture under the top-20 curve). Variants are:

  baseline     -- the validated production optimizer knobs (EXPECTED_PROD_CONFIG)
  knob:*       -- one registered knob flipped away from production at a time,
                  so each row is a marginal ablation, not a confounded bundle
  temp:*       -- sampling-temperature variants: every player's log-space sigma
                  is scaled by a deterministic factor, sweeping how much
                  variance the copula sampler assumes

Like scripts/backtest_walkforward.py, predictions for each slate come only
from the production spec builder as of that slate, so results measure the live
path. Configuration comes from the process environment (DATABASE_URL is
required, or pass --labels-csv/--leaderboards-csv pointing at a verified
corpus-backup snapshot for offline runs); no .env files are loaded. Output
files are written atomically (temp file + os.replace) into --output-dir:

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
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

SEED = 2026
SLOT_MULTIPLIERS = (2.0, 1.8, 1.6, 1.4, 1.2)

# One OptimizeConfig override per registered knob, flipped away from the
# validated production value so each variant isolates one knob's effect.
KNOB_ABLATIONS: dict[str, dict[str, Any]] = {
    "knob:field_same_game_boost_off": {"field_same_game_boost": 1.0},
    "knob:field_same_team_boost_off": {"field_same_team_boost": 1.0},
    "knob:dynamic_team_cap_off": {"dynamic_team_cap": False},
    "knob:duplication_aware_payout_on": {"duplication_aware_payout": True},
    "knob:leverage_weight_0.2": {"leverage_weight": 0.2},
    "knob:ceiling_weight_0.2": {"ceiling_weight": 0.2},
}

# Optimizer-facing production knobs (mirrors EXPECTED_PROD_CONFIG / D88-D92).
BASELINE_OVERRIDES: dict[str, Any] = {
    "field_same_game_boost": 3.0,
    "field_same_team_boost": 2.0,
    "dynamic_team_cap": True,
    "duplication_aware_payout": False,
    "leverage_weight": 0.0,
    "ceiling_weight": 0.0,
}


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
    player_ids: list[int],
    boost_by: dict[int, float],
    rs_by: dict[int, float],
) -> float:
    """Realized contest score for the committed lineup: best realized score
    gets the highest slot multiplier, matching the platform's scoring."""
    members = sorted(
        ((int(pid), rs_by.get(int(pid), 0.0)) for pid in player_ids),
        key=lambda x: -x[1],
    )
    return sum(
        (SLOT_MULTIPLIERS[i] + boost_by.get(pid, 0.0)) * rs
        for i, (pid, rs) in enumerate(members[: len(SLOT_MULTIPLIERS)])
    )


def placement_for_score(our_score: float, lb_scores: list[float]) -> int:
    """1-based placement of ``our_score`` against a real leaderboard."""
    return sum(1 for s in lb_scores if s > our_score) + 1


def summarize_variant(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-slate rows into the summary metrics reported per variant."""
    n = len(rows)
    if n == 0:
        return {"n_slates": 0}
    return {
        "n_slates": n,
        "beat_median_pct": round(100.0 * sum(r["beat_median"] for r in rows) / n, 1),
        "top5_pct": round(100.0 * sum(1 for r in rows if r["placement"] <= 5) / n, 1),
        "top1_pct": round(100.0 * sum(1 for r in rows if r["placement"] == 1) / n, 1),
        "mean_placement": round(sum(r["placement"] for r in rows) / n, 2),
        "mean_gap_vs_top1": round(sum(r["gap"] for r in rows) / n, 3),
        "mean_payout_capture": round(sum(r["payout_capture"] for r in rows) / n, 4),
    }


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
        "Placement and payout capture are measured against the real stored "
        "leaderboard for each slate under the top-20 payout curve. "
        "`payout_capture` is the realized payout divided by the rank-1 payout.",
        "",
        "| variant | slates | beat median | top 5 | top 1 | mean placement "
        "| mean gap vs top 1 | payout capture |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for v in result["variants"]:
        s = v["summary"]
        if s.get("n_slates", 0) == 0:
            lines.append(f"| {v['name']} | 0 | - | - | - | - | - | - |")
            continue
        lines.append(
            f"| {v['name']} | {s['n_slates']} | {s['beat_median_pct']}% "
            f"| {s['top5_pct']}% | {s['top1_pct']}% | {s['mean_placement']} "
            f"| {s['mean_gap_vs_top1']} | {s['mean_payout_capture']} |"
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


def _precompute_slates(
    max_slates: int | None,
    labels_csv: Path | None = None,
    leaderboards_csv: Path | None = None,
    shard: tuple[int, int] | None = None,
) -> dict[str, dict[str, Any]]:
    """Load labels and leaderboards (database, or offline corpus-backup CSVs)
    and build the production sampling and field specs once per eligible
    2026 slate. ``shard=(index, count)`` keeps every count-th slate starting
    at index, so parallel shards partition the slate set exactly."""
    import polars as pl

    from wnba_oracle.scheduler.job2 import _build_specs

    if labels_csv is not None and leaderboards_csv is not None:
        sl = load_labels_csv(labels_csv)
        lb = load_leaderboards_csv(leaderboards_csv)
        # Offline mode has no engine: serve measured drafts from the CSV so
        # the D86 measured-ownership path matches the live path.
        import wnba_oracle.scheduler.job2 as _job2

        measured = drafts_by_slate(sl)
        _job2._load_measured_drafts = lambda sd: measured.get(str(sd), {})
    else:
        from wnba_oracle.db.reads import read_leaderboards, read_slate_labels

        sl = read_slate_labels()
        lb = read_leaderboards()
    slates_2026 = {d for d in sl["slate_date"].unique().to_list() if str(d).startswith("2026-")}
    valid = sorted(slates_2026 & set(lb["slate_date"].unique().to_list()))
    if shard is not None:
        valid = select_shard(valid, shard[0], shard[1])
    if max_slates is not None:
        valid = valid[:max_slates]

    precomputed: dict[str, dict[str, Any]] = {}
    for sd in valid:
        slate = sl.filter(pl.col("slate_date") == sd)
        if slate.filter(pl.col("real_score").is_not_null()).height < 5:
            continue
        lb_scores = lb.filter(pl.col("slate_date") == sd)["score"].to_list()
        if len(lb_scores) < 5:
            continue
        teams = slate["team_key"].unique().to_list()
        team_to_opp = {t: teams[(i + 1) % len(teams)] for i, t in enumerate(teams)}
        boost_by: dict[int, float] = {}
        rs_by: dict[int, float] = {}
        enrichment = []
        for r in slate.iter_rows(named=True):
            pid = int(r["platform_player_id"])
            boost_by[pid] = float(r["card_boost"])
            rs_by[pid] = float(r["real_score"]) if r["real_score"] is not None else 0.0
            enrichment.append(
                {
                    "real_sports_player_id": str(pid),
                    "name": r["display_name"],
                    "team": r["team_key"],
                    "opponent": team_to_opp.get(r["team_key"], "UNK"),
                    "position": "F",
                    "card_boost": boost_by[pid],
                    "features_json": json.dumps({}),
                }
            )
        samps, fields, _ = _build_specs(enrichment, slate_date=sd)
        if len(samps) < 5:
            continue
        precomputed[sd] = {
            "samps": samps,
            "fields": fields,
            "boost_by": boost_by,
            "rs_by": rs_by,
            "lb_scores": sorted(lb_scores, reverse=True),
        }
    return precomputed


def _run_variant(
    variant: dict[str, Any],
    precomputed: dict[str, dict[str, Any]],
    n_samples: int,
) -> list[dict[str, Any]]:
    """Replay every precomputed slate under one variant's configuration."""
    from wnba_oracle.picker.optimize import OptimizeConfig, optimize_lineup
    from wnba_oracle.picker.payout import default_curve_for_regime

    curve = default_curve_for_regime("top_20")
    rows: list[dict[str, Any]] = []
    for sd in sorted(precomputed):
        d = precomputed[sd]
        cfg = OptimizeConfig(
            top_n_filter=min(20, len(d["samps"])),
            n_samples=n_samples,
            n_field_lineups=40,
            seed=SEED,
            max_per_team=2,
            score_offset=2.0,
            **{**BASELINE_OVERRIDES, **variant["overrides"]},
        )
        samps = scale_sigma(d["samps"], variant["sigma_scale"])
        try:
            rec = optimize_lineup(samps, d["fields"], curve, cfg=cfg)
        except Exception:
            continue
        our = score_lineup(list(rec.player_ids), d["boost_by"], d["rs_by"])
        lb_scores = d["lb_scores"]
        placement = placement_for_score(our, lb_scores)
        field_size = len(lb_scores)
        top1_payout = curve.payout_for_rank(1, field_size)
        payout = curve.payout_for_rank(placement, field_size)
        median = lb_scores[min(len(lb_scores) // 2, len(lb_scores) - 1)]
        rows.append(
            {
                "slate_date": str(sd),
                "our_score": round(our, 3),
                "placement": placement,
                "field_size": field_size,
                "gap": round(lb_scores[0] - our, 3),
                "beat_median": 1 if our > median else 0,
                "payout": round(payout, 4),
                "payout_capture": round(payout / top1_payout, 4) if top1_payout > 0 else 0.0,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--temperature-variants", type=int, default=4)
    parser.add_argument("--n-samples", type=int, default=80)
    parser.add_argument("--max-slates", type=int, default=None)
    parser.add_argument("--labels-csv", type=Path, default=None)
    parser.add_argument("--leaderboards-csv", type=Path, default=None)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument(
        "--variant",
        action="append",
        default=None,
        help="Run only the named variant(s); repeatable. Default: full grid.",
    )
    args = parser.parse_args()

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

    os.environ.setdefault(
        "WNBA_ORACLE_MODEL_ARTIFACT_SHA",
        "94f8e8606dab4d48652929bb3884fb9152e1abc766eeb2c2d86559f4318676cd",
    )
    os.environ.setdefault("PAYOUT_REGIME", "top_20")
    os.environ.setdefault("OPTIMIZER_MAX_PER_TEAM", "2")
    os.environ.setdefault("FIELD_MEASURED_OWNERSHIP_ENABLED", "true")

    import structlog

    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    print("Precomputing production specs per slate...")
    precomputed = _precompute_slates(
        args.max_slates,
        args.labels_csv,
        args.leaderboards_csv,
        shard=(args.shard_index, args.shard_count),
    )
    print(f"{len(precomputed)} slates eligible.")
    if not precomputed:
        print("No eligible slates; nothing to benchmark.", file=sys.stderr)
        return 1

    grid = build_variant_grid(args.temperature_variants)
    if args.variant:
        wanted = set(args.variant)
        unknown = wanted - {v["name"] for v in grid}
        if unknown:
            print(f"unknown variant name(s): {sorted(unknown)}", file=sys.stderr)
            return 2
        grid = [v for v in grid if v["name"] in wanted]
    variants: list[dict[str, Any]] = []
    for i, variant in enumerate(grid, 1):
        print(f"[{i}/{len(grid)}] {variant['name']}")
        rows = _run_variant(variant, precomputed, args.n_samples)
        variants.append(
            {
                "name": variant["name"],
                "overrides": variant["overrides"],
                "sigma_scale": variant["sigma_scale"],
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
            "temperature_variants": args.temperature_variants,
            "shard_index": args.shard_index,
            "shard_count": args.shard_count,
            "offline_csv": bool(offline),
        },
        "variants": variants,
    }
    out = args.output_dir
    atomic_write_text(out / "benchmark_results.json", json.dumps(result, indent=2) + "\n")
    atomic_write_text(out / "MODEL_RESEARCH_BENCHMARK.md", render_markdown(result))
    print(f"Wrote {out / 'benchmark_results.json'}")
    print(f"Wrote {out / 'MODEL_RESEARCH_BENCHMARK.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

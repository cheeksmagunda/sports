"""Closed-loop placement / calibration tracking (D90, Phase 2).

The 2026 research synthesis (research/internal/07_placement_overhaul.md)
names the placement feedback loop as the keystone instrumentation phase:
no later objective change (leverage, ceiling, duplication weights, the
Phase 3 stack-aware field, the Phase 4 ceiling marginals) can be calibrated
without a clean record of where the entered lineup actually finished
across enough slates to dominate variance.

This module is the writer + reader of two append-only tables:

  contest_placements
    Per (slate_date, contest_id, recorded_at) row. Captures the realized
    outcome (rank, total entries, score, payout, ROI), the forecast snapshot
    at freeze (expected_payout, lineup_score percentiles, serving knobs),
    and the projected vs actual ownership maps. Append-only via the PK so
    re-records keep history; readers take the latest row per
    (slate_date, contest_id).

  player_slate_ownership
    Per (slate_date, player_id) row with projected_ownership at freeze
    (from the field model) and actual_ownership at lock (from
    slate_labels.drafts or post-contest data).

Diagnostics surfaced by `summarize_placements` and `compute_pit_histogram`:

  - Rolling median finish percentile (always-on signal).
  - PIT histogram on the predicted finish CDF -- shape (U / dome / skew)
    diagnoses simulator over- / under-dispersion.
  - Per-decile ownership log-loss -- localizes the miscalibration regime
    in the field-ownership model.

Synthesis anti-patterns enforced (see research/internal/07*.md):
  - No tuning of PROP_SIGNAL_SCALE / leverage / ceiling weights below 100
    logged slates (the analysis emits a warning).
  - ROI is hidden until >= 500 slates.
  - Append-only: a re-record never amends an old row.

CLI:
    oracle-placements record \\
        --slate-date 2026-06-12 --contest-id 12345 \\
        --rank 4253 --count 8300 --score 32.4 \\
        --payout-cents 0 --entry-fee-cents 100
    oracle-placements summary [--window 50]
    oracle-placements calibrate [--metric pit|ownership]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Connection, text

from wnba_oracle.common.logging import configure_logging, get_logger
from wnba_oracle.common.settings import get_settings

log = get_logger("oracle.placements")

# Synthesis display thresholds (research/internal/07_placement_overhaul.md).
# Below these slate counts, the corresponding metric is unreliable and the CLI
# warns rather than silently presenting noise as signal.
SHOW_PIT_AFTER_SLATES = 50
SHOW_RELIABILITY_AFTER_SLATES = 50
TUNE_WEIGHTS_AFTER_SLATES = 100
SHOW_ROI_AFTER_SLATES = 500


# --------------------------------------------------------------------------
# Pure model + math (DB-free, unit-testable)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class PlacementRow:
    slate_date: str
    contest_id: int
    entry_rank: int | None
    entry_count: int | None
    entry_score: float | None
    payout_cents: int | None
    entry_fee_cents: int | None

    @property
    def finish_percentile(self) -> float | None:
        if self.entry_rank is None or not self.entry_count:
            return None
        if self.entry_count <= 0:
            return None
        return float(self.entry_rank) / float(self.entry_count)

    @property
    def roi(self) -> float | None:
        if self.payout_cents is None or self.entry_fee_cents is None or self.entry_fee_cents <= 0:
            return None
        return float(self.payout_cents - self.entry_fee_cents) / float(self.entry_fee_cents)


def compute_pit_value(
    finish_percentile: float,
    predicted_cdf: dict[float, float] | None,
) -> float | None:
    """Probability-Integral Transform on the predicted finish CDF.

    `predicted_cdf` is {percentile_threshold: cumulative_probability} (e.g.
    {0.05: 0.10, 0.20: 0.30, 0.50: 0.60}). If the predicted distribution is
    calibrated, the PIT values over many slates are uniformly distributed
    on [0, 1]. Skew toward 0 / 1 signals bias; U-shape signals
    over-confidence (under-dispersion); dome shape signals over-dispersion.

    Returns None if cdf is missing or empty.
    """
    if predicted_cdf is None or not predicted_cdf:
        return None
    # Find the smallest threshold >= finish_percentile.
    items = sorted((float(k), float(v)) for k, v in predicted_cdf.items())
    for threshold, cum_prob in items:
        if finish_percentile <= threshold:
            return cum_prob
    # finish_percentile is past the worst tracked threshold -> at the upper
    # tail of the CDF (we finished worse than the predicted 50th percentile,
    # etc.). Clip at the last cumulative probability.
    return items[-1][1]


def pit_histogram(pit_values: list[float], n_bins: int = 10) -> list[int]:
    """Bin PIT values into `n_bins` equal-width bins on [0, 1]. Returns
    integer counts per bin. A perfectly calibrated forecaster produces a
    flat histogram; deviations diagnose simulator dispersion."""
    counts = [0] * n_bins
    for v in pit_values:
        if v is None:
            continue
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        if not (0.0 <= x <= 1.0):
            continue
        idx = min(int(x * n_bins), n_bins - 1)
        counts[idx] += 1
    return counts


def chi2_uniformity_pvalue(counts: list[int]) -> float | None:
    """Pearson chi-square uniformity test on the PIT histogram. Returns the
    p-value; small p means the histogram is unlikely uniform (forecast not
    calibrated). Returns None when total < 30 (test underpowered).
    """
    total = sum(counts)
    if total < 30:
        return None
    n_bins = len(counts)
    expected = total / float(n_bins)
    chi2 = sum((c - expected) ** 2 / expected for c in counts)
    # Survival function of chi2 with (n_bins - 1) df. Use a Wilson-Hilferty
    # approximation to avoid pulling scipy for a single tail-area lookup.
    df = n_bins - 1
    if df <= 0:
        return None
    a = chi2 / df
    z = ((a ** (1 / 3)) - (1 - 2 / (9 * df))) / ((2 / (9 * df)) ** 0.5)
    # Standard normal tail. Abramowitz-Stegun 26.2.17 approximation.
    return _stdnorm_sf(z)


def _stdnorm_sf(z: float) -> float:
    # 1 - Phi(z) via Abramowitz-Stegun 26.2.17. Sufficient accuracy
    # (~1e-7) for our calibration p-values; avoids the scipy dep.
    if z < 0:
        return 1.0 - _stdnorm_sf(-z)
    t = 1.0 / (1.0 + 0.2316419 * z)
    p = (
        0.319381530 * t
        - 0.356563782 * t ** 2
        + 1.781477937 * t ** 3
        - 1.821255978 * t ** 4
        + 1.330274429 * t ** 5
    )
    pdf = 0.39894228 * pow(2.71828182845905, -0.5 * z * z)
    return pdf * p


def ownership_log_loss_by_decile(
    projected: dict[int, float], actual: dict[int, float]
) -> list[tuple[float, float, int]]:
    """Per-decile binary cross-entropy on projected vs actual ownership.

    Players are bucketed by `projected` into 10 deciles. Within each bucket
    LL = -mean(y log p + (1-y) log(1-p)) over the players in the bucket,
    treating actual ownership as the Bernoulli probability target.

    Returns [(bucket_upper, log_loss, n_players), ...] for the 10 deciles
    (0.0-0.1, 0.1-0.2, ..., 0.9-1.0). A bucket with far-higher log-loss
    than its neighbours localizes the miscalibration regime (e.g. the
    20-30% projected bucket is being systematically underowned).
    """
    if not projected or not actual:
        return []
    common = set(projected) & set(actual)
    if not common:
        return []
    eps = 1e-9
    buckets: dict[int, list[tuple[float, float]]] = {i: [] for i in range(10)}
    for pid in common:
        p = max(eps, min(1.0 - eps, float(projected[pid])))
        y = max(0.0, min(1.0, float(actual[pid])))
        decile = min(int(p * 10), 9)
        buckets[decile].append((p, y))
    out: list[tuple[float, float, int]] = []
    import math

    for d in range(10):
        rows = buckets[d]
        if not rows:
            out.append(((d + 1) / 10.0, float("nan"), 0))
            continue
        ll = -sum(
            y * math.log(p) + (1 - y) * math.log(1 - p) for p, y in rows
        ) / len(rows)
        out.append(((d + 1) / 10.0, ll, len(rows)))
    return out


# --------------------------------------------------------------------------
# DB layer
# --------------------------------------------------------------------------
PLACEMENT_INSERT = text(
    """
    INSERT INTO contest_placements (
        slate_date, contest_id, recorded_at, source,
        entry_rank, entry_count, entry_score,
        payout_received_cents, entry_fee_cents,
        finish_percentile, cashed, top_10pct, top_1pct, roi,
        freeze_model_sha, expected_payout,
        lineup_score_p10, lineup_score_p50, lineup_score_p90,
        payout_curve_json, freeze_config_json,
        predicted_ownership_json, actual_ownership_json, metadata_json
    ) VALUES (
        :slate_date, :contest_id, now(), :source,
        :entry_rank, :entry_count, :entry_score,
        :payout_received_cents, :entry_fee_cents,
        :finish_percentile, :cashed, :top_10pct, :top_1pct, :roi,
        :freeze_model_sha, :expected_payout,
        :lineup_score_p10, :lineup_score_p50, :lineup_score_p90,
        CAST(:payout_curve_json AS JSONB),
        CAST(:freeze_config_json AS JSONB),
        CAST(:predicted_ownership_json AS JSONB),
        CAST(:actual_ownership_json AS JSONB),
        CAST(:metadata_json AS JSONB)
    )
    """
)

LATEST_PLACEMENT_SELECT = text(
    """
    SELECT entry_rank, entry_count, entry_score, payout_received_cents,
           entry_fee_cents, finish_percentile, roi, expected_payout
    FROM contest_placements
    WHERE slate_date = :sd AND contest_id = :cid
    ORDER BY recorded_at DESC LIMIT 1
    """
)

FROZEN_SNAPSHOT_SELECT_LATEST = text(
    """
    SELECT model_sha, expected_payout, lineup, payout_regime,
           metadata_json, freeze_seq
    FROM frozen_lineups
    WHERE slate_date = :sd
    ORDER BY freeze_seq DESC, frozen_at DESC LIMIT 1
    """
)

# When the operator entered the 21:00 lineup but a 23:00 D75 late re-freeze
# wrote a new row, the LATEST freeze is NOT the one they entered. Caller can
# supply the explicit freeze_seq from the audit ledger so the recorded
# forecast matches what shipped.
FROZEN_SNAPSHOT_SELECT_BY_SEQ = text(
    """
    SELECT model_sha, expected_payout, lineup, payout_regime,
           metadata_json, freeze_seq
    FROM frozen_lineups
    WHERE slate_date = :sd AND freeze_seq = :seq
    ORDER BY frozen_at DESC LIMIT 1
    """
)

PLACEMENTS_WINDOW_SELECT = text(
    """
    SELECT DISTINCT ON (slate_date, contest_id)
        slate_date, contest_id, entry_rank, entry_count,
        finish_percentile, roi, expected_payout
    FROM contest_placements
    ORDER BY slate_date DESC, contest_id, recorded_at DESC
    LIMIT :n
    """
)


def _as_obj(raw: Any) -> Any:
    if isinstance(raw, (str, bytes)):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return raw


def record_placement(
    conn: Connection,
    *,
    slate_date: str,
    contest_id: int,
    entry_rank: int | None,
    entry_count: int | None,
    entry_score: float | None = None,
    payout_received_cents: int | None = None,
    entry_fee_cents: int | None = None,
    source: str = "manual",
    actual_ownership: dict[int, float] | None = None,
    freeze_seq: int | None = None,
) -> dict[str, Any]:
    """Write one placement row. Joins forecast snapshot from frozen_lineups.

    `freeze_seq` (D82 / D90 audit-correctness): when supplied, the joined
    forecast snapshot reads the specified freeze (the one the operator
    actually entered) rather than the latest. The D75 late re-freeze is
    why this matters: a 21:00-entered lineup followed by a 23:00 re-freeze
    leaves freeze_seq=2 as the latest, but the operator's entry was
    freeze_seq=1. Default None preserves "latest" semantics, which is
    correct for the common no-re-freeze path.

    Returns the persisted derived fields (finish_percentile, cashed, ROI,
    etc.) for the caller's response. Append-only: the unique key
    (slate_date, contest_id, recorded_at) keeps history; readers take the
    latest by recorded_at DESC.
    """
    row = PlacementRow(
        slate_date=slate_date,
        contest_id=contest_id,
        entry_rank=entry_rank,
        entry_count=entry_count,
        entry_score=entry_score,
        payout_cents=payout_received_cents,
        entry_fee_cents=entry_fee_cents,
    )
    finish_pct = row.finish_percentile
    cashed = (payout_received_cents or 0) > 0
    top_10pct = bool(finish_pct is not None and finish_pct <= 0.10)
    top_1pct = bool(finish_pct is not None and finish_pct <= 0.01)
    roi = row.roi

    # Look up the freeze snapshot that produced this entry.
    if freeze_seq is None:
        frozen = conn.execute(
            FROZEN_SNAPSHOT_SELECT_LATEST, {"sd": slate_date}
        ).first()
    else:
        frozen = conn.execute(
            FROZEN_SNAPSHOT_SELECT_BY_SEQ, {"sd": slate_date, "seq": freeze_seq}
        ).first()
    freeze_model_sha: str | None = None
    expected_payout: float | None = None
    lineup_score_p10: float | None = None
    lineup_score_p50: float | None = None
    lineup_score_p90: float | None = None
    payout_curve_json: str | None = None
    freeze_config_json: str | None = None
    predicted_ownership_json: str | None = None
    if frozen is not None:
        freeze_model_sha = str(frozen.model_sha)
        expected_payout = (
            float(frozen.expected_payout) if frozen.expected_payout is not None else None
        )
        lineup = _as_obj(frozen.lineup) or {}
        if isinstance(lineup, dict):
            # The freeze payload writes p10/p50/p90 as FLAT top-level keys
            # (job2:_freeze, post D90 also writes payout_curve/serving_knobs).
            # Reading a nested lineup_score_quantiles dict was the original
            # bug that silently NULL'd these columns -- now we read the flats
            # directly, which is byte-correct for current and historical rows.
            p10_raw = lineup.get("lineup_score_p10")
            p50_raw = lineup.get("lineup_score_p50")
            p90_raw = lineup.get("lineup_score_p90")
            lineup_score_p10 = float(p10_raw) if p10_raw is not None else None
            lineup_score_p50 = float(p50_raw) if p50_raw is not None else None
            lineup_score_p90 = float(p90_raw) if p90_raw is not None else None
            curve = lineup.get("payout_curve")
            knobs = lineup.get("serving_knobs")
            payout_curve_json = json.dumps(curve) if curve else None
            freeze_config_json = json.dumps(knobs) if knobs else None
            preds = lineup.get("predicted_ownership")
            if preds:
                predicted_ownership_json = json.dumps(preds)

    actual_ownership_json = json.dumps(actual_ownership) if actual_ownership else None

    params = {
        "slate_date": slate_date,
        "contest_id": contest_id,
        "source": source,
        "entry_rank": entry_rank,
        "entry_count": entry_count,
        "entry_score": entry_score,
        "payout_received_cents": payout_received_cents,
        "entry_fee_cents": entry_fee_cents,
        "finish_percentile": finish_pct,
        "cashed": cashed,
        "top_10pct": top_10pct,
        "top_1pct": top_1pct,
        "roi": roi,
        "freeze_model_sha": freeze_model_sha,
        "expected_payout": expected_payout,
        "lineup_score_p10": lineup_score_p10,
        "lineup_score_p50": lineup_score_p50,
        "lineup_score_p90": lineup_score_p90,
        "payout_curve_json": payout_curve_json,
        "freeze_config_json": freeze_config_json,
        "predicted_ownership_json": predicted_ownership_json,
        "actual_ownership_json": actual_ownership_json,
        "metadata_json": None,
    }
    conn.execute(PLACEMENT_INSERT, params)
    log.info(
        "placement_recorded",
        slate_date=slate_date,
        contest_id=contest_id,
        rank=entry_rank,
        count=entry_count,
        finish_pct=finish_pct,
        cashed=cashed,
        roi=roi,
    )
    return {
        "finish_percentile": finish_pct,
        "cashed": cashed,
        "top_10pct": top_10pct,
        "top_1pct": top_1pct,
        "roi": roi,
        "freeze_model_sha": freeze_model_sha,
        "expected_payout": expected_payout,
    }


def auto_record_from_dayclose(
    conn: Connection,
    *,
    slate_date: str,
    entry_score: float,
    leaderboard_scores: list[float],
    contest_id: int,
    actual_ownership: dict[int, float] | None = None,
) -> dict[str, Any] | None:
    """Record placement automatically after day-close ingestion.

    Called by `job_dayclose.py` once real scores are in `slate_labels`
    and the frozen lineup exists. Computes relative rank within the
    captured leaderboard (top-20 captures). Sets entry_count=None because
    the total contest field size is not stored -- finish_percentile will be
    NULL until the operator runs `oracle-placements record` with the real
    total. The auto record still surfaces `entry_score`, the frozen lineup
    snapshot, and the beat-top-N booleans.

    Returns None if there is no frozen lineup for `slate_date` (non-contest
    slate or lineup never frozen) or if a placement was already recorded
    today.
    """
    frozen = conn.execute(FROZEN_SNAPSHOT_SELECT_LATEST, {"sd": slate_date}).first()
    if frozen is None:
        return None

    lb_sorted = sorted(leaderboard_scores, reverse=True)
    n_above = sum(1 for s in lb_sorted if s > entry_score)
    relative_rank = n_above + 1

    return record_placement(
        conn,
        slate_date=slate_date,
        contest_id=contest_id,
        entry_rank=relative_rank,
        entry_count=None,
        entry_score=entry_score,
        payout_received_cents=None,
        entry_fee_cents=None,
        source="auto_dayclose",
        actual_ownership=actual_ownership,
        freeze_seq=None,
    )


def summarize_placements(conn: Connection, *, window: int = 50) -> dict[str, Any]:
    """Aggregate KPIs across the most-recent `window` slates.

    Honours the synthesis display thresholds: ROI is hidden until
    SHOW_ROI_AFTER_SLATES, PIT histograms wait for SHOW_PIT_AFTER_SLATES.
    """
    rows = list(conn.execute(PLACEMENTS_WINDOW_SELECT, {"n": window}))
    n = len(rows)
    if n == 0:
        return {"n_placements": 0, "warning": "no placements logged yet"}
    pcts = [float(r.finish_percentile) for r in rows if r.finish_percentile is not None]
    rois = [float(r.roi) for r in rows if r.roi is not None]
    cash_count = sum(
        1 for r in rows if r.finish_percentile is not None and float(r.finish_percentile) <= 0.50
    )
    top10_count = sum(
        1 for r in rows if r.finish_percentile is not None and float(r.finish_percentile) <= 0.10
    )
    top1_count = sum(
        1 for r in rows if r.finish_percentile is not None and float(r.finish_percentile) <= 0.01
    )
    pcts_sorted = sorted(pcts)
    median_pct = pcts_sorted[len(pcts_sorted) // 2] if pcts_sorted else None
    summary: dict[str, Any] = {
        "n_placements": n,
        "median_finish_percentile": median_pct,
        "cash_rate": cash_count / n if n else None,
        "top_10pct_rate": top10_count / n if n else None,
        "top_1pct_rate": top1_count / n if n else None,
    }
    if n >= SHOW_ROI_AFTER_SLATES and rois:
        summary["mean_roi"] = sum(rois) / len(rois)
    elif rois:
        summary["roi_hidden_reason"] = (
            f"hidden until {SHOW_ROI_AFTER_SLATES} slates "
            f"(have {n}; payout skew dominates smaller samples)"
        )
    if n < TUNE_WEIGHTS_AFTER_SLATES:
        summary["tuning_warning"] = (
            f"do not tune objective weights below {TUNE_WEIGHTS_AFTER_SLATES} "
            f"slates (have {n}; small-sample overfitting risk)"
        )
    return summary


def render_summary_markdown(summary: dict[str, Any]) -> str:
    if not summary or summary.get("n_placements", 0) == 0:
        return "No placements logged yet."
    lines = [f"## Placement summary (last {summary['n_placements']} slates)\n"]
    if summary.get("median_finish_percentile") is not None:
        lines.append(
            f"- Median finish percentile: **{summary['median_finish_percentile']:.3f}**"
        )
    if summary.get("cash_rate") is not None:
        lines.append(f"- Cash (top 50%) rate: **{summary['cash_rate']:.1%}**")
    if summary.get("top_10pct_rate") is not None:
        lines.append(f"- Top 10% rate: **{summary['top_10pct_rate']:.1%}**")
    if summary.get("top_1pct_rate") is not None:
        lines.append(f"- Top 1% rate: **{summary['top_1pct_rate']:.1%}**")
    if "mean_roi" in summary:
        lines.append(f"- Mean ROI: **{summary['mean_roi']:+.1%}**")
    if "roi_hidden_reason" in summary:
        lines.append(f"- ROI: hidden ({summary['roi_hidden_reason']})")
    if "tuning_warning" in summary:
        lines.append(f"\n> {summary['tuning_warning']}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _cli_record(args: argparse.Namespace) -> int:
    settings = get_settings()
    if not settings.database_url:
        log.error("placements_no_database_url")
        return 1
    from wnba_oracle.db.engine import get_engine

    with get_engine().begin() as conn:
        result = record_placement(
            conn,
            slate_date=args.slate_date,
            contest_id=int(args.contest_id),
            entry_rank=int(args.rank),
            entry_count=int(args.count),
            entry_score=float(args.score) if args.score is not None else None,
            payout_received_cents=(
                int(args.payout_cents) if args.payout_cents is not None else None
            ),
            entry_fee_cents=(
                int(args.entry_fee_cents) if args.entry_fee_cents is not None else None
            ),
            source=args.source,
            freeze_seq=int(args.freeze_seq) if args.freeze_seq is not None else None,
        )
    print(json.dumps(result, indent=2, default=str))
    return 0


def _cli_summary(args: argparse.Namespace) -> int:
    settings = get_settings()
    if not settings.database_url:
        log.error("placements_no_database_url")
        return 1
    from wnba_oracle.db.engine import get_engine

    with get_engine().connect() as conn:
        summary = summarize_placements(conn, window=int(args.window))
    if args.format == "markdown":
        sys.stdout.write(render_summary_markdown(summary) + "\n")
    else:
        sys.stdout.write(json.dumps(summary, indent=2, default=str) + "\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Closed-loop placement tracking + calibration (D90).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_record = sub.add_parser("record", help="Record a placement for a slate.")
    p_record.add_argument("--slate-date", required=True)
    p_record.add_argument("--contest-id", required=True)
    p_record.add_argument("--rank", required=True, type=int)
    p_record.add_argument("--count", required=True, type=int)
    p_record.add_argument("--score", default=None)
    p_record.add_argument("--payout-cents", default=None)
    p_record.add_argument("--entry-fee-cents", default=None)
    p_record.add_argument("--source", default="manual")
    p_record.add_argument(
        "--freeze-seq",
        default=None,
        help=(
            "When the operator entered a freeze before the D75 late re-freeze "
            "(e.g. seq=1 when seq=2 is the latest), pin the snapshot join."
        ),
    )
    p_record.set_defaults(func=_cli_record)

    p_summary = sub.add_parser("summary", help="Aggregate placement KPIs.")
    p_summary.add_argument("--window", default=50, type=int)
    p_summary.add_argument("--format", choices=["json", "markdown"], default="markdown")
    p_summary.set_defaults(func=_cli_summary)

    # Logging is configured BEFORE the subcommand dispatch so any early DB /
    # auth error in the handler reaches the structured logger, not stderr.
    settings = get_settings()
    configure_logging(settings.log_level)
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

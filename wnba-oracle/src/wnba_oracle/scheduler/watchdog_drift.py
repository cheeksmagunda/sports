"""Watchdog rolling prediction-drift metrics (dayclose-only).

Extracted from watchdog.py. Reads the last N *finalized* slates and
reports (a) Pearson correlation between per-pick freeze-time pred_p50
and realized real_score, and (b) rolling median gap between our lineup
score and the top-20 median. Baselines from D77 walk-forward + the
2026-07-03 loss-ledger snapshot; alert only on materially worse than
baseline (silent when steady-state, even though steady-state is not
healthy -- an operator already knows).
"""

from __future__ import annotations

import json

from sqlalchemy import text

from wnba_oracle.common.logging import get_logger
from wnba_oracle.db.engine import get_engine
from wnba_oracle.eval.contest_score import committed_lineup_score
from wnba_oracle.scheduler.watchdog import SEVERITY_WARN, WatchdogEvent

log = get_logger("oracle.watchdog")

DRIFT_WINDOW = 20
DRIFT_CORR_WARN = 0.35  # D77 walk-forward baseline was 0.554
DRIFT_MEDIAN_GAP_WARN = -25.0  # loss-ledger baseline ~-17

# 2026-08-03: the corr alert fired on 15-20 pick pairs for a month straight and
# every reading was statistically indistinguishable from both the pooled history
# (0.408 over 95 pairs) and the 0.554 baseline it was compared against. At
# r=0.285, n=20 the 95% CI is [-0.180, +0.646], which also contains zero.
#
# Minimum n to separate DRIFT_CORR_WARN from the baseline at 95%, via Fisher z:
#   atanh(0.554) - atanh(0.35) = 0.2589;  1.96 / sqrt(n - 3) <= 0.2589  =>  n >= 61
#
# DRIFT_WINDOW was 10, capping pairs at 50, so the check could never reach that
# power. Window raised to 20 (max 100 pairs) and the alert now holds fire below
# the threshold rather than reporting noise as a retrain signal.
#
# Note this correlation is taken over the five optimizer-selected picks only,
# whose predicted spread is range-restricted (sd 1.072) against a full-width
# realized spread. It is not the same estimator as the D77 full-corpus
# walk-forward figure, so 0.35 remains a rough guide, not a like-for-like bound.
DRIFT_MIN_PICK_PAIRS = 61

DRIFT_WINDOW_Q = text(
    """
    SELECT DISTINCT ON (f.slate_date)
        f.slate_date::text AS slate_date,
        f.freeze_seq,
        f.lineup
    FROM frozen_lineups f
    WHERE EXISTS (
        SELECT 1 FROM contest_leaderboards cl
        WHERE cl.slate_date = f.slate_date::text
    )
    AND EXISTS (
        SELECT 1 FROM slate_labels l
        WHERE l.slate_date = f.slate_date::text
          AND l.real_score IS NOT NULL
    )
    ORDER BY f.slate_date DESC, f.frozen_at DESC, f.id DESC
    LIMIT :n
    """
)

DRIFT_LABELS_Q = text(
    """
    SELECT platform_player_id, real_score, card_boost
    FROM slate_labels
    WHERE slate_date = :sd AND real_score IS NOT NULL
    """
)

DRIFT_LB_Q = text(
    "SELECT score FROM contest_leaderboards WHERE slate_date = :sd ORDER BY rank ASC LIMIT 20"
)


def _pearson(pairs: list[tuple[float, float]]) -> float | None:
    """Pearson correlation over (x, y) pairs. Returns None when the sample
    is degenerate (n<3) or either variable has zero variance."""
    n = len(pairs)
    if n < 3:
        return None
    mean_x = sum(p[0] for p in pairs) / n
    mean_y = sum(p[1] for p in pairs) / n
    num = sum((p[0] - mean_x) * (p[1] - mean_y) for p in pairs)
    denom_x = sum((p[0] - mean_x) ** 2 for p in pairs)
    denom_y = sum((p[1] - mean_y) ** 2 for p in pairs)
    if denom_x <= 0 or denom_y <= 0:
        return None
    return num / (denom_x * denom_y) ** 0.5


def compute_drift_metrics(
    window: int = DRIFT_WINDOW,
) -> dict[str, float | int | None] | None:
    """Read the last ``window`` finalized slates and return calibration
    metrics. Pure(-ish) helper: no clock, no logging, no emit -- unit-testable
    over a live engine. Returns None when fewer than 3 slates qualify."""
    eng = get_engine()
    with eng.connect() as conn:
        rows = conn.execute(DRIFT_WINDOW_Q, {"n": window}).fetchall()
        if len(rows) < 3:
            return None

        pick_pairs: list[tuple[float, float]] = []
        score_gaps: list[float] = []
        n_slates_scored = 0
        n_lb_missing = 0

        for row in rows:
            sd = row.slate_date
            lu = row.lineup
            lu = lu if isinstance(lu, dict) else json.loads(lu)
            pids: list[int] = [int(x) for x in (lu.get("player_ids") or [])]
            per = lu.get("per_player") or []
            if not pids or not per:
                continue
            pred_by_pid: dict[int, float] = {}
            for entry in per:
                try:
                    pred_by_pid[int(entry["player_id"])] = float(
                        entry.get("pred_real_score_p50") or 0.0
                    )
                except (KeyError, TypeError, ValueError):
                    continue

            labels = {
                int(r._mapping["platform_player_id"]): (
                    float(r._mapping["real_score"] or 0.0),
                    float(r._mapping["card_boost"] or 0.0),
                )
                for r in conn.execute(DRIFT_LABELS_Q, {"sd": sd}).fetchall()
            }
            for pid, pred in pred_by_pid.items():
                if pid in labels:
                    pick_pairs.append((pred, labels[pid][0]))

            # Per-slate gap vs top-20 median.
            all_pids_scored = all(pid in labels for pid in pids)
            if not all_pids_scored:
                continue
            our_score = committed_lineup_score(
                pids,
                {pid: labels[pid][0] for pid in pids},
                {pid: labels[pid][1] for pid in pids},
            )

            lb_rows = conn.execute(DRIFT_LB_Q, {"sd": sd}).fetchall()
            if not lb_rows:
                n_lb_missing += 1
                continue
            lb_scores = sorted(float(r._mapping["score"]) for r in lb_rows)
            median = lb_scores[len(lb_scores) // 2]
            score_gaps.append(our_score - median)
            n_slates_scored += 1

    if n_slates_scored < 3:
        return None
    score_gaps_sorted = sorted(score_gaps)
    median_gap = score_gaps_sorted[len(score_gaps_sorted) // 2]
    return {
        "n_slates": n_slates_scored,
        "n_pick_pairs": len(pick_pairs),
        "pick_pred_vs_real_corr": _pearson(pick_pairs),
        "median_score_gap": median_gap,
        "worst_score_gap": min(score_gaps),
        "best_score_gap": max(score_gaps),
    }


def _check_prediction_drift(slate_date: str, *, window: int = DRIFT_WINDOW) -> list[WatchdogEvent]:
    """Rolling-window calibration alert (dayclose-only).

    Fires when either signal materially worsens:
    - Pearson corr(pred_p50, realized rs) across our five picks over the
      window drops below DRIFT_CORR_WARN. D77 walk-forward baseline was
      0.554; sub-0.35 is a 30%+ degradation.
    - Rolling median (our_score - top20_median) drops below
      DRIFT_MEDIAN_GAP_WARN. The 2026-07-03 loss-ledger baseline sat at
      ~-17; sub-25 means the lineup got materially worse.

    Steady-state under baseline does NOT fire -- the operator already
    knows the state from the loss ledger. Fires only on regression from
    baseline.
    """
    try:
        m = compute_drift_metrics(window=window)
    except Exception as exc:
        log.warning("drift_check_failed", reason=str(exc)[:120])
        return []
    if not m:
        return []
    events: list[WatchdogEvent] = []
    corr = m.get("pick_pred_vs_real_corr")
    n_pairs = int(m.get("n_pick_pairs") or 0)
    if corr is not None and float(corr) < DRIFT_CORR_WARN:
        if n_pairs < DRIFT_MIN_PICK_PAIRS:
            log.info(
                "drift_corr_underpowered",
                n_pick_pairs=n_pairs,
                min_pairs=DRIFT_MIN_PICK_PAIRS,
                corr=round(float(corr), 3),
            )
        else:
            events.append(
                WatchdogEvent(
                    slate_date=slate_date,
                    trigger="prediction_calibration_drift",
                    severity=SEVERITY_WARN,
                    payload={
                        "window": m["n_slates"],
                        "n_pick_pairs": n_pairs,
                        "corr": round(float(corr), 3),
                        "threshold": DRIFT_CORR_WARN,
                        "baseline_d77": 0.554,
                        "note": (
                            "Rolling Pearson corr(pred_p50, realized) over the five "
                            "picks has dropped below the D77-baseline threshold on a "
                            "sample large enough to separate the two; retrain candidate. "
                            "Range-restricted estimator, not like-for-like with D77."
                        ),
                    },
                )
            )
    gap = m.get("median_score_gap")
    if gap is not None and float(gap) < DRIFT_MEDIAN_GAP_WARN:
        events.append(
            WatchdogEvent(
                slate_date=slate_date,
                trigger="lineup_gap_regression",
                severity=SEVERITY_WARN,
                payload={
                    "window": m["n_slates"],
                    "median_gap": round(float(gap), 2),
                    "worst_gap": round(float(m["worst_score_gap"] or 0.0), 2),
                    "threshold": DRIFT_MEDIAN_GAP_WARN,
                    "baseline_ledger_2026_07_03": -17.0,
                    "note": (
                        "10-slate median (our_score - top20_median) has "
                        "worsened past the 2026-07-03 loss-ledger baseline."
                    ),
                },
            )
        )
    log.info(
        "drift_metrics",
        window=m["n_slates"],
        corr=m.get("pick_pred_vs_real_corr"),
        median_gap=m.get("median_score_gap"),
    )
    return events

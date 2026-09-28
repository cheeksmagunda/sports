"""Replay the F-only EB cohort bug against the 2026-09-27 freeze (#592).

Reads immutable post-slate dossiers (the live ``/dossier/{date}`` payload
saved to disk). Does not open a database and does not call Real Sports.

Modes on each slate:
  eb_bug        real position, missing G/C cohort mean treated as 0.0
                (the serve math that froze 2026-09-27)
  eb_fallback   real position, missing cohort uses the trained F mean
  eb_hardcoded  every row forced to position F (same base as fallback
                when the artifact only stores F)
  heads         ``serve_primary=heads`` (LightGBM). That path still stamps
                position F inside ``_predict_heads_for_pool``.
  eb_empirical  prior-slate HV mean by real cohort, plus the stored alpha.
                Not a retrain. Keeps the F-centered alpha, so a lower C
                mean drops A'ja-class centers. Rejected.
  eb_hv_aligned real cohort mean AND the stored alpha shifted by the
                same gap. A player already in the artifact was shrunk
                against F. Moving only the mean (eb_empirical) drops
                A'ja-class centers. Shifting the alpha with the mean keeps
                her board level. Blank positions inherit her modal pool
                position. Focus scores stay out of the means.

The focus slate also re-runs the production total-draft-value optimizer
(seed 1729, 1000 samples). Field-lineup count is 1 because that objective
does not read field scores. ``leverage_weight`` is compared at 0.28, 0.0,
and 0.40 on the fallback predictions.

Grading uses ``slate_labels.real_score`` from the dossier. A lineup with a
player who has no ingested score is ``partial`` and is not treated as zero.
"""

from __future__ import annotations

import argparse
import itertools
import json
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import numpy as np

from wnba_oracle.common.settings import Settings
from wnba_oracle.eval.contest_score import committed_order_score, hindsight_max_score
from wnba_oracle.eval.highest_value import HV_SECTION
from wnba_oracle.features.spec import cohort_for_position
from wnba_oracle.modeling import prediction as prediction_mod
from wnba_oracle.picker.optimize import optimize_lineup
from wnba_oracle.picker.payout import default_curve_for_regime
from wnba_oracle.scheduler.job2 import _build_specs, build_model_policy, build_optimize_config
from wnba_oracle.train.pipeline import load_artifact

SLOT_BASES = (2.0, 1.8, 1.6, 1.4, 1.2)
FOCUS = "2026-09-27"


@contextmanager
def _serve_missing_cohort_as_zero() -> Iterator[None]:
    """Replay the pre-#592 lookup: missing G/C mean is 0.0, not the F mean.

    The shipped function falls back to F when the key is absent. Hiding the
    F key for that one call forces the remaining 0.0 branch, which is the
    math that froze 2026-09-27. Present cohort keys are left alone.
    """

    original = prediction_mod.eb_predict_one

    def _bug(artifact: object, player_id: int, position: str, **kwargs: object) -> float | None:
        baseline = getattr(artifact, "eb_baseline", None)
        if baseline is None or int(player_id) not in baseline.player_alpha:
            return original(artifact, player_id, position, **kwargs)  # type: ignore[arg-type]
        cohort = cohort_for_position(position)
        means = baseline.cohort_means
        if cohort in means or "F" not in means:
            return original(artifact, player_id, position, **kwargs)  # type: ignore[arg-type]
        saved = means.pop("F")
        try:
            return original(artifact, player_id, position, **kwargs)  # type: ignore[arg-type]
        finally:
            means["F"] = saved

    prediction_mod.eb_predict_one = _bug  # type: ignore[assignment]
    try:
        yield
    finally:
        prediction_mod.eb_predict_one = original  # type: ignore[assignment]


def _load_dossier(path: Path) -> dict:
    return json.loads(path.read_text())


def _enrichment(dossier: dict, *, force_f: bool) -> list[dict]:
    rows = (dossier.get("input_snapshot") or {}).get("rows") or []
    out: list[dict] = []
    for row in rows:
        pid = row.get("real_sports_player_id")
        if pid is None:
            continue
        position = "F" if force_f else str(row.get("position") or "")
        out.append(
            {
                "real_sports_player_id": str(pid),
                "name": row.get("display_name") or "",
                "team": row.get("team") or "",
                "opponent": row.get("opponent") or "",
                "position": position,
                "card_boost": float(row.get("card_boost") or 0.0),
                "features_json": row.get("features_json") or {},
            }
        )
    return out


def _labels(dossier: dict) -> dict[int, tuple[float, str]]:
    """pid -> (real_score, section). Highest-value wins over other sections."""
    best: dict[int, tuple[int, float, str]] = {}
    for row in (dossier.get("realized_player_results") or {}).get("rows") or []:
        if row.get("real_score") is None:
            continue
        pid = int(row["platform_player_id"])
        section = str(row.get("section") or "")
        rank = 0 if section == HV_SECTION else 1
        score = float(row["real_score"])
        current = best.get(pid)
        if current is None or (rank, -score) < (current[0], -current[1]):
            best[pid] = (rank, score, section)
    return {pid: (score, section) for pid, (_rank, score, section) in best.items()}


def _hv_board(dossier: dict) -> list[dict]:
    rows = []
    for row in (dossier.get("realized_player_results") or {}).get("rows") or []:
        if row.get("section") != HV_SECTION or row.get("real_score") is None:
            continue
        rows.append(row)
    rows.sort(key=lambda r: (-float(r["real_score"]), int(r["platform_player_id"])))
    return rows


def _names(dossier: dict) -> dict[int, str]:
    named: dict[int, str] = {}
    for row in (dossier.get("input_snapshot") or {}).get("rows") or []:
        pid = row.get("real_sports_player_id")
        if pid is None:
            continue
        named[int(pid)] = str(row.get("display_name") or pid)
    return named


def _frozen_ids(dossier: dict) -> list[int]:
    lineup = (dossier.get("frozen_lineup") or {}).get("lineup") or {}
    return [int(pid) for pid in lineup.get("player_ids") or []]


def _score_ids(
    pids: Sequence[int],
    labels: Mapping[int, tuple[float, str]],
    boost_by: Mapping[int, float],
) -> dict:
    missing = [int(pid) for pid in pids if int(pid) not in labels]
    if len(pids) != 5:
        return {"status": "short", "n": len(pids), "missing_player_ids": missing}
    if missing:
        known = [int(pid) for pid in pids if int(pid) in labels]
        partial = None
        if known:
            partial = round(
                sum(labels[pid][0] * (2.0 + boost_by.get(pid, 0.0)) for pid in known),
                3,
            )
        return {
            "status": "partial",
            "missing_player_ids": missing,
            "known_value_times_boost_only": partial,
        }
    values = [labels[int(pid)][0] for pid in pids]
    boosts = [float(boost_by.get(int(pid), 0.0)) for pid in pids]
    return {
        "status": "scored",
        "committed_score": round(committed_order_score(values, boosts, SLOT_BASES), 3),
        "hindsight_max_score": round(hindsight_max_score(values, boosts, SLOT_BASES), 3),
    }


def _hv_reference(board: Sequence[dict]) -> dict:
    top = list(board[:5])
    if len(top) < 5:
        return {"status": "thin", "n": len(board)}
    values = [float(row["real_score"]) for row in top]
    boosts = [float(row.get("card_boost") or 0.0) for row in top]
    return {
        "status": "scored",
        "players": [str(row.get("display_name")) for row in top],
        "hindsight_max_score": round(hindsight_max_score(values, boosts, SLOT_BASES), 3),
    }


def _spearman(pred: list[float], realized: list[float]) -> float | None:
    if len(pred) < 8:
        return None
    pred_rank = np.argsort(np.argsort(np.asarray(pred, dtype=float)))
    real_rank = np.argsort(np.argsort(np.asarray(realized, dtype=float)))
    if float(np.std(pred_rank)) == 0.0 or float(np.std(real_rank)) == 0.0:
        return None
    return round(float(np.corrcoef(pred_rank, real_rank)[0, 1]), 3)


def _prediction_summary(
    enrichment: Sequence[dict],
    pred_real_scores: Mapping[int, float],
    labels: Mapping[int, tuple[float, str]],
) -> dict:
    by_cohort: dict[str, list[float]] = defaultdict(list)
    floored: dict[str, int] = defaultdict(int)
    paired_pred: list[float] = []
    paired_real: list[float] = []
    for row in enrichment:
        pid = int(row["real_sports_player_id"])
        cohort = cohort_for_position(str(row.get("position") or ""))
        score = pred_real_scores.get(pid)
        if score is None:
            continue
        by_cohort[cohort].append(float(score))
        if float(score) <= 0.51:
            floored[cohort] += 1
        if pid in labels:
            paired_pred.append(float(score))
            paired_real.append(labels[pid][0])
    medians = {
        cohort: round(float(np.median(values)), 3) for cohort, values in sorted(by_cohort.items())
    }
    return {
        "n_predicted": sum(len(v) for v in by_cohort.values()),
        "median_pred_by_cohort": medians,
        "n_floored_at_half_by_cohort": dict(sorted(floored.items())),
        "spearman_vs_labeled_real_score": _spearman(paired_pred, paired_real),
        "n_labeled_pairs": len(paired_pred),
    }


def _deterministic_tdv(
    enrichment: Sequence[dict],
    pred_real_scores: Mapping[int, float],
) -> list[int]:
    """Committed-order total draft value, team cap 2, boost caps 3 and 9.

    This is the production objective without Monte Carlo noise. Slot order
    follows predicted real_score, which is what the freeze commits ex ante.
    """
    players = []
    for row in enrichment:
        pid = int(row["real_sports_player_id"])
        pred = pred_real_scores.get(pid)
        if pred is None:
            continue
        boost = float(row.get("card_boost") or 0.0)
        if boost > 3.0:
            continue
        players.append((pid, float(pred), boost, str(row.get("team") or "")))
    players.sort(key=lambda item: -(item[1] * (2.0 + item[2])))
    pool = players[:20]
    best: tuple[float, tuple[int, ...]] | None = None
    for combo in itertools.combinations(range(len(pool)), 5):
        chosen = [pool[i] for i in combo]
        teams: dict[str, int] = defaultdict(int)
        over_cap = False
        for item in chosen:
            team = item[3]
            if not team:
                continue
            teams[team] += 1
            if teams[team] > 2:
                over_cap = True
                break
        if over_cap or sum(item[2] for item in chosen) > 9.0:
            continue
        order = sorted(range(5), key=lambda i: (-chosen[i][1], chosen[i][0]))
        ordered = [chosen[i] for i in order]
        values = [item[1] for item in ordered]
        boosts = [item[2] for item in ordered]
        objective = committed_order_score(values, boosts, SLOT_BASES)
        pids = tuple(item[0] for item in ordered)
        if best is None or objective > best[0]:
            best = (objective, pids)
    return list(best[1]) if best else []


def _specs(enrichment: list[dict], slate: str, policy: object, art: object):
    return _build_specs(
        enrichment,
        slate_date=slate,
        policy=policy,  # type: ignore[arg-type]
        art=art,  # type: ignore[arg-type]
        artifact_resolved=True,
        player_history={},
        measured_drafts_override=None,
    )


def _predict(enrichment: list[dict], slate: str, policy: object, art: object):
    _samps, _fields, projection = _specs(enrichment, slate, policy, art)
    scores = {
        pid: float(row["pred_real_score_p50"])
        for pid, row in projection.items()
        if row.get("pred_real_score_p50") is not None
    }
    return scores, projection


def _optimize(samps: list, fields: list, cfg: object) -> list[int]:
    rec = optimize_lineup(
        samps,
        fields,
        default_curve_for_regime("top_1"),
        cfg=cfg,  # type: ignore[arg-type]
    )
    return [int(pid) for pid in rec.player_ids]


def _describe(
    pids: Sequence[int], names: Mapping[int, str], enrichment: Sequence[dict]
) -> list[dict]:
    pos = {int(row["real_sports_player_id"]): row.get("position") for row in enrichment}
    boost = {int(row["real_sports_player_id"]): row.get("card_boost") for row in enrichment}
    return [
        {
            "player_id": int(pid),
            "name": names.get(int(pid), str(pid)),
            "position": pos.get(int(pid)),
            "cohort": cohort_for_position(str(pos.get(int(pid)) or "")),
            "card_boost": boost.get(int(pid)),
        }
        for pid in pids
    ]


def _prior_cohort_means(dossiers: dict[str, dict], exclude: str) -> dict[str, dict]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for slate, dossier in dossiers.items():
        if slate == exclude:
            continue
        labels = _labels(dossier)
        for row in (dossier.get("input_snapshot") or {}).get("rows") or []:
            pid = int(row["real_sports_player_id"])
            labeled = labels.get(pid)
            if labeled is None or labeled[1] != HV_SECTION:
                continue
            cohort = cohort_for_position(str(row.get("position") or ""))
            buckets[cohort].append(labeled[0])
    out = {}
    for cohort, values in sorted(buckets.items()):
        out[cohort] = {
            "n": len(values),
            "mean_real_score": round(float(np.mean(values)), 3),
        }
    return out


def _modal_positions(
    dossiers: Mapping[str, dict],
    *,
    slates: set[str],
) -> dict[int, str]:
    """Most common non-blank pool position per player on the allowed slates.

    Ties break toward the later slate. A blank row does not vote, so one
    missing snapshot cannot relabel a center as F.
    """

    counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    latest: dict[int, dict[str, str]] = defaultdict(dict)
    for slate in sorted(slates):
        dossier = dossiers.get(slate)
        if dossier is None:
            continue
        for row in (dossier.get("input_snapshot") or {}).get("rows") or []:
            pid = row.get("real_sports_player_id")
            position = str(row.get("position") or "").strip()
            if pid is None or not position:
                continue
            counts[int(pid)][position] += 1
            latest[int(pid)][position] = slate
    chosen: dict[int, str] = {}
    for pid, tally in counts.items():
        chosen[pid] = max(tally, key=lambda position: (tally[position], latest[pid][position]))
    return chosen


def _aligned_alpha_overrides(
    dossiers: Mapping[str, dict],
    *,
    score_slates: set[str],
    position_slates: set[str],
    stored_alpha: Mapping[int, float],
    artifact_f_mean: float,
) -> tuple[dict[int, float], dict[str, float]]:
    """Shift stored alphas by the same gap as the new cohort mean.

    The shipped alpha was shrunk against the F mean. A serve that writes
    ``mu_C`` and keeps that alpha moves every center by ``mu_C - mu_F``.
    The paired update is ``alpha' = alpha + (mu_F - mu_C)``, so

        mu_C + alpha' = mu_F + alpha

    which is the F-fallback level. That is what a high-shrink retrain on
    the joined HV corpus does for a player already in the artifact. The
    focus slate's scores stay out. Its pool position is allowed, and a
    blank earlier position inherits the modal pool position.
    """

    positions = _modal_positions(dossiers, slates=position_slates)
    buckets: dict[str, list[float]] = defaultdict(list)
    for slate in score_slates:
        dossier = dossiers.get(slate)
        if dossier is None:
            continue
        seen: set[int] = set()
        for row in (dossier.get("realized_player_results") or {}).get("rows") or []:
            if row.get("section") != HV_SECTION or row.get("real_score") is None:
                continue
            pid = int(row["platform_player_id"])
            if pid in seen:
                continue
            seen.add(pid)
            cohort = cohort_for_position(positions.get(pid) or "")
            buckets[cohort].append(float(row["real_score"]))
    if "F" not in buckets or not buckets["F"]:
        return {}, {"F": float(artifact_f_mean)}
    hv_f = float(np.mean(buckets["F"]))
    serve_means = {
        cohort: float(artifact_f_mean) + (float(np.mean(values)) - hv_f)
        for cohort, values in buckets.items()
        if values
    }
    serve_means["F"] = float(artifact_f_mean)
    overrides: dict[int, float] = {}
    for pid, alpha in stored_alpha.items():
        cohort = cohort_for_position(positions.get(int(pid)) or "")
        mu = float(serve_means.get(cohort, artifact_f_mean))
        overrides[int(pid)] = float(alpha) + float(artifact_f_mean) - mu
    return overrides, serve_means


def main(argv: list[str] | None = None) -> int:  # noqa: C901
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dossier-dir", type=Path, required=True)
    parser.add_argument("--focus", default=FOCUS)
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "models" / "picker_95264ce9_1788339935.pkl",
    )
    args = parser.parse_args(argv)

    dossiers = {path.stem: _load_dossier(path) for path in sorted(args.dossier_dir.glob("*.json"))}
    if args.focus not in dossiers:
        raise SystemExit(f"missing dossier for {args.focus}")

    art = load_artifact(args.artifact)
    baseline = art.eb_baseline
    sha = (
        args.artifact.with_suffix(".sha256").read_text().strip()
        if args.artifact.with_suffix(".sha256").exists()
        else ""
    )
    settings = Settings.model_validate(
        {
            "WNBA_ORACLE_MODEL_ARTIFACT_SHA": sha,
            "WNBA_SERVE_PRIMARY": "eb",
            "PAYOUT_REGIME": "top_1",
            "OPTIMIZER_OBJECTIVE_MODE": "total_draft_value",
            "OPTIMIZER_LEVERAGE_WEIGHT": 0.28,
            "OPTIMIZER_MAX_VALUE_OWNERSHIP_FADE": 0.001,
        }
    )
    policy = build_model_policy(settings)
    # Field scores are unused by the total-draft-value objective. Keeping
    # n_samples and seed at the freeze values preserves that objective.
    opt_cfg = replace(build_optimize_config(settings), n_field_lineups=1)
    import wnba_oracle.scheduler.job2 as job2

    def _empty_lookup(*_args: object, **_kwargs: object) -> dict:
        return {}

    job2._load_measured_drafts = _empty_lookup  # type: ignore[method-assign]
    job2._load_slate_label_names = _empty_lookup  # type: ignore[method-assign]

    overrides_by_slate: dict[str, dict[int, float]] = {}
    aligned_means_by_slate: dict[str, dict[str, float]] = {}

    def _alignment(slate: str) -> tuple[dict[int, float], dict[str, float]]:
        if slate not in overrides_by_slate:
            stored = dict(baseline.player_alpha) if baseline is not None else {}
            overrides, aligned_means = _aligned_alpha_overrides(
                dossiers,
                score_slates={day for day in dossiers if day < slate},
                position_slates={day for day in dossiers if day <= slate},
                stored_alpha=stored,
                artifact_f_mean=artifact_f,
            )
            overrides_by_slate[slate] = overrides
            aligned_means_by_slate[slate] = aligned_means
        return overrides_by_slate[slate], aligned_means_by_slate[slate]

    means = _prior_cohort_means(dossiers, args.focus)
    # Shift only by the prior HV gap versus F. Replacing the artifact F
    # mean with the HV-board mean would lift every player, because the
    # board is the right tail and alpha is already centered on the
    # artifact mean.
    original_means = dict(baseline.cohort_means) if baseline else {}
    artifact_f = float(original_means.get("F", 0.0))
    prior_f = (means.get("F") or {}).get("mean_real_score")
    empirical_means: dict[str, float] = {}
    if prior_f:
        for cohort, row in means.items():
            gap = float(row["mean_real_score"]) - float(prior_f)
            empirical_means[cohort] = round(artifact_f + gap, 6)

    report: dict = {
        "focus": args.focus,
        "artifact": args.artifact.name,
        "cohort_means_in_artifact": dict(original_means),
        "n_player_alpha": len(baseline.player_alpha) if baseline else 0,
        "prior_hv_cohort_means_excluding_focus": means,
        "empirical_serve_means": empirical_means,
        "note": (
            "Measured drafts are omitted. The freeze snapshot does not store "
            "pre-lock draft counts, and post-slate slate_labels.drafts would leak."
        ),
        "slates": {},
    }

    def run_mode(slate: str, dossier: dict, mode: str) -> dict:
        force_f = mode == "eb_hardcoded"
        enrichment = _enrichment(dossier, force_f=force_f)
        labels = _labels(dossier)
        names = _names(dossier)
        boost_by = {
            int(row["real_sports_player_id"]): float(row["card_boost"] or 0.0) for row in enrichment
        }
        use_policy = policy
        if mode == "heads":
            use_policy = replace(policy, serve_primary="heads")
        saved_alphas: dict[int, float] | None = None
        if mode == "eb_empirical" and baseline is not None:
            baseline.cohort_means = dict(empirical_means)
        elif baseline is not None:
            baseline.cohort_means = dict(original_means)
        if mode == "eb_hv_aligned" and baseline is not None:
            saved_alphas = dict(baseline.player_alpha)
            aligned_alphas, aligned_means = _alignment(slate)
            baseline.cohort_means = dict(aligned_means)
            for pid, alpha in aligned_alphas.items():
                if pid in baseline.player_alpha:
                    baseline.player_alpha[pid] = alpha
        try:
            if mode == "eb_bug":
                with _serve_missing_cohort_as_zero():
                    scores, _projection = _predict(enrichment, slate, use_policy, art)
            else:
                scores, _projection = _predict(enrichment, slate, use_policy, art)
            chosen = _deterministic_tdv(enrichment, scores)
        finally:
            if saved_alphas is not None and baseline is not None:
                baseline.player_alpha.clear()
                baseline.player_alpha.update(saved_alphas)
            if baseline is not None:
                baseline.cohort_means = dict(original_means)
        scored = _score_ids(chosen, labels, boost_by)
        board = _hv_board(dossier)
        top5 = {int(row["platform_player_id"]) for row in board[:5]}
        top10 = {int(row["platform_player_id"]) for row in board[:10]}
        return {
            "deterministic_lineup": _describe(chosen, names, _enrichment(dossier, force_f=False)),
            "deterministic_score": scored,
            "overlap_hv_top5": len(set(chosen) & top5),
            "overlap_hv_top10": len(set(chosen) & top10),
            "predictions": _prediction_summary(enrichment, scores, labels),
        }

    modes = (
        "eb_bug",
        "eb_fallback",
        "eb_hardcoded",
        "heads",
        "eb_empirical",
        "eb_hv_aligned",
    )
    for slate, dossier in dossiers.items():
        slate_report = {"modes": {}}
        for mode in modes:
            if mode == "eb_empirical" and not empirical_means:
                continue
            slate_report["modes"][mode] = run_mode(slate, dossier, mode)
        frozen = _frozen_ids(dossier)
        labels = _labels(dossier)
        enrichment = _enrichment(dossier, force_f=False)
        boost_by = {
            int(row["real_sports_player_id"]): float(row["card_boost"] or 0.0) for row in enrichment
        }
        slate_report["frozen"] = {
            "player_ids": frozen,
            "lineup": _describe(frozen, _names(dossier), enrichment),
            "score": _score_ids(frozen, labels, boost_by),
            "hv_top5_hindsight": _hv_reference(_hv_board(dossier)),
        }
        report["slates"][slate] = slate_report

    focus = dossiers[args.focus]
    enrichment = _enrichment(focus, force_f=False)
    labels = _labels(focus)
    names = _names(focus)
    boost_by = {
        int(row["real_sports_player_id"]): float(row["card_boost"] or 0.0) for row in enrichment
    }

    def optimize_mode(mode: str, leverage: float) -> dict:
        force_f = mode == "eb_hardcoded"
        rows = _enrichment(focus, force_f=force_f)
        use_policy = policy
        cfg = replace(opt_cfg, leverage_weight=leverage)
        if mode == "heads":
            use_policy = replace(policy, serve_primary="heads")
        saved_alphas: dict[int, float] | None = None
        if mode == "eb_empirical" and baseline is not None:
            baseline.cohort_means = dict(empirical_means)
        elif baseline is not None:
            baseline.cohort_means = dict(original_means)
        if mode == "eb_hv_aligned" and baseline is not None:
            saved_alphas = dict(baseline.player_alpha)
            aligned_alphas, aligned_means = _alignment(args.focus)
            baseline.cohort_means = dict(aligned_means)
            for pid, alpha in aligned_alphas.items():
                if pid in baseline.player_alpha:
                    baseline.player_alpha[pid] = alpha
        try:
            if mode == "eb_bug":
                with _serve_missing_cohort_as_zero():
                    samps, fields, _projection = _specs(rows, args.focus, use_policy, art)
            else:
                samps, fields, _projection = _specs(rows, args.focus, use_policy, art)
            pids = _optimize(samps, fields, cfg)
        finally:
            if saved_alphas is not None and baseline is not None:
                baseline.player_alpha.clear()
                baseline.player_alpha.update(saved_alphas)
            if baseline is not None:
                baseline.cohort_means = dict(original_means)
        return {
            "leverage_weight": leverage,
            "lineup": _describe(pids, names, enrichment),
            "score": _score_ids(pids, labels, boost_by),
            "overlap_frozen": len(set(pids) & set(_frozen_ids(focus))),
        }

    optimizer_runs = {}
    for mode in (
        "eb_bug",
        "eb_fallback",
        "eb_hardcoded",
        "heads",
        "eb_empirical",
        "eb_hv_aligned",
    ):
        optimizer_runs[mode] = optimize_mode(mode, 0.28)
    optimizer_runs["eb_fallback_leverage_0"] = optimize_mode("eb_fallback", 0.0)
    optimizer_runs["eb_fallback_leverage_0_40"] = optimize_mode("eb_fallback", 0.40)
    report["focus_optimizer"] = optimizer_runs
    aligned_overrides, aligned_means = _alignment(args.focus)
    report["hv_aligned_prior_means"] = aligned_means
    report["hv_aligned_n_alpha_overrides"] = (
        sum(1 for pid in aligned_overrides if pid in baseline.player_alpha) if baseline else 0
    )

    def _scores_for(mode: str) -> dict[int, float]:
        saved_alphas: dict[int, float] | None = None
        if mode == "eb_empirical" and baseline is not None:
            baseline.cohort_means = dict(empirical_means)
        elif baseline is not None:
            baseline.cohort_means = dict(original_means)
        if mode == "eb_hv_aligned" and baseline is not None:
            saved_alphas = dict(baseline.player_alpha)
            baseline.cohort_means = dict(aligned_means)
            for pid, alpha in aligned_overrides.items():
                if pid in baseline.player_alpha:
                    baseline.player_alpha[pid] = alpha
        try:
            if mode == "eb_bug":
                with _serve_missing_cohort_as_zero():
                    scores, _projection = _predict(enrichment, args.focus, policy, art)
            else:
                scores, _projection = _predict(enrichment, args.focus, policy, art)
            return scores
        finally:
            if saved_alphas is not None and baseline is not None:
                baseline.player_alpha.clear()
                baseline.player_alpha.update(saved_alphas)
            if baseline is not None:
                baseline.cohort_means = dict(original_means)

    bug_scores = _scores_for("eb_bug")
    fallback_scores = _scores_for("eb_fallback")
    aligned_scores = _scores_for("eb_hv_aligned")
    position_by = {
        int(row["real_sports_player_id"]): str(row.get("position") or "") for row in enrichment
    }

    def _lineup_ids(mode: str) -> set[int]:
        return {int(row["player_id"]) for row in optimizer_runs[mode]["lineup"]}

    aja_class: list[dict] = []
    for pid, (real, section) in labels.items():
        if section != HV_SECTION:
            continue
        position = position_by.get(pid, "")
        if cohort_for_position(position) != "C":
            continue
        boost = float(boost_by.get(pid, 0.0))
        slot1 = float(real) * (2.0 + boost)
        if slot1 < 10.0:
            continue
        aja_class.append(
            {
                "player_id": pid,
                "name": names.get(pid, str(pid)),
                "position": position,
                "real_score": round(float(real), 3),
                "card_boost": boost,
                "slot1_committed_value": round(slot1, 3),
                "pred_bug": None if bug_scores.get(pid) is None else round(bug_scores[pid], 3),
                "pred_fallback": (
                    None if fallback_scores.get(pid) is None else round(fallback_scores[pid], 3)
                ),
                "pred_hv_aligned": (
                    None if aligned_scores.get(pid) is None else round(aligned_scores[pid], 3)
                ),
                "in_bug_optimizer": pid in _lineup_ids("eb_bug"),
                "in_fallback_optimizer": pid in _lineup_ids("eb_fallback"),
                "in_empirical_optimizer": pid in _lineup_ids("eb_empirical"),
                "in_hv_aligned_optimizer": pid in _lineup_ids("eb_hv_aligned"),
            }
        )
    aja_class.sort(key=lambda row: (-float(row["slot1_committed_value"]), int(row["player_id"])))
    leader = aja_class[0] if aja_class else None
    recovered = bool(leader) and (
        leader["in_fallback_optimizer"]
        and leader["in_hv_aligned_optimizer"]
        and not leader["in_bug_optimizer"]
        and all(
            row["pred_fallback"] is not None
            and row["pred_hv_aligned"] is not None
            and float(row["pred_fallback"]) > 1.0
            and float(row["pred_hv_aligned"]) > 1.0
            for row in aja_class
        )
    )
    report["aja_class_centers"] = {
        "rule": (
            "Cohort C on the focus Highest-value board whose slot-1 committed "
            "value (real_score * (2 + card_boost)) is at least 10. The board "
            "Value column is that product. Wilson at boost 0 is real_score * 2."
        ),
        "players": aja_class,
        "board_leader_recovered": recovered,
        "empirical_mean_gap_drops_board_leader": bool(leader)
        and not leader["in_empirical_optimizer"],
    }
    report["leverage_weight_changes_tdv_lineup"] = (
        optimizer_runs["eb_fallback"]["lineup"]
        != optimizer_runs["eb_fallback_leverage_0"]["lineup"]
        or optimizer_runs["eb_fallback"]["lineup"]
        != optimizer_runs["eb_fallback_leverage_0_40"]["lineup"]
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

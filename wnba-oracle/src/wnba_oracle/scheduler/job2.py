"""Job 2: predict + freeze near tip. Redis SET NX + Postgres UPSERT.

Once the lineup freezes, it never re-rolls intra-day. The Redis key
`wnba.frozen.{slate_date}` is SET with NX + TTL=24h; if it already exists
this Job 2 invocation is a no-op (idempotent). The Postgres frozen_lineups
table is UPSERTed on (slate_date, model_sha).

Pipeline:
1. Read Job 1 enrichment from job1_enrichment table.
2. Load the model artifact (if WNBA_ORACLE_MODEL_ARTIFACT_SHA set + file
   exists). Else use the transparent heuristic picker (low-data fallback).
3. Build sampling/field specs for the optimizer.
4. Load payout curve (from archive if available, else default for regime).
5. Run optimize_lineup.
6. Freeze.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import text

from wnba_oracle.common.logging import configure_logging, get_logger
from wnba_oracle.common.settings import Settings, get_settings
from wnba_oracle.db.engine import get_engine, get_redis
from wnba_oracle.features.game_script_minutes import (
    GameScriptInput,
    GameScriptMinutesConfig,
    blowout_probability,
    redistribute_game_script_minutes,
)
from wnba_oracle.features.spec import cohort_for_position
from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.game_script import GameScriptConfig, game_script_multiplier
from wnba_oracle.picker.optimize import LineupRecommendation, OptimizeConfig, optimize_lineup
from wnba_oracle.picker.payout import default_curve_for_regime, load_curve_from_archive
from wnba_oracle.picker.popularity import (
    ContrarianConfig,
    apply_contrarian_adjustment,
    estimate_draft_popularity,
    slate_labels_to_popularity,
)
from wnba_oracle.picker.sample import PlayerSamplingSpec, ceiling_adjusted_sigma_log
from wnba_oracle.predict.archetypes import ArchetypeInput, classify_pool
from wnba_oracle.predict.availability import AvailabilityConfig, availability_probability
from wnba_oracle.predict.base import player_volatility
from wnba_oracle.predict.minutes import (
    MinutesConfig,
    blended_real_score,
    minutes_interval_from_projection,
    minutes_interval_from_role,
    project_minutes_from_base,
)
from wnba_oracle.train.pipeline import PickerArtifact, load_artifact

log = get_logger("oracle.job2")

# Anchor definition for the Tier 1 lineup anchor floor (D57): a player we are
# confident logs real minutes tonight. Either an established rotation player
# (>= ANCHOR_MIN_GAMES recent games averaging >= ANCHOR_MIN_MINUTES) or a
# RotoWire-confirmed starter. Cold-start darts (no minutes history) are NOT
# anchors -- they are exactly the boost longshots that sank 2026-06-01.
ANCHOR_MIN_GAMES = 3
ANCHOR_MIN_MINUTES = 20.0


@dataclass(frozen=True)
class Job2Result:
    slate_date: str
    model_sha: str
    recommendation: LineupRecommendation | None
    frozen: bool
    reason: str


# Pure scoring/feature-extraction helpers live in job2_scoring so this
# module can focus on freeze orchestration + DB/Redis glue. Re-exported
# here because tests reference them via ``job2._name``.
from wnba_oracle.scheduler.job2_scoring import (  # noqa: E402
    _cascade_bonuses,
    _effective_confirmed,
    _features_dict,
    _floor_tilt_multiplier,
    _heuristic_real_score,
    _is_out_from_features,
    _minutes_features,
    _prop_signal_multiplier,
    _starter_minutes_lift,
    _starter_multiplier,
    _vegas_from_features,
)

__all__ = [
    "_cascade_bonuses",
    "_effective_confirmed",
    "_features_dict",
    "_floor_tilt_multiplier",
    "_heuristic_real_score",
    "_is_out_from_features",
    "_minutes_features",
    "_prop_signal_multiplier",
    "_starter_minutes_lift",
    "_starter_multiplier",
    "_vegas_from_features",
]


REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_player_history() -> dict[int, float]:
    """Per-player mean real_score from slate_labels in Postgres.

    Used as a fallback prediction tier between the EB model and the generic
    heuristic. Players not yet in the EB model (trained before their 2026 data
    was backfilled) but with any corpus history get their actual observed mean
    rather than the boost-level heuristic. This matters most for boost-3
    players: the heuristic gives them 1.81, but a player like Milic whose only
    observed slate scored 0.51 should not be treated as average-for-boost-3.

    Returns an empty dict on any read/parse error so the caller degrades
    gracefully to the heuristic.
    """
    try:
        from wnba_oracle.db.reads import read_player_history

        return read_player_history()
    except Exception:
        return {}


def _load_model_artifact(sha: str) -> PickerArtifact | None:
    """Load the trained PickerArtifact whose SHA256 matches `sha`.

    Looks under `models/` for any `picker_*.pkl` whose sidecar
    `.sha256` file matches. Returns None on any failure (missing,
    SHA mismatch, unpickle error) — the caller falls back to the
    transparent heuristic.

    Empty `sha` short-circuits to None so deployments without the
    env var set behave exactly like the pre-D45 heuristic-only path.
    """
    if not sha:
        return None
    sha = sha.strip().lower()
    models_dir = REPO_ROOT / "models"
    if not models_dir.exists():
        log.warning("model_artifact_dir_missing", dir=str(models_dir))
        return None
    # `write_artifact` writes the sidecar at `picker_<commit>_<ts>.sha256`
    # (path.with_suffix(".sha256") REPLACES `.pkl`, it doesn't append).
    for sidecar in models_dir.glob("picker_*.sha256"):
        try:
            disk_sha = sidecar.read_text().strip().lower()
        except OSError:
            continue
        if disk_sha != sha:
            continue
        pkl_path = sidecar.with_suffix(".pkl")
        if not pkl_path.exists():
            log.warning("model_artifact_pkl_missing", path=str(pkl_path))
            return None
        try:
            art = load_artifact(pkl_path)
        except Exception as exc:
            log.exception("model_artifact_load_failed", path=str(pkl_path), error=str(exc))
            return None
        log.info(
            "model_artifact_loaded",
            path=str(pkl_path),
            sha=sha[:12],
            training_rows=art.training_rows,
            low_data_mode=art.low_data_mode,
            n_heads=len(art.heads),
            has_eb_baseline=art.eb_baseline is not None,
            n_eb_players=len(art.eb_baseline.player_alpha) if art.eb_baseline else 0,
        )
        return art
    log.warning("model_artifact_sha_not_found", sha=sha[:12])
    return None


def _eb_predict_one(art: PickerArtifact | None, player_id: int, position: str) -> float | None:
    """Single-player EB prediction with cohort + player-alpha lookup.

    Returns None if (a) no artifact, (b) no EB baseline in artifact, or
    (c) player_id wasn't seen in training. Caller falls back to the
    heuristic on None — this preserves graceful degradation for new
    players the model never saw. The `team_pace` term is dropped
    because job1_enrichment doesn't yet carry team pace.
    """
    if art is None or art.eb_baseline is None:
        return None
    eb = art.eb_baseline
    if int(player_id) not in eb.player_alpha:
        return None
    cohort = cohort_for_position(position)
    mu = eb.cohort_means.get(cohort, 0.0)
    alpha = eb.player_alpha[int(player_id)]
    pred = mu + alpha
    return max(0.5, float(pred))


def _load_enrichment(slate_date: str) -> list[dict]:
    eng = get_engine()
    q = text(
        "SELECT real_sports_player_id, name, team, opponent, position, "
        "card_boost, features_json "
        "FROM job1_enrichment WHERE slate_date = :sd"
    )
    with eng.connect() as conn:
        result = conn.execute(q, {"sd": slate_date})
        return [dict(row._mapping) for row in result]


def _load_prior_real_scores(slate_date: str) -> dict[int, list[float]]:
    """As-of per-player realized real_scores from slate_labels for all slates
    STRICTLY BEFORE `slate_date`, most-recent-first. Drives per-player
    sampling sigma (volatility). Empty on any DB error -> caller uses the
    calibrated default sigma. Walk-forward-safe: never reads the target slate.
    """
    try:
        eng = get_engine()
    except RuntimeError:
        return {}
    q = text(
        "SELECT platform_player_id, slate_date, MAX(real_score) AS real_score "
        "FROM slate_labels WHERE slate_date < :sd AND real_score IS NOT NULL "
        "GROUP BY platform_player_id, slate_date ORDER BY slate_date DESC"
    )
    out: dict[int, list[float]] = {}
    with eng.connect() as conn:
        for row in conn.execute(q, {"sd": slate_date}):
            m = row._mapping
            pid = m.get("platform_player_id")
            rs = m.get("real_score")
            if pid is None or rs is None:
                continue
            out.setdefault(int(pid), []).append(float(rs))
    return out


def _load_measured_drafts(slate_date: str) -> dict[int, int]:
    """Pull the most recent draftStats.drafts counts from slate_labels for
    the slate. Empty if Job 2 is firing before any contest finalized
    (typical case pregame). Job 2 then falls back to the popularity
    estimator."""
    try:
        eng = get_engine()
    except RuntimeError:
        return {}
    q = text(
        "SELECT platform_player_id, MAX(drafts) AS drafts "
        "FROM slate_labels WHERE slate_date = :sd AND drafts IS NOT NULL "
        "GROUP BY platform_player_id"
    )
    with eng.connect() as conn:
        rows = conn.execute(q, {"sd": slate_date}).fetchall()
    out: dict[int, int] = {}
    for r in rows:
        m = r._mapping
        pid = m.get("platform_player_id")
        d = m.get("drafts")
        if pid is None or d is None:
            continue
        out[int(pid)] = int(d)
    return out


def _load_slate_label_names(slate_date: str) -> dict[int, str]:
    """Pull display names from slate_labels for the slate, keyed by
    platform_player_id.

    Defense-in-depth name source for the frozen lineup (D50). The primary
    name path is `job1_enrichment.name` (Real Sports pool, D49). When that
    is empty for a player, this fallback fills it from the independently
    populated `slate_labels.display_name` so the freeze never ships a
    `Player <id>` placeholder when a real name exists anywhere in the DB.
    Empty / blank names are skipped so they never shadow the final
    `Player {pid}` fallback. Empty when Job 2 fires before any contest
    finalized (typical pregame), in which case the enrichment name stands.
    """
    try:
        eng = get_engine()
    except RuntimeError:
        return {}
    q = text(
        "SELECT DISTINCT ON (platform_player_id) platform_player_id, display_name "
        "FROM slate_labels WHERE slate_date = :sd "
        "ORDER BY platform_player_id, id DESC"
    )
    with eng.connect() as conn:
        rows = conn.execute(q, {"sd": slate_date}).fetchall()
    out: dict[int, str] = {}
    for r in rows:
        m = r._mapping
        pid = m.get("platform_player_id")
        name = str(m.get("display_name", "") or "").strip()
        if pid is None or not name:
            continue
        out[int(pid)] = name
    return out


def _predict_heads_for_pool(
    art: PickerArtifact | None,
    enrichment: list[dict],
) -> dict[int, dict[str, float]]:
    """D69 / Phase 2b Tier-0: run the D63 trained heads over every pool player
    whose `head_features` row Job 1 persisted into ``features_json``.

    Returns {pid: {"p10", "p50", "p90"}} for matched players. Empty dict on:
      - artifact None / no minutes head trained (no behavioural change)
      - no pool player has head_features (cold-start day, fall through to ladder)
      - any predict failure (logged + skipped, per-player ladder still fires)
    """
    if art is None:
        return {}
    # Require both heads the recompose uses; otherwise predict_real_score returns
    # None and we save the import + frame build.
    minutes_head = art.heads.get(("minutes", "F"))
    rate_head = art.heads.get(("real_score_per_min", "F"))
    if minutes_head is None or rate_head is None:
        return {}
    feature_cols = minutes_head.feature_columns
    rate_cols = rate_head.feature_columns
    # The two heads were trained on identical _BASE_FEATURES (features/spec.py).
    # Take the union so neither booster sees a missing column at predict time.
    needed = tuple(dict.fromkeys((*feature_cols, *rate_cols)))

    pids: list[int] = []
    rows: list[dict] = []
    for r in enrichment:
        pid_raw = r.get("real_sports_player_id")
        if pid_raw is None:
            continue
        try:
            pid = int(pid_raw)
        except (TypeError, ValueError):
            continue
        f = _features_dict(r.get("features_json"))
        hf = f.get("head_features") if isinstance(f, dict) else None
        if not isinstance(hf, dict) or not hf:
            continue
        # Cohort routing inside predict_real_score reads `position`; pool into "F"
        # for now (matches features/corpus build_gamelog_corpus, D63 memory).
        row: dict[str, object] = {"position": "F"}
        for c in needed:
            v = hf.get(c, 0.0)
            try:
                row[c] = float(v) if v is not None else 0.0
            except (TypeError, ValueError):
                row[c] = 0.0
        pids.append(pid)
        rows.append(row)
    if not rows:
        return {}
    try:
        import polars as pl

        frame = pl.DataFrame(rows)
        pred = art.predict_real_score(frame)
    except Exception as exc:
        log.warning("head_predict_failed", reason=str(exc)[:160])
        return {}
    if pred is None:
        return {}
    out: dict[int, dict[str, float]] = {}
    for pid, p10, p50, p90 in zip(pids, pred["p10"], pred["p50"], pred["p90"]):
        if p50 is None or not np.isfinite(p50):
            continue
        out[int(pid)] = {
            "p10": float(p10) if np.isfinite(p10) else 0.0,
            "p50": float(p50),
            "p90": float(p90) if np.isfinite(p90) else float(p50),
        }
    log.info("head_predict", n_in=len(rows), n_out=len(out))
    return out


def build_optimize_config(settings: Settings) -> OptimizeConfig:
    """The OptimizeConfig production actually runs, from Settings.

    Extracted so the offline lab (scripts/lab.py) can evaluate a change
    against the SAME base configuration the freeze uses. A bare
    ``OptimizeConfig()`` is not that: the dataclass defaults are
    top_n_filter=30 / n_samples=5000 / n_field_lineups=1000, while Settings
    serves 20 / 1000 / 500. Comparing "defaults+delta vs defaults" answers a
    question nobody asked, and costs ~90x the compute doing it.
    """
    return OptimizeConfig(
        top_n_filter=settings.optimizer_top_n_filter,
        n_samples=settings.optimizer_n_samples,
        n_field_lineups=settings.optimizer_n_field_lineups,
        max_per_team=settings.optimizer_max_per_team,
        dynamic_team_cap=settings.optimizer_dynamic_team_cap,
        caveat_is_skip=settings.caveat_is_skip,
        never_skip=settings.never_skip,
        score_offset=settings.sampling_score_offset,
        min_anchors=settings.lineup_anchor_floor,
        boost_sum_cap=settings.optimizer_boost_sum_cap,
        max_single_boost=settings.optimizer_max_single_boost,
        game_stack_bonus=settings.optimizer_game_stack_bonus,
        leverage_weight=getattr(settings, "optimizer_leverage_weight", 0.0),
        ceiling_weight=getattr(settings, "optimizer_ceiling_weight", 0.0),
        duplication_weight=getattr(settings, "optimizer_duplication_weight", 0.0),
        ceiling_tilt_slots=getattr(settings, "optimizer_ceiling_tilt_slots", False),
        field_same_game_boost=getattr(settings, "field_same_game_boost", 1.0),
        field_same_team_boost=getattr(settings, "field_same_team_boost", 1.0),
        duplication_aware_payout=getattr(settings, "optimizer_duplication_aware_payout", False),
    )


def _build_specs(
    enrichment: list[dict],
    *,
    slate_date: str,
    contrarian_cfg: ContrarianConfig | None = None,
    player_history: dict[int, float] | None = None,
    prior_by_player: dict[int, list[float]] | None = None,
    injury_bonus_by_pid: dict[int, float] | None = None,
) -> tuple[list[PlayerSamplingSpec], list[FieldPlayerSpec], dict[int, dict]]:
    """Build the (sampling, field) specs the optimizer reads.

    Applies the anti-popularity contrarian adjustment (basketball-main
    Finding 4) to the heuristic real_score. Popularity comes from
    measured `drafts` in slate_labels when available, else from the
    estimator (season ppg + big-market + slate size).

    Returns: (sampling_specs, field_specs, projection_by_pid). The third
    element carries the per-player display data needed to materialize
    `per_player` into the frozen JSONB (display_name, team, opponent,
    position, card_boost, final pred_real_score after contrarian).
    """
    if contrarian_cfg is None:
        s = get_settings()
        contrarian_cfg = ContrarianConfig(
            enabled=s.contrarian_enabled, strength=s.contrarian_strength
        )
    if not enrichment:
        return [], [], {}

    # Defense-in-depth name source (D50): when the Real Sports pool left
    # `job1_enrichment.name` empty, fill display names from slate_labels so
    # the frozen lineup never ships a `Player <id>` placeholder.
    label_names = _load_slate_label_names(slate_date)

    # Load trained artifact when WNBA_ORACLE_MODEL_ARTIFACT_SHA matches a
    # picker_*.pkl under models/. EB baseline predictions replace the
    # heuristic for any player seen in training; unseen players still
    # use _heuristic_real_score. None on missing/mismatched artifact
    # means the entire pool falls back to heuristic — same path as before
    # D45 wiring. This makes deployment of a new model SHA non-destructive.
    settings = get_settings()
    art = _load_model_artifact(settings.model_artifact_sha)
    # D69 / Phase 2b Tier-0: batch-predict from the D63 quantile heads up-front.
    # Empty dict means no head served (no features, no trained heads, or predict
    # failure) -- the per-player loop falls through to the existing ladder for
    # every pid not in this map, preserving the byte-identical pre-D69 freeze.
    head_predictions = _predict_heads_for_pool(art, enrichment)
    head_quantiles_by_pid: dict[int, dict[str, float]] = {}
    n_head_predicted = 0
    n_eb_predicted = 0
    n_history_fallback = 0
    n_heuristic_fallback = 0

    # Slate-size signal for the popularity estimator
    n_games_on_slate = len({str(r.get("team", "") or "") for r in enrichment if r.get("team")}) // 2
    n_games_on_slate = max(n_games_on_slate, 1)

    measured_drafts = _load_measured_drafts(slate_date)
    if measured_drafts:
        popularity_scores = slate_labels_to_popularity(measured_drafts)
        log.info("contrarian_using_measured", n_measured=len(popularity_scores))
    else:
        # Estimator fallback: use card_boost as a weak proxy for season_ppg
        # since we don't yet ingest per-player season stats. card_boost is
        # inverse to rolling Real Rating average, so 3.0 -> cold star,
        # 0.0 -> hot star. We invert it.
        popularity_scores = {}
        for r in enrichment:
            pid_raw = r.get("real_sports_player_id")
            if pid_raw is None:
                continue
            try:
                pid = int(pid_raw)
            except (TypeError, ValueError):
                continue
            boost = float(r.get("card_boost", 0.0) or 0.0)
            # Pseudo-ppg in [10, 22] from boost in [3, 0]
            pseudo_ppg = 10.0 + (3.0 - boost) * 4.0
            popularity_scores[pid] = estimate_draft_popularity(
                season_ppg=pseudo_ppg,
                team=str(r.get("team", "") or ""),
                n_games_on_slate=n_games_on_slate,
            )

    # First pass: per-player predicted real_score (heuristic) modulated by
    # the per-game game-script multiplier. The multiplier reads Vegas
    # total + spread from features_json (Job 1 persisted them). Games
    # with no Vegas signal degrade to a neutral 1.0x.
    pred_real_scores: dict[int, float] = {}
    rank_pred_by_pid: dict[int, float] = {}
    rows_by_pid: dict[int, dict] = {}
    minutes_vol_by_pid: dict[int, float] = {}
    # Per-player projected (P10, P50, P90) MINUTES — surfaces the same minutes
    # projection the predictor already computes so the frontend's minutes bar
    # reflects the model, not a slot-position placeholder. Populated in each
    # prediction tier; consumed in _build_specs' second loop when materializing
    # projection_by_pid.
    pred_minutes_by_pid: dict[int, tuple[float, float, float]] = {}
    gsm_enabled = settings.game_script_minutes_enabled
    gsm_cfg = GameScriptMinutesConfig()
    # When the role-aware blowout redistribution is on it OWNS the blowout
    # effect, so disable the blunt team-wide blowout penalty to avoid
    # double-counting (D57).
    gs_cfg = GameScriptConfig(blowout_penalty=1.0) if gsm_enabled else GameScriptConfig()
    mcfg = MinutesConfig()
    bonus = injury_bonus_by_pid or {}
    avail_enabled = settings.availability_model_enabled
    avail_cfg = AvailabilityConfig()
    blowout_prob_by_pid: dict[int, float] = {}
    is_starter_by_pid: dict[int, bool] = {}
    is_anchor_by_pid: dict[int, bool] = {}
    p_active_by_pid: dict[int, float] = {}
    gsm_rows: list[GameScriptInput] = []
    rate_by_pid: dict[int, float] = {}
    n_minutes_predicted = 0
    for r in enrichment:
        pid_raw = r.get("real_sports_player_id")
        if pid_raw is None:
            continue
        try:
            pid = int(pid_raw)
        except (TypeError, ValueError):
            continue
        boost = float(r.get("card_boost", 0.0) or 0.0)
        position = str(r.get("position", "") or "")
        total, spread = _vegas_from_features(r.get("features_json"))
        gs_mult = game_script_multiplier(total, spread, cfg=gs_cfg) if total > 0 else 1.0
        f = _features_dict(r.get("features_json"))
        # D104: treat RotoWire EXPECTED starters as a known role, not only
        # CONFIRMED ones -- confirmed lineups for every game are not all out by
        # the T-40 freeze. This `eff_confirmed` flag feeds every role consumer
        # below (anchor, availability, blended minutes) so the starting five on
        # the slate's later games is honored from the 13:00 expected lineup.
        eff_confirmed = _effective_confirmed(f, use_expected=settings.starter_signal_use_expected)
        mf = _minutes_features(r.get("features_json")) if settings.minutes_model_enabled else None
        # Anchor flag (D57, Tier 1) -- computed regardless of the floor setting
        # so it always rides on the spec; the optimizer only enforces it when
        # min_anchors > 0.
        is_anchor_by_pid[pid] = (
            mf is not None
            and mf["n_min_games"] >= ANCHOR_MIN_GAMES
            and mf["recent_minutes"] >= ANCHOR_MIN_MINUTES
        ) or (eff_confirmed and bool(int(f.get("is_starter", 0) or 0)))
        if avail_enabled:
            p_active_by_pid[pid] = availability_probability(
                recent_minutes=float(mf["recent_minutes"]) if mf is not None else 0.0,
                minutes_vol=float(mf["minutes_vol"]) if mf is not None else 0.0,
                n_min_games=int(mf["n_min_games"]) if mf is not None else 0,
                rotowire_confirmed=eff_confirmed,
                is_starter=bool(int(f.get("is_starter", 0) or 0)),
                cfg=avail_cfg,
            )
        if gsm_enabled and total > 0:
            # Blowout context for the regime-switching copula + the minutes
            # redistribution (D57). Only players with known recent minutes can
            # donate/receive; cold-start darts have no minutes and so are left
            # untouched here (the availability engine, not this, gates them).
            blowout_prob_by_pid[pid] = blowout_probability(abs(spread), gsm_cfg)
            recent_min_gs = float(mf["recent_minutes"]) if mf is not None else 0.0
            is_starter_by_pid[pid] = (
                bool(int(f.get("is_starter", 0) or 0))
                or recent_min_gs >= gsm_cfg.starter_minutes_floor
            )
            if mf is not None and recent_min_gs > 0.0:
                gsm_rows.append(
                    GameScriptInput(pid, str(r.get("team", "") or ""), recent_min_gs, abs(spread))
                )
                rate_by_pid[pid] = float(mf["per_min_rate"])
        # D69 / Phase 2b Tier-0: trained quantile heads (D63). Walk-forward
        # validated corr 0.554 vs the existing ladder's 0.246. Falls through to
        # Tier 1 (blended_real_score) for any pid the head didn't score.
        hp = head_predictions.get(pid)
        if hp is not None:
            p10 = hp["p10"]
            p50 = hp["p50"]
            p90 = hp["p90"]
            # D71 / R5: apply the RotoWire confirmed-starter signal symmetrically
            # to all three quantiles. The trained head learned from game logs
            # only (`features/corpus.build_gamelog_corpus` does NOT compute
            # `is_confirmed_starter`; `train/pipeline.py:240` drops it because
            # it's missing from the corpus), so without this nudge the head is
            # blind to today's confirmed lineup. Mirrors the Tier-3 fallback's
            # use of `_starter_multiplier`; the Tier-1 blend deliberately omits
            # the nudge because `blended_real_score` already weighs minutes.
            # Magnitude is small (1.10 confirmed starter, 0.82 confirmed bench,
            # 1.0 unknown) so we never overpower the head on the median, but
            # the symmetric scaling of the 80% interval keeps the sampler's
            # delta-method sigma in the same units.
            starter_mult = _starter_multiplier(
                r.get("features_json"),
                enabled=settings.starter_signal_enabled,
                use_expected=settings.starter_signal_use_expected,
                unknown_fade=float(getattr(settings, "starter_unknown_fade", 1.0)),
            )
            # 2026-07-10: minutes-conditional starter lift. The head's
            # features carry pre-promotion minutes, so an expected starter
            # coming off a bench stretch is systematically under-projected
            # (Kuier 07-05/07-07, Harris 07-09 -- each the slate's top missed
            # swap). Folded into starter_mult so it rides every place the
            # starter signal already touches (p50, interval, rank).
            starter_mult *= _starter_minutes_lift(
                r.get("features_json"),
                enabled=settings.starter_minutes_lift_enabled,
                use_expected=settings.starter_signal_use_expected,
                norm=settings.starter_minutes_norm,
                weight=settings.starter_minutes_lift_weight,
                cap=settings.starter_minutes_lift_cap,
            )
            # Game-script multiplier still applies (Vegas tilt on top of the
            # head). Floor matches every other Tier so the downstream sampler
            # never sees a non-positive mean.
            # D78: sportsbook prop signal (sharp-money pts over/under). Disabled
            # by default (scale=0); enable via PROP_SIGNAL_SCALE=0.3 once
            # calibrated against placement data.
            prop_mult = _prop_signal_multiplier(
                r.get("features_json"), scale=settings.prop_signal_scale
            )
            # 2026-07-10 floor tilt: blend the sampling/rank center of
            # non-spike candidates toward their p10 so wide-interval ceiling
            # plays fade out of the mid slots (winners' 1.8/1.6/1.4 slots are
            # floor plays). Spike tier (boost >= max_boost) is untouched.
            floor_mult = _floor_tilt_multiplier(
                p10,
                p50,
                boost,
                weight=settings.picker_floor_tilt_weight,
                max_boost=settings.picker_floor_tilt_max_boost,
            )
            pred_real_scores[pid] = max(0.5, p50 * gs_mult * starter_mult * prop_mult * floor_mult)
            # 2026-07-04 boost-tail lift: multiplicative ceiling nudge applied
            # only to the stage-1 ranker (visible_value), not to the sampler.
            # calibrate_starter_and_boost.py: mean_real / mean_p50 ratio at
            # boost>=2.0 is 1.57 across 1202 pool-slates, so a lift factor of
            # ~1.5 matches empirical without inflating the noisy head p90
            # (p90 for boost-3 role players is a fabricated 10x ceiling; its
            # training rows are too sparse to bound the tail). Off by default.
            lift_enabled = bool(getattr(settings, "picker_boost_tail_lift", False))
            lift_thresh = float(getattr(settings, "boost_tail_lift_threshold", 2.0))
            lift_factor = float(getattr(settings, "boost_tail_lift_factor", 1.5))
            if lift_enabled and boost >= lift_thresh:
                rank_pred_by_pid[pid] = max(
                    0.5, p50 * lift_factor * gs_mult * starter_mult * prop_mult * floor_mult
                )
            # 80% interval (~2.56 sigma) -> additive real_score volatility. Same
            # semantic as `minutes_vol_by_pid` for the Tier-1 path so the
            # sampler's delta-method conversion works unchanged. starter_mult
            # is applied so the spread stays proportional to the shifted mean.
            spread = max(0.0, p90 - p10) * starter_mult / 2.56
            minutes_vol_by_pid[pid] = max(0.5, spread)
            head_quantiles_by_pid[pid] = {
                "p10": p10 * starter_mult,
                "p50": p50 * starter_mult,
                "p90": p90 * starter_mult,
            }
            # Real projected-minutes interval for the frozen per-player payload
            # (frontend interval bar). The head predicts real_score, not
            # minutes, so we anchor the interval on the same minutes machinery
            # the D55 path uses when the player has recent minutes history;
            # otherwise fall back to role anchors from the confirmed-starter
            # signal so cold-start darts still get a plausible interval.
            is_starter_flag = bool(int(f.get("is_starter", 0) or 0))
            if mf is not None and mf["n_min_games"] >= mcfg.min_obs_for_history:
                m50 = project_minutes_from_base(
                    float(mf["recent_minutes"]),
                    has_history=True,
                    rotowire_confirmed=eff_confirmed,
                    is_starter=is_starter_flag,
                    injury_bonus_min=float(bonus.get(pid, 0.0)),
                    blowout=False,
                    cfg=mcfg,
                )
                pred_minutes_by_pid[pid] = minutes_interval_from_projection(
                    m50, float(mf["minutes_vol"]), cfg=mcfg
                )
            else:
                pred_minutes_by_pid[pid] = minutes_interval_from_role(
                    rotowire_confirmed=eff_confirmed,
                    is_starter=is_starter_flag,
                    cfg=mcfg,
                )
            n_head_predicted += 1
            rows_by_pid[pid] = r
            continue
        if mf is not None and mf["n_min_games"] >= mcfg.min_obs_for_history:
            # D55 minutes edge: blended_real_score handles the boost<->minutes
            # weighting internally, with same-day role signals. Blowout is left
            # to game_script (it already penalises via the spread tier) to avoid
            # double-counting; the starter multiplier is superseded by the
            # confirmed-role minutes anchor here, so it is NOT applied.
            base = blended_real_score(
                recent_min=mf["recent_minutes"],
                rate=mf["per_min_rate"],
                n_games=mf["n_min_games"],
                boost_prior=_heuristic_real_score(boost),
                rotowire_confirmed=eff_confirmed,
                is_starter=bool(int(f.get("is_starter", 0) or 0)),
                injury_bonus_min=float(bonus.get(pid, 0.0)),
                blowout=False,
                cfg=mcfg,
            )
            pred_real_scores[pid] = max(0.5, base * gs_mult)
            minutes_vol_by_pid[pid] = mf["minutes_vol"] * mf["per_min_rate"]
            # Tier-1 minutes interval: reuse the same projection blended_real_score
            # applied internally, so the frontend interval matches what the model
            # actually used to score the player.
            m50_t1 = project_minutes_from_base(
                float(mf["recent_minutes"]),
                has_history=True,
                rotowire_confirmed=eff_confirmed,
                is_starter=bool(int(f.get("is_starter", 0) or 0)),
                injury_bonus_min=float(bonus.get(pid, 0.0)),
                blowout=False,
                cfg=mcfg,
            )
            pred_minutes_by_pid[pid] = minutes_interval_from_projection(
                m50_t1, float(mf["minutes_vol"]), cfg=mcfg
            )
            n_minutes_predicted += 1
            rows_by_pid[pid] = r
            continue
        # Fallback (no minutes match): EB > corpus history > boost heuristic,
        # with the legacy starter nudge.
        starter_mult = _starter_multiplier(
            r.get("features_json"),
            enabled=settings.starter_signal_enabled,
            use_expected=settings.starter_signal_use_expected,
            unknown_fade=float(getattr(settings, "starter_unknown_fade", 1.0)),
        )
        eb_pred = _eb_predict_one(art, pid, position)
        if eb_pred is not None:
            base = eb_pred
            n_eb_predicted += 1
        elif player_history is not None and pid in player_history:
            # Use observed per-player mean from the label corpus. More
            # accurate than the generic heuristic for players whose data
            # postdates the last training run (common early-season pattern).
            base = max(0.5, player_history[pid])
            n_history_fallback += 1
        else:
            base = _heuristic_real_score(boost)
            n_heuristic_fallback += 1
        pred_real_scores[pid] = max(0.5, base * gs_mult * starter_mult)
        # Tier-3 minutes interval: no per-player minutes history, so we anchor
        # on the confirmed-role signal (starter -> ~30 min, bench -> ~13 min,
        # unknown -> wide 20-min band). Consistent with how _starter_multiplier
        # tilts the real_score in this same branch.
        pred_minutes_by_pid[pid] = minutes_interval_from_role(
            rotowire_confirmed=eff_confirmed,
            is_starter=bool(int(f.get("is_starter", 0) or 0)),
            cfg=mcfg,
        )
        rows_by_pid[pid] = r

    if gsm_enabled and gsm_rows:
        # Convert the signed minute deltas to real_score via each player's
        # per-minute rate, then fold into pred_real_score (D57). Bench up,
        # starters down; floored at 0.5 like every other predictor branch.
        deltas_min = redistribute_game_script_minutes(gsm_rows, gsm_cfg)
        n_bumped = sum(1 for d in deltas_min.values() if d > 0)
        n_trimmed = sum(1 for d in deltas_min.values() if d < 0)
        for pid_d, dmin in deltas_min.items():
            rate = rate_by_pid.get(pid_d, mcfg.league_rate)
            pred_real_scores[pid_d] = max(0.5, pred_real_scores[pid_d] + dmin * rate)
        log.info(
            "game_script_minutes", n_bumped=n_bumped, n_trimmed=n_trimmed, n_rows=len(gsm_rows)
        )

    log.info(
        "predictor_mix",
        artifact_sha=settings.model_artifact_sha[:12] if settings.model_artifact_sha else "",
        n_head_predicted=n_head_predicted,
        n_minutes_predicted=n_minutes_predicted,
        n_eb_predicted=n_eb_predicted,
        n_history_fallback=n_history_fallback,
        n_heuristic_fallback=n_heuristic_fallback,
    )

    if avail_enabled and p_active_by_pid:
        # Two-part hurdle (D57, Tier 2): scale each active-conditional pred by
        # P(active). Cold-start darts collapse; established players ~unchanged.
        n_low = 0
        for pid_a, p_act in p_active_by_pid.items():
            if pid_a in pred_real_scores:
                pred_real_scores[pid_a] = max(0.5, pred_real_scores[pid_a] * p_act)
                if p_act < 0.5:
                    n_low += 1
        log.info("availability_model", n_players=len(p_active_by_pid), n_low_availability=n_low)

    # Apply contrarian adjustment
    adjusted = apply_contrarian_adjustment(pred_real_scores, popularity_scores, contrarian_cfg)

    # Per-player sampling sigma from volatility (D52/D55). A flat sigma priced
    # every player the same; ceiling plays (high game-to-game variance) should
    # sample wider so the EV/percentile math sees their upside. Prefer the
    # minutes-derived volatility (minutes_vol x rate, D55) for matched players,
    # else fall back to realized real_score volatility. K and sigma share the
    # same score_offset the copula un-offsets.
    K = float(settings.sampling_score_offset)
    volatility = player_volatility(prior_by_player or {})

    samps: list[PlayerSamplingSpec] = []
    fields: list[FieldPlayerSpec] = []
    projection_by_pid: dict[int, dict[str, Any]] = {}
    for pid, pred in adjusted.items():
        r = rows_by_pid[pid]
        team = str(r.get("team", "") or "")
        opp = str(r.get("opponent", "") or "")
        boost = float(r.get("card_boost", 0.0) or 0.0)
        mu_log = float(np.log(max(pred + K, 1.0)))
        # Convert the real_score-unit volatility to a log-scale sigma via the
        # delta method: std(real) ~= (pred + K) * sigma_log. Clamp to a sane
        # band so a single outlier game can't blow up the percentile bias.
        vol = minutes_vol_by_pid.get(int(pid)) or volatility.get(int(pid), 1.17)
        sigma_log = min(0.6, max(0.12, vol / max(pred + K, 1e-6)))
        # D89 (Phase 4): environment-conditioned ceiling sigma boost. Widens
        # the per-player marginal sigma when the game has blowout
        # uncertainty (role volatility) and/or the player has limited
        # recent history (sample-size shrinkage). Both default to 0.0 so
        # the path is byte-identical until armed via env var.
        n_min_games = int(mf["n_min_games"]) if mf is not None else 0
        sigma_log = ceiling_adjusted_sigma_log(
            sigma_log,
            blowout_prob=blowout_prob_by_pid.get(pid, 0.0),
            n_history_games=n_min_games,
            blowout_boost=getattr(settings, "ceiling_sigma_blowout_boost", 0.0),
            low_history_boost=getattr(settings, "ceiling_sigma_low_history_boost", 0.0),
        )
        samps.append(
            PlayerSamplingSpec(
                player_id=pid,
                team=team,
                opponent=opp,
                mu=mu_log,
                sigma=sigma_log,
                boost=boost,
                is_starter=is_starter_by_pid.get(pid, False),
                blowout_prob=blowout_prob_by_pid.get(pid, 0.0),
                is_anchor=is_anchor_by_pid.get(pid, False),
                p_active=p_active_by_pid.get(
                    pid, 1.0
                ),  # D107 (Tier 2): P(active) for mixture-variance sampling
            )
        )
        # D86: when enabled, attach the real measured draft count so the field
        # simulation samples opponent lineups from observed ownership instead of
        # a softmax of our own projections. measured_drafts was loaded above for
        # the contrarian penalty; here it also grounds the EV/leverage math.
        md = (
            float(measured_drafts[pid])
            if (
                getattr(settings, "field_measured_ownership_enabled", True)
                and pid in measured_drafts
            )
            else None
        )
        fields.append(
            FieldPlayerSpec(
                player_id=pid,
                pred_real_score=pred,
                card_boost=boost,
                measured_drafts=md,
                rank_pred_override=rank_pred_by_pid.get(pid),
            )
        )
        enrichment_name = str(r.get("name", "") or "").strip()
        display_name = enrichment_name or label_names.get(pid, "") or f"Player {pid}"
        proj = {
            "display_name": display_name,
            "team": team,
            "opponent": opp,
            "position": str(r.get("position", "") or "F"),
            "card_boost": boost,
            "pred_real_score_p50": pred,
        }
        # D69 / Phase 2b: surface the head quantiles when Tier-0 served this
        # pid. The frontend (_build_per_player) reads p10/p90 to draw the
        # real_score interval; absent for ladder-served players (unchanged).
        hq = head_quantiles_by_pid.get(pid)
        if hq is not None:
            proj["pred_real_score_p10"] = float(hq["p10"])
            proj["pred_real_score_p90"] = float(hq["p90"])
        mp = pred_minutes_by_pid.get(pid)
        if mp is not None:
            p10m, p50m, p90m = mp
            proj["pred_minutes_p10"] = float(p10m)
            proj["pred_minutes_p50"] = float(p50m)
            proj["pred_minutes_p90"] = float(p90m)
        projection_by_pid[pid] = proj

    # D105: archetype classification. Surface the DFS value archetype for each
    # player in the frozen lineup metadata. Derived from the MLB highest-value
    # archetype analysis: ceiling_anchor (high-usage starter on high-total team),
    # efficient_producer (high-leverage stat concentration), leverage_spike
    # (cheap confirmed starter), plus a streaking tag. Metadata-only -- does
    # not change predictions or optimizer behaviour.
    archetype_inputs: list[ArchetypeInput] = []
    for pid, proj in projection_by_pid.items():
        r = rows_by_pid.get(pid, {})
        f = _features_dict(r.get("features_json"))
        hf = f.get("head_features") if isinstance(f, dict) else None
        hf = hf if isinstance(hf, dict) else {}
        card_boost_raw = proj.get("card_boost", 0.0)
        card_boost = float(card_boost_raw) if isinstance(card_boost_raw, (int, float, str)) else 0.0
        archetype_inputs.append(
            ArchetypeInput(
                player_id=pid,
                card_boost=card_boost,
                is_confirmed_starter=is_anchor_by_pid.get(pid, False),
                is_anchor=is_anchor_by_pid.get(pid, False),
                mins_l10=float(hf.get("mins_l10", 0.0) or 0.0),
                pts_per_min_l10=float(hf.get("pts_per_min_l10", 0.0) or 0.0),
                ast_per_min_l10=float(hf.get("ast_per_min_l10", 0.0) or 0.0),
                stl_blk_per_min_l10=float(hf.get("stl_blk_per_min_l10", 0.0) or 0.0),
                reb_per_min_l10=float(hf.get("reb_per_min_l10", 0.0) or 0.0),
                ts_pct_l10=float(hf.get("ts_pct_l10", 0.0) or 0.0),
                fantasy_pts_l5=float(hf.get("fantasy_pts_l5", 0.0) or 0.0),
                fantasy_pts_l10=float(hf.get("fantasy_pts_l10", 0.0) or 0.0),
                pts_per_min_l5=float(hf.get("pts_per_min_l5", 0.0) or 0.0),
                implied_team_total=float(hf.get("implied_team_total", 0.0) or 0.0),
                vegas_total=float(hf.get("vegas_total", 0.0) or 0.0),
                usg_pct_l10=float(hf.get("usg_pct_l10", 0.0) or 0.0),
            )
        )
    if archetype_inputs:
        archetype_labels = classify_pool(archetype_inputs)
        for pid, label in archetype_labels.items():
            if pid in projection_by_pid:
                projection_by_pid[pid]["archetype"] = label.primary
                if label.is_streaking:
                    projection_by_pid[pid]["streak_driver"] = label.streak_driver
                    projection_by_pid[pid]["streak_quality"] = label.streak_quality
                projection_by_pid[pid]["stat_leverage"] = label.stat_leverage

    return samps, fields, projection_by_pid


# D82: frozen_lineups is append-only. Every freeze fire (the first tip-relative T-40 fire
# freeze and D75 late re-freeze alike) inserts a NEW row with the next
# freeze_seq for (slate_date, model_sha); nothing ever updates a frozen row
# in place, so the lineup the operator saw at any point stays reconstructable.
# The seq is computed in the INSERT's source SELECT; if two writers race to
# the same seq the unique constraint on (slate_date, model_sha, freeze_seq)
# turns the loser into a clean no-op (empty RETURNING) that _freeze retries.
#
# :model_sha is CAST to varchar explicitly. It is referenced twice (the SELECT
# value and the WHERE filter); after migration 0008 widened the column to
# varchar(64), Postgres deduced inconsistent types for the reused bind param
# ("text versus character varying") and raised AmbiguousParameter on every
# append, which silently blocked all freezes from 2026-06-13 onward. The cast
# pins a single type so the parameter unifies.
FROZEN_APPEND = text(
    """
    INSERT INTO frozen_lineups (
        slate_date, model_sha, payout_regime, frozen_at, lineup,
        entry_recommendation, expected_payout, metadata_json,
        freeze_seq, frozen_via
    )
    SELECT
        :slate_date, CAST(:model_sha AS varchar), :payout_regime, now(),
        CAST(:lineup AS JSONB),
        :entry_recommendation, :expected_payout, CAST(:metadata_json AS JSONB),
        COALESCE(MAX(freeze_seq), 0) + 1, :frozen_via
    FROM frozen_lineups
    WHERE slate_date = :slate_date AND model_sha = CAST(:model_sha AS varchar)
    ON CONFLICT (slate_date, model_sha, freeze_seq) DO NOTHING
    RETURNING id, freeze_seq;
    """
)

FROZEN_EXISTS = text("SELECT 1 FROM frozen_lineups WHERE slate_date = :sd AND model_sha = :ms")

SLATE_LOCK_Q = text("SELECT contest_lock_utc, first_tip_utc FROM slate_meta WHERE slate_date = :sd")


def _load_slate_lock_time(slate_date: str) -> dt.datetime | None:
    """The slate's contest lock time from slate_meta (D83).

    Prefers an explicit contest_lock_utc; falls back to first_tip_utc
    (DFS contests lock at first game start, and the platform exposes no
    lock timestamp). None when job1 never captured timing for the slate,
    in which case the gate uses its hard deadline instead.
    """
    try:
        eng = get_engine()
        with eng.connect() as conn:
            row = conn.execute(SLATE_LOCK_Q, {"sd": slate_date}).first()
    except Exception as exc:
        log.warning("job2_slate_lock_read_failed", reason=str(exc)[:120])
        return None
    if row is None:
        return None
    lock = row[0] or row[1]
    if lock is None:
        return None
    if lock.tzinfo is None:
        lock = lock.replace(tzinfo=dt.UTC)
    return lock.astimezone(dt.UTC)


def _freeze_deadline_utc(
    lock_time_utc: dt.datetime | None,
    settings,
) -> dt.datetime | None:
    """The tip-relative freeze deadline = lock/first-tip minus freeze_lead_minutes.

    WNBA slates tip at different clock times each day, so a static UTC cutoff
    (late_refreeze_after_utc) misses an afternoon slate that locks before the
    evening cron window. The deadline anchors freeze timing to the slate's own
    first tip. None when slate_meta has no timing (callers fall back to their
    static behaviour). See deep-dive E.
    """
    if lock_time_utc is None:
        return None
    lead = int(getattr(settings, "freeze_lead_minutes", 40))
    return lock_time_utc - dt.timedelta(minutes=lead)


def _in_pre_freeze_window(now_utc: dt.datetime, deadline_utc: dt.datetime | None) -> bool:
    """True when this fire should be skipped because the slate has not reached
    its T-minus freeze deadline yet. A None deadline (tip unknown) never skips:
    the static late-refreeze fallback handles timing in that case. See E."""
    return deadline_utc is not None and now_utc < deadline_utc


def _late_refreeze_allowed(
    now_utc: dt.datetime,
    lock_time_utc: dt.datetime | None,
    settings,
) -> tuple[bool, str]:
    """D83 lock gate for the late re-freeze.

    Lock time known: allow only strictly before lock minus the buffer.
    Lock time unknown: allow only strictly before the configured hard
    deadline (HH:MM UTC). A malformed deadline blocks the re-freeze;
    failing closed is the point of the gate.
    """
    if lock_time_utc is not None:
        buffer = dt.timedelta(minutes=int(settings.refreeze_lock_buffer_min))
        if now_utc < lock_time_utc - buffer:
            return True, "pre_lock"
        return False, "lock_gated"
    try:
        h, m = (int(x) for x in settings.late_refreeze_deadline_utc.split(":"))
        deadline = now_utc.replace(hour=h, minute=m, second=0, microsecond=0)
    except (ValueError, AttributeError):
        return False, "bad_deadline_config"
    if now_utc < deadline:
        return True, "pre_deadline_no_locktime"
    return False, "deadline_no_locktime"


def _build_per_player(
    rec: LineupRecommendation,
    projection_by_pid: dict[int, dict],
) -> list[dict]:
    """Materialize the per-player projection list embedded in the frozen
    lineup JSONB. The frontend's FrozenLineup contract reads this to
    render player names, teams, opponents, positions, boosts, and the
    minutes-quantile interval bar.

    Minutes P10/P50/P90 pass through from the predictor (the same
    project_minutes_from_base + minutes_vol the D55/D63 tiers use to score
    the player). Rows without a projection map (missing pid, upstream
    bug) fall back to a rank-aware default so the row still emits with
    a plausible interval instead of crashing the freeze.
    """
    pid_order = list(rec.player_ids)
    out: list[dict] = []
    for slot_idx, pid in enumerate(pid_order):
        proj = projection_by_pid.get(int(pid), {})
        # Rank-aware minutes fallback used only when the predictor did not
        # attach an interval (safe-default path — missing pid or a tier that
        # skipped minutes projection). Slot 1 leans starter, slot 5 trails.
        p50_default = max(22.0, 32.0 - 1.5 * slot_idx)
        p10m = float(proj.get("pred_minutes_p10", p50_default - 4.0))
        p50m = float(proj.get("pred_minutes_p50", p50_default))
        p90m = float(proj.get("pred_minutes_p90", p50_default + 4.0))
        entry = {
            "player_id": int(pid),
            "display_name": proj.get("display_name", f"Player {pid}"),
            "team": proj.get("team", ""),
            "opponent": proj.get("opponent", ""),
            "position": proj.get("position", "F"),
            "card_boost": float(proj.get("card_boost", 0.0)),
            "pred_real_score_p50": float(proj.get("pred_real_score_p50", 0.0)),
            "pred_minutes_p10": p10m,
            "pred_minutes_p50": p50m,
            "pred_minutes_p90": p90m,
        }
        # D69 / Phase 2b: pass through the real_score interval when the
        # trained heads served this player. Absent fields are backward-compatible.
        if "pred_real_score_p10" in proj:
            entry["pred_real_score_p10"] = float(proj["pred_real_score_p10"])
            entry["pred_real_score_p90"] = float(proj["pred_real_score_p90"])
        # D105: archetype label (metadata-only; does not affect predictions).
        if "archetype" in proj:
            entry["archetype"] = proj["archetype"]
        if "streak_driver" in proj:
            entry["streak_driver"] = proj["streak_driver"]
            entry["streak_quality"] = float(proj.get("streak_quality", 0.0))
        if "stat_leverage" in proj:
            entry["stat_leverage"] = float(proj["stat_leverage"])
        out.append(entry)
    return out


def _release_freeze_lock(slate_date: str, force: bool) -> None:
    """Drop the Redis freeze lock for a slate so the next fire can retry.

    The lock (wnba.frozen.{sd} / wnba.late_frozen.{sd}) is taken with a 24h
    TTL before the Postgres append. If the append then fails, leaving the lock
    set would defer every later fire for the full TTL and wedge the slate (the
    2026-06-13 outage). Releasing it on failure makes the lock self-healing:
    a transient append error costs one fire, not a day. Best-effort; a Redis
    error here is irrelevant because the lock auto-expires anyway.
    """
    key = f"wnba.late_frozen.{slate_date}" if force else f"wnba.frozen.{slate_date}"
    try:
        get_redis().delete(key)
    except Exception as exc:
        log.warning("job2_freeze_lock_release_failed", slate_date=slate_date, error=str(exc)[:120])


def _freeze(
    slate_date: str,
    model_sha: str,
    rec: LineupRecommendation,
    payout_regime: str,
    projection_by_pid: dict[int, dict],
    *,
    force: bool = False,
    payout_curve: dict | None = None,
    serving_knobs: dict | None = None,
) -> bool:
    """Idempotent freeze: first job2 fire writes, subsequent fires no-op.

    True-freeze semantics (the operator submits one lineup per slate and
    must not see it change underneath them):

    1. Check Postgres for an existing row keyed on (slate_date, model_sha).
       Existence is the canonical "already frozen" signal — Redis is just
       a fast-path hint.
    2. If absent, take the Redis SETNX lock as a fast soft-lock to
       discourage concurrent inserts within the cron window (cron-job2
       fires every 15 min; without the lock two cron tasks could race
       between the existence-check and the INSERT). On lock-miss treat
       it as "another fire is in flight" and bail without writing.
    3. Issue FROZEN_APPEND (D82): an INSERT that computes the next
       freeze_seq for the key and no-ops on a seq collision. ``RETURNING``
       distinguishes "I wrote this row" from "lost the seq race".

    When force=True (late re-freeze, D75): skip the Postgres existence
    check, use the wnba.late_frozen.{slate_date} Redis key (first-fire-wins
    per day, 24h TTL) to prevent duplicate late re-freezes, and APPEND a
    new row (D82) so the earlier freeze stays intact for audit. This path
    is only reached when LATE_REFREEZE_ENABLED=true, the current UTC time
    is past LATE_REFREEZE_AFTER_UTC, and the D83 lock gate allows it.

    Returns True iff this invocation appended a freeze record.
    """
    eng = get_engine()
    frozen_via = "job2_late_refreeze" if force else "job2_first_fire"

    if force:
        # D75 late re-freeze: use a separate Redis key so only the first
        # late-fire appends. Subsequent fires (every 15 min) see the key
        # already set and bail without touching frozen_lineups.
        try:
            rd = get_redis()
            late_key = f"wnba.late_frozen.{slate_date}"
            lock_acquired = bool(rd.set(late_key, model_sha, nx=True, ex=24 * 3600))
        except Exception as redis_exc:
            log.warning("job2_redis_unavailable", error=str(redis_exc)[:120])
            lock_acquired = True  # proceed; Postgres UPSERT is the canonical guard
        if not lock_acquired:
            log.info("job2_late_refreeze_already_done", slate_date=slate_date)
            return False
    else:
        with eng.connect() as conn:
            existing = conn.execute(FROZEN_EXISTS, {"sd": slate_date, "ms": model_sha}).first()
        if existing:
            log.info("job2_already_frozen", slate_date=slate_date, model_sha=model_sha)
            return False

        try:
            rd = get_redis()
            key = f"wnba.frozen.{slate_date}"
            # The 24h TTL covers a full slate window; if the writer crashes the
            # lock auto-releases for the next fire to retry.
            lock_acquired = bool(rd.set(key, model_sha, nx=True, ex=24 * 3600))
        except Exception as redis_exc:
            log.warning("job2_redis_unavailable", error=str(redis_exc)[:120])
            lock_acquired = True  # proceed; Postgres ON CONFLICT guards correctness
        if not lock_acquired:
            log.info(
                "job2_freeze_lock_held",
                slate_date=slate_date,
                note="another job2 fire is mid-freeze; deferring",
            )
            return False

    # D90 calibration fields: payout_curve + serving_knobs persist in the
    # lineup JSONB so the placement reader can join the freeze-time forecast
    # to the realized contest outcome. None payloads are dropped to keep the
    # JSONB compact when callers (older test fixtures) do not supply them.
    lineup_payload: dict = {
        "player_ids": list(rec.player_ids),
        "slot_multipliers": list(rec.slot_multipliers),
        "lineup_score_p10": rec.lineup_score_p10,
        "lineup_score_p50": rec.lineup_score_p50,
        "lineup_score_p90": rec.lineup_score_p90,
        "per_player": _build_per_player(rec, projection_by_pid),
    }
    if payout_curve is not None:
        lineup_payload["payout_curve"] = payout_curve
    if serving_knobs is not None:
        lineup_payload["serving_knobs"] = serving_knobs

    payload = {
        "slate_date": slate_date,
        "model_sha": model_sha,
        "payout_regime": payout_regime,
        "lineup": json.dumps(lineup_payload),
        "entry_recommendation": rec.entry_flag,
        "expected_payout": rec.expected_payout,
        # frozen_via stays duplicated in metadata_json for one release so
        # existing readers of metadata keep working (drop after frontend
        # confirms it reads the column).
        "metadata_json": json.dumps({"frozen_via": frozen_via}),
        "frozen_via": frozen_via,
    }
    # One retry on an empty RETURNING: a concurrent appender took our seq.
    # The Redis locks make this near-impossible, but the constraint is the
    # actual correctness boundary, so honor it.
    result = None
    try:
        for attempt in (1, 2):
            with eng.begin() as conn:
                result = conn.execute(FROZEN_APPEND, payload).first()
            if result is not None:
                break
            log.info("job2_lost_seq_race", slate_date=slate_date, attempt=attempt)
    except Exception as append_exc:
        # The append raised (e.g. a SQL/parameter error). Release the freeze
        # lock so the next fire retries immediately instead of deferring for
        # the 24h TTL, then surface the error to the caller.
        _release_freeze_lock(slate_date, force)
        log.exception(
            "job2_freeze_append_error", slate_date=slate_date, error=str(append_exc)[:200]
        )
        return False
    if result is None:
        _release_freeze_lock(slate_date, force)
        log.warning("job2_freeze_append_failed", slate_date=slate_date, via=frozen_via)
        return False
    log.info(
        "job2_late_refrozen" if force else "job2_frozen",
        slate_date=slate_date,
        row_id=int(result[0]),
        freeze_seq=int(result[1]),
    )
    return True


def run(slate_date: str | None = None, *, dry_run: bool = False) -> Job2Result:
    settings = get_settings()
    sd = slate_date or dt.date.today().isoformat()
    model_sha = settings.model_artifact_sha or "heuristic-v1"

    log.info("job2_start", slate_date=sd, model_sha=model_sha)
    enrichment_raw = _load_enrichment(sd)
    # Serving-schema boundary check (warn-only rollout). Rejects the
    # 2026-07-02-style degraded pool (all-G positions, null minutes) as
    # watchdog events without blocking the freeze; escalate to strict
    # after the count stays at zero for a rolling week.
    try:
        from wnba_oracle.features.serving_schema import validate_enrichment
        from wnba_oracle.scheduler.watchdog import (
            SEVERITY_WARN,
            WatchdogEvent,
            persist_events,
        )

        findings = validate_enrichment(enrichment_raw, strict=False)
        if findings:
            persist_events(
                [
                    WatchdogEvent(
                        slate_date=sd,
                        trigger=f.trigger,
                        severity=SEVERITY_WARN,
                        payload=f.payload,
                    )
                    for f in findings
                ]
            )
    except Exception as schema_exc:
        log.warning("serving_schema_check_failed", reason=str(schema_exc)[:160])
    # Injury cascade (D55): redistribute OUT players' recent minutes to active
    # teammates BEFORE dropping the OUT players from the pool (they are the
    # donors). job1 now ships recent_minutes per player, so the full D33/D29
    # cascade finally has the mins_l10 it needs. Empty when no OUT player has
    # minutes history.
    injury_bonus = _cascade_bonuses(enrichment_raw)
    if injury_bonus:
        log.info(
            "job2_injury_cascade",
            n_recipients=len(injury_bonus),
            max_bonus=round(max(injury_bonus.values()), 1),
        )
    # RotoWire OUT players are excluded from the optimizer pool (the binary
    # drop is the other half of the cascade).
    enrichment = [r for r in enrichment_raw if not _is_out_from_features(r.get("features_json"))]
    n_dropped = len(enrichment_raw) - len(enrichment)
    if n_dropped:
        log.info("job2_dropped_out_players", n_dropped=n_dropped, n_remaining=len(enrichment))
    if len(enrichment) < 5:
        log.warning("job2_pool_too_small", n=len(enrichment), n_dropped=n_dropped)
        return Job2Result(sd, model_sha, None, False, "pool_too_small")

    player_history = _load_player_history()
    prior_by_player = _load_prior_real_scores(sd)
    log.info(
        "player_history_loaded",
        n_players=len(player_history),
        n_prior_history=len(prior_by_player),
    )
    samps, fields, projection_by_pid = _build_specs(
        enrichment,
        slate_date=sd,
        player_history=player_history,
        prior_by_player=prior_by_player,
        injury_bonus_by_pid=injury_bonus,
    )
    if len(samps) < 5:
        return Job2Result(sd, model_sha, None, False, "specs_too_small")

    curve = load_curve_from_archive(sd) or default_curve_for_regime(settings.payout_regime)
    cfg = build_optimize_config(settings)
    mixture_variance_enabled = getattr(settings, "optimizer_mixture_variance_enabled", True)
    rec = optimize_lineup(
        samps, fields, curve, cfg=cfg, mixture_variance_enabled=mixture_variance_enabled
    )
    log.info(
        "job2_optimizer_done",
        n_pool=len(samps),
        expected_payout=rec.expected_payout,
        entry_flag=rec.entry_flag,
    )
    if dry_run:
        return Job2Result(sd, model_sha, rec, False, "dry_run")

    # E (deep-dive): T-minus freeze gate. WNBA slates tip at different clock
    # times, so the freeze is anchored to the slate's own first tip, not a
    # hardcoded evening slot. The freeze deadline is first_tip - freeze_lead
    # (T-40 by default). When the tip is known:
    #   - before T-40: skip this fire entirely. The lineup is finalized at
    #     T-40 with the freshest enrichment (the confirmed-lineup refresh lands
    #     ~T-35 via cron-job1-late); the next cron tick re-evaluates. This is
    #     what makes the pipeline tip-relative instead of clock-relative -- a
    #     noon-tip slate freezes ~T-40 in the morning, an evening slate at night.
    #   - at/after T-40: freeze once (idempotent first-freeze path); later fires
    #     see the existing row and no-op. No forced re-freeze is needed because
    #     the single T-40 freeze already carries the latest data.
    # When the tip is UNKNOWN (slate_meta empty), fall back to the legacy static
    # behaviour: freeze on the first fire + optional late re-freeze at
    # LATE_REFREEZE_AFTER_UTC (D75), gated by the D83 lock gate.
    now_utc = dt.datetime.now(dt.UTC)
    lock_time = _load_slate_lock_time(sd)
    deadline = _freeze_deadline_utc(lock_time, settings)

    force_refreeze = False
    if deadline is not None:
        if _in_pre_freeze_window(now_utc, deadline):
            log.info(
                "job2_pre_freeze_window",
                slate_date=sd,
                deadline_utc=deadline.isoformat(),
                now_utc=now_utc.isoformat(),
            )
            return Job2Result(sd, model_sha, rec, False, "pre_freeze_window")
    elif settings.late_refreeze_enabled:
        # tip unknown: legacy static late-refreeze trigger (D75).
        try:
            h, m = (int(x) for x in settings.late_refreeze_after_utc.split(":"))
            cutoff = now_utc.replace(hour=h, minute=m, second=0, microsecond=0)
            force_refreeze = now_utc >= cutoff
        except (ValueError, AttributeError):
            log.warning("job2_late_refreeze_bad_config", val=settings.late_refreeze_after_utc)
        if force_refreeze:
            allowed, gate_reason = _late_refreeze_allowed(now_utc, lock_time, settings)
            if not allowed:
                force_refreeze = False
                log.warning(
                    "job2_late_refreeze_gated",
                    slate_date=sd,
                    reason=gate_reason,
                    lock_time_utc=lock_time.isoformat() if lock_time else None,
                )
                try:
                    from wnba_oracle.scheduler.watchdog import (
                        SEVERITY_WARN,
                        WatchdogEvent,
                        persist_events,
                    )

                    persist_events(
                        [
                            WatchdogEvent(
                                slate_date=sd,
                                trigger="late_refreeze_gated",
                                severity=SEVERITY_WARN,
                                payload={
                                    "reason": gate_reason,
                                    "lock_time_utc": (lock_time.isoformat() if lock_time else None),
                                },
                            )
                        ]
                    )
                except Exception as exc:
                    log.warning("job2_gate_event_failed", reason=str(exc)[:120])

    # D90: capture the curve + serving knobs the optimizer used so the
    # placement reader can later join the freeze-time forecast to the
    # realized outcome. Strings/floats only (no Decimal/NaN) so the JSONB
    # column round-trips cleanly.
    payout_curve_payload = {
        "regime": curve.regime,
        "cash_line_percentile": curve.cash_line_percentile,
        "percentile_to_payout": {str(k): float(v) for k, v in curve.percentile_to_payout.items()},
    }
    serving_knobs_payload = {
        "n_samples": cfg.n_samples,
        "n_field_lineups": cfg.n_field_lineups,
        "top_n_filter": cfg.top_n_filter,
        "max_per_team": cfg.max_per_team,
        "min_anchors": cfg.min_anchors,
        "boost_sum_cap": cfg.boost_sum_cap,
        "max_single_boost": cfg.max_single_boost,
        "game_stack_bonus": cfg.game_stack_bonus,
        "leverage_weight": cfg.leverage_weight,
        "ceiling_weight": cfg.ceiling_weight,
        "duplication_weight": cfg.duplication_weight,
        "field_same_game_boost": cfg.field_same_game_boost,
        "field_same_team_boost": cfg.field_same_team_boost,
        "duplication_aware_payout": cfg.duplication_aware_payout,
        "never_skip": cfg.never_skip,
        "caveat_is_skip": cfg.caveat_is_skip,
    }
    frozen = _freeze(
        sd,
        model_sha,
        rec,
        curve.regime,
        projection_by_pid,
        force=force_refreeze,
        payout_curve=payout_curve_payload,
        serving_knobs=serving_knobs_payload,
    )
    status = (
        "ok" if frozen else ("already_frozen" if not force_refreeze else "late_refreeze_skipped")
    )
    # Shadow-eval the challenger head against the same enrichment. Guarded:
    # any failure logs and returns without touching the freeze result. The
    # writer is idempotent per (slate_date, challenger_sha) via ON CONFLICT
    # so the every-15-min cron cadence naturally dedups. Realized delta is
    # backfilled in dayclose once slate_labels finalize.
    if settings.model_challenger_sha or getattr(settings, "picker_knob_challenger_json", ""):
        try:
            from wnba_oracle.scheduler.shadow import (
                _maybe_run_knob_shadow,
                _maybe_run_shadow,
            )

            # Reload the incumbent here rather than plumbing it out of
            # _build_specs -- the artifact is cached by _load_model_artifact
            # in practice, so this is a no-cost second call.
            incumbent_art = _load_model_artifact(settings.model_artifact_sha)
            incumbent_head = _predict_heads_for_pool(incumbent_art, enrichment)
            boost_by_pid = {
                int(r["real_sports_player_id"]): float(r.get("card_boost", 0.0) or 0.0)
                for r in enrichment
                if r.get("real_sports_player_id") is not None
            }
            if settings.model_challenger_sha:
                _maybe_run_shadow(
                    sd,
                    enrichment,
                    incumbent_sha=model_sha,
                    incumbent_head=incumbent_head,
                    boost_by_pid=boost_by_pid,
                    challenger_sha=settings.model_challenger_sha,
                )
            overlay_json = getattr(settings, "picker_knob_challenger_json", "")
            if overlay_json:
                _maybe_run_knob_shadow(
                    sd,
                    enrichment,
                    incumbent_sha=model_sha,
                    incumbent_head=incumbent_head,
                    boost_by_pid=boost_by_pid,
                    overlay_json=overlay_json,
                )
        except Exception as exc:
            log.warning("shadow_run_wrapper_failed", reason=str(exc)[:160])
    return Job2Result(sd, model_sha, rec, frozen, status)


def main() -> int:
    configure_logging("INFO")
    settings = get_settings()
    sd = dt.date.today().isoformat()
    try:
        result = run(sd, dry_run=settings.job2_dry_run)
    except Exception as exc:
        log.exception("job2_failed", error=str(exc))
        return 1
    if result.recommendation is None:
        return 0
    return 0

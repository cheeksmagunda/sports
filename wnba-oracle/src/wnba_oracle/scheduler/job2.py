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
from dataclasses import dataclass
from typing import Any

import numpy as np

from wnba_oracle.common.clock import slate_date as current_slate_date
from wnba_oracle.common.logging import configure_logging, get_logger
from wnba_oracle.common.settings import Settings, get_settings
from wnba_oracle.db.engine import get_engine
from wnba_oracle.features.game_script_minutes import (
    GameScriptInput,
    GameScriptMinutesConfig,
    blowout_probability,
    redistribute_game_script_minutes,
)
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

    @property
    def exit_code(self) -> int:
        """Map operational outcomes to a stable process contract."""
        failures = {
            "model_artifact_unset",
            "model_artifact_invalid",
            "pool_too_small",
            "specs_too_small",
            "freeze_not_persisted",
        }
        return 1 if self.reason in failures else 0


# The scoring helpers, DB loaders, model/prediction tier, timing gates,
# and freeze persistence live in sibling job2_* modules so this module
# can focus on spec building + freeze orchestration. Re-imported here
# because tests and scripts reference them via ``job2._name``, and
# because the orchestration below resolves them through this module's
# globals, which keeps monkeypatching on job2 effective.
from wnba_oracle.scheduler.job2_freeze import (  # noqa: E402
    FREEZE_LEASE_TTL_SECONDS,
    FROZEN_APPEND,
    FROZEN_EXISTS,
    FROZEN_OPERATION_EXISTS,
    _build_per_player,
    _freeze,
    _release_freeze_lock,
)
from wnba_oracle.scheduler.job2_io import (  # noqa: E402
    SLATE_LOCK_Q,
    _load_enrichment,
    _load_measured_drafts,
    _load_player_history,
    _load_prior_real_scores,
    _load_slate_label_names,
    _load_slate_lock_time,
)
from wnba_oracle.scheduler.job2_model import (  # noqa: E402
    REPO_ROOT,
    _eb_predict_one,
    _load_model_artifact,
    _predict_heads_for_pool,
)
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
from wnba_oracle.scheduler.job2_timing import (  # noqa: E402
    _freeze_deadline_utc,
    _game_start_utc,
    _in_pre_freeze_window,
    _late_refreeze_allowed,
    scope_to_upcoming_games,
)

__all__ = [
    "FREEZE_LEASE_TTL_SECONDS",
    "FROZEN_APPEND",
    "FROZEN_EXISTS",
    "FROZEN_OPERATION_EXISTS",
    "REPO_ROOT",
    "SLATE_LOCK_Q",
    "_build_per_player",
    "_cascade_bonuses",
    "_eb_predict_one",
    "_effective_confirmed",
    "_features_dict",
    "_floor_tilt_multiplier",
    "_freeze",
    "_freeze_deadline_utc",
    "_game_start_utc",
    "_heuristic_real_score",
    "_in_pre_freeze_window",
    "_is_out_from_features",
    "_late_refreeze_allowed",
    "_load_enrichment",
    "_load_measured_drafts",
    "_load_model_artifact",
    "_load_player_history",
    "_load_prior_real_scores",
    "_load_slate_label_names",
    "_load_slate_lock_time",
    "_minutes_features",
    "_predict_heads_for_pool",
    "_prop_signal_multiplier",
    "_release_freeze_lock",
    "_starter_minutes_lift",
    "_starter_multiplier",
    "_vegas_from_features",
    "scope_to_upcoming_games",
]


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
    n_min_games_by_pid: dict[int, int] = {}
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
        n_min_games_by_pid[pid] = int(mf["n_min_games"]) if mf is not None else 0
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
        n_min_games = n_min_games_by_pid.get(pid, 0)
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


def run(slate_date: str | None = None, *, dry_run: bool = False) -> Job2Result:
    settings = get_settings()
    sd = slate_date or current_slate_date().isoformat()
    model_sha = settings.model_artifact_sha or "heuristic-v1"

    log.info("job2_start", slate_date=sd, model_sha=model_sha)
    if getattr(settings, "env", "dev") == "prod":
        if not settings.model_artifact_sha:
            log.error("job2_model_artifact_required", slate_date=sd)
            return Job2Result(sd, model_sha, None, False, "model_artifact_unset")
        if _load_model_artifact(settings.model_artifact_sha) is None:
            log.error("job2_model_artifact_invalid", slate_date=sd, sha=model_sha[:12])
            return Job2Result(sd, model_sha, None, False, "model_artifact_invalid")
    enrichment_raw = _load_enrichment(sd)
    # D109 pool scope: exclude players whose game already tipped. Applied
    # before the injury cascade so OUT-minutes only redistribute inside the
    # games still ahead. The earliest remaining tip becomes this run's lock
    # time: the freeze deadline that matters is the first game we can still
    # enter, not the slate's first tip (already in the past by definition).
    now_utc = dt.datetime.now(dt.UTC)
    upcoming_tip: dt.datetime | None = None
    n_started = 0
    if settings.pool_exclude_started_games:
        scoped, upcoming_tip, n_started, n_unknown = scope_to_upcoming_games(
            enrichment_raw, now_utc
        )
        log.info(
            "job2_pool_scoped_to_upcoming",
            slate_date=sd,
            n_before=len(enrichment_raw),
            n_after=len(scoped),
            n_started=n_started,
            n_unknown_start=n_unknown,
            upcoming_tip_utc=upcoming_tip.isoformat() if upcoming_tip else None,
        )
        enrichment_raw = scoped
        if not enrichment_raw:
            log.warning("job2_no_upcoming_games", slate_date=sd, n_started=n_started)
            return Job2Result(sd, model_sha, None, False, "no_upcoming_games")

    # Resolve the app-owned slate deadline before feature construction and
    # optimization. Scheduled fires before the window have no committable
    # output, so doing the expensive work first only wastes provider and CPU
    # budget. Dry runs intentionally bypass this gate for diagnostics.
    lock_time = upcoming_tip or _load_slate_lock_time(sd)
    deadline = _freeze_deadline_utc(lock_time, settings)
    if not dry_run and deadline is not None and _in_pre_freeze_window(now_utc, deadline):
        log.info(
            "job2_pre_freeze_window",
            slate_date=sd,
            deadline_utc=deadline.isoformat(),
            now_utc=now_utc.isoformat(),
        )
        return Job2Result(sd, model_sha, None, False, "pre_freeze_window")
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
    force_refreeze = False
    frozen_via_override: str | None = None
    if settings.pool_exclude_started_games and upcoming_tip is not None and n_started > 0:
        # A game has tipped since the slate froze, so the frozen lineup was
        # drawn partly from players nobody can still draft. Append a scoped
        # freeze so the operator sees an enterable lineup, gated by the same
        # D83 lock buffer against the game we are actually entering. Before
        # the first tip (n_started == 0) the scope is a no-op and freeze
        # semantics are untouched: one freeze per slate, never re-rolled.
        try:
            eng = get_engine()
            with eng.connect() as conn:
                already = conn.execute(FROZEN_EXISTS, {"sd": sd, "ms": model_sha}).first()
        except Exception as exc:
            log.warning("job2_frozen_exists_check_failed", reason=str(exc)[:120])
            already = None
        if already:
            allowed, gate_reason = _late_refreeze_allowed(now_utc, upcoming_tip, settings)
            if allowed:
                force_refreeze = True
                frozen_via_override = "job2_upcoming_games_only"
            else:
                log.warning(
                    "job2_upcoming_refreeze_gated",
                    slate_date=sd,
                    reason=gate_reason,
                    upcoming_tip_utc=upcoming_tip.isoformat(),
                )
                return Job2Result(sd, model_sha, rec, False, "upcoming_refreeze_gated")
    if deadline is None and settings.late_refreeze_enabled:
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
        via=frozen_via_override,
    )
    if frozen:
        status = "ok"
    elif force_refreeze:
        status = "late_refreeze_skipped"
    else:
        # A Redis lock miss is only an expected no-op if the canonical
        # Postgres row now exists. Otherwise this run produced no durable
        # lineup and must be retried as a failure, not mislabeled frozen.
        with get_engine().connect() as conn:
            persisted = conn.execute(FROZEN_EXISTS, {"sd": sd, "ms": model_sha}).first()
        status = "already_frozen" if persisted else "freeze_not_persisted"
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
    sd = current_slate_date().isoformat()
    try:
        result = run(sd, dry_run=settings.job2_dry_run)
    except Exception as exc:
        log.exception("job2_failed", error=str(exc))
        return 1
    log.info(
        "job2_complete",
        slate_date=result.slate_date,
        outcome=result.reason,
        frozen=result.frozen,
        exit_code=result.exit_code,
    )
    return result.exit_code

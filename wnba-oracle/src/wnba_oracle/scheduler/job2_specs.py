"""Job 2 spec building: per-player prediction tiers, sampling/field specs,
and archetype classification.

Extracted from job2.py's ``_build_specs``, which had grown into a single
~540-line function threading a dozen per-player accumulator dicts through
three phases: popularity scoring, the tiered real_score/minutes predictor
(D45 EB baseline -> D63/D69 trained heads -> D55 minutes edge -> boost
heuristic, plus the D57 game-script/availability/anchor machinery), and
spec/projection materialization (D89 ceiling sigma, D105 archetypes). Each
phase is now a function with an explicit input/output contract; job2._build_specs
composes them in the same order the original code ran them, so this is a
pure reorganization -- no tier, multiplier, or ordering changed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from wnba_oracle.common.logging import get_logger
from wnba_oracle.common.settings import Settings
from wnba_oracle.features.game_script_minutes import (
    GameScriptInput,
    GameScriptMinutesConfig,
    blowout_probability,
    redistribute_game_script_minutes,
)
from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.game_script import GameScriptConfig, game_script_multiplier
from wnba_oracle.picker.popularity import estimate_draft_popularity, slate_labels_to_popularity
from wnba_oracle.picker.sample import PlayerSamplingSpec, ceiling_adjusted_sigma_log
from wnba_oracle.predict.archetypes import ArchetypeInput, classify_pool
from wnba_oracle.predict.availability import AvailabilityConfig, availability_probability
from wnba_oracle.predict.minutes import (
    MinutesConfig,
    blended_real_score,
    minutes_interval_from_projection,
    minutes_interval_from_role,
    project_minutes_from_base,
)
from wnba_oracle.scheduler.job2_model import _eb_predict_one
from wnba_oracle.scheduler.job2_scoring import (
    _effective_confirmed,
    _features_dict,
    _floor_tilt_multiplier,
    _heuristic_real_score,
    _minutes_features,
    _prop_signal_multiplier,
    _starter_minutes_lift,
    _starter_multiplier,
    _vegas_from_features,
)
from wnba_oracle.train.pipeline import PickerArtifact

log = get_logger("oracle.job2")

# Anchor definition for the Tier 1 lineup anchor floor (D57): a player we are
# confident logs real minutes tonight. Either an established rotation player
# (>= ANCHOR_MIN_GAMES recent games averaging >= ANCHOR_MIN_MINUTES) or a
# RotoWire-confirmed starter. Cold-start darts (no minutes history) are NOT
# anchors -- they are exactly the boost longshots that sank 2026-06-01.
ANCHOR_MIN_GAMES = 3
ANCHOR_MIN_MINUTES = 20.0


def _compute_popularity_scores(
    enrichment: list[dict], measured_drafts: dict[int, int]
) -> dict[int, float]:
    """Popularity used by the anti-popularity contrarian adjustment.

    Prefers measured `drafts` from slate_labels; falls back to the
    card_boost-as-pseudo-ppg estimator when no contest has finalized yet.
    """
    if measured_drafts:
        scores = slate_labels_to_popularity(measured_drafts)
        log.info("contrarian_using_measured", n_measured=len(scores))
        return scores

    # Slate-size signal for the popularity estimator
    n_games_on_slate = len({str(r.get("team", "") or "") for r in enrichment if r.get("team")}) // 2
    n_games_on_slate = max(n_games_on_slate, 1)

    # Estimator fallback: use card_boost as a weak proxy for season_ppg
    # since we don't yet ingest per-player season stats. card_boost is
    # inverse to rolling Real Rating average, so 3.0 -> cold star,
    # 0.0 -> hot star. We invert it.
    estimated_scores: dict[int, float] = {}
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
        estimated_scores[pid] = estimate_draft_popularity(
            season_ppg=pseudo_ppg,
            team=str(r.get("team", "") or ""),
            n_games_on_slate=n_games_on_slate,
        )
    return estimated_scores


@dataclass
class PlayerPredictions:
    """Per-pid accumulator bundle produced by ``predict_players``.

    ``pred_real_scores`` already has the D57 game-script-minutes delta and
    the D57 Tier-2 availability hurdle applied -- it is ready for the
    contrarian adjustment, not an intermediate value.
    """

    pred_real_scores: dict[int, float] = field(default_factory=dict)
    rank_pred_by_pid: dict[int, float] = field(default_factory=dict)
    rows_by_pid: dict[int, dict] = field(default_factory=dict)
    minutes_vol_by_pid: dict[int, float] = field(default_factory=dict)
    pred_minutes_by_pid: dict[int, tuple[float, float, float]] = field(default_factory=dict)
    blowout_prob_by_pid: dict[int, float] = field(default_factory=dict)
    is_starter_by_pid: dict[int, bool] = field(default_factory=dict)
    is_anchor_by_pid: dict[int, bool] = field(default_factory=dict)
    p_active_by_pid: dict[int, float] = field(default_factory=dict)
    n_min_games_by_pid: dict[int, int] = field(default_factory=dict)
    head_quantiles_by_pid: dict[int, dict[str, float]] = field(default_factory=dict)


def predict_players(
    enrichment: list[dict],
    *,
    settings: Settings,
    art: PickerArtifact | None,
    head_predictions: dict[int, dict[str, float]],
    player_history: dict[int, float] | None,
    bonus: dict[int, float],
) -> PlayerPredictions:
    """The tiered per-player real_score + minutes predictor (D45/D55/D57/D63/D69).

    Ladder per player: D69/D63 trained quantile heads -> D55 minutes-edge
    blend -> D45 EB baseline -> corpus history -> boost heuristic, each with
    its own starter/game-script/floor-tilt multipliers. After the loop,
    folds in the D57 game-script-minutes redistribution and the D57 Tier-2
    availability hurdle so the returned ``pred_real_scores`` is the final
    pre-contrarian prediction.
    """
    gsm_enabled = settings.game_script_minutes_enabled
    gsm_cfg = GameScriptMinutesConfig()
    # When the role-aware blowout redistribution is on it OWNS the blowout
    # effect, so disable the blunt team-wide blowout penalty to avoid
    # double-counting (D57).
    gs_cfg = GameScriptConfig(blowout_penalty=1.0) if gsm_enabled else GameScriptConfig()
    mcfg = MinutesConfig()
    avail_enabled = settings.availability_model_enabled
    avail_cfg = AvailabilityConfig()

    preds = PlayerPredictions()
    gsm_rows: list[GameScriptInput] = []
    rate_by_pid: dict[int, float] = {}
    n_head_predicted = 0
    n_minutes_predicted = 0
    n_eb_predicted = 0
    n_history_fallback = 0
    n_heuristic_fallback = 0

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
        preds.n_min_games_by_pid[pid] = int(mf["n_min_games"]) if mf is not None else 0
        # Anchor flag (D57, Tier 1) -- computed regardless of the floor setting
        # so it always rides on the spec; the optimizer only enforces it when
        # min_anchors > 0.
        preds.is_anchor_by_pid[pid] = (
            mf is not None
            and mf["n_min_games"] >= ANCHOR_MIN_GAMES
            and mf["recent_minutes"] >= ANCHOR_MIN_MINUTES
        ) or (eff_confirmed and bool(int(f.get("is_starter", 0) or 0)))
        if avail_enabled:
            preds.p_active_by_pid[pid] = availability_probability(
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
            preds.blowout_prob_by_pid[pid] = blowout_probability(abs(spread), gsm_cfg)
            recent_min_gs = float(mf["recent_minutes"]) if mf is not None else 0.0
            preds.is_starter_by_pid[pid] = (
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
            preds.pred_real_scores[pid] = max(
                0.5, p50 * gs_mult * starter_mult * prop_mult * floor_mult
            )
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
                preds.rank_pred_by_pid[pid] = max(
                    0.5, p50 * lift_factor * gs_mult * starter_mult * prop_mult * floor_mult
                )
            # 80% interval (~2.56 sigma) -> additive real_score volatility. Same
            # semantic as `minutes_vol_by_pid` for the Tier-1 path so the
            # sampler's delta-method conversion works unchanged. starter_mult
            # is applied so the spread stays proportional to the shifted mean.
            hp_spread = max(0.0, p90 - p10) * starter_mult / 2.56
            preds.minutes_vol_by_pid[pid] = max(0.5, hp_spread)
            preds.head_quantiles_by_pid[pid] = {
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
                preds.pred_minutes_by_pid[pid] = minutes_interval_from_projection(
                    m50, float(mf["minutes_vol"]), cfg=mcfg
                )
            else:
                preds.pred_minutes_by_pid[pid] = minutes_interval_from_role(
                    rotowire_confirmed=eff_confirmed,
                    is_starter=is_starter_flag,
                    cfg=mcfg,
                )
            n_head_predicted += 1
            preds.rows_by_pid[pid] = r
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
            preds.pred_real_scores[pid] = max(0.5, base * gs_mult)
            preds.minutes_vol_by_pid[pid] = mf["minutes_vol"] * mf["per_min_rate"]
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
            preds.pred_minutes_by_pid[pid] = minutes_interval_from_projection(
                m50_t1, float(mf["minutes_vol"]), cfg=mcfg
            )
            n_minutes_predicted += 1
            preds.rows_by_pid[pid] = r
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
        preds.pred_real_scores[pid] = max(0.5, base * gs_mult * starter_mult)
        # Tier-3 minutes interval: no per-player minutes history, so we anchor
        # on the confirmed-role signal (starter -> ~30 min, bench -> ~13 min,
        # unknown -> wide 20-min band). Consistent with how _starter_multiplier
        # tilts the real_score in this same branch.
        preds.pred_minutes_by_pid[pid] = minutes_interval_from_role(
            rotowire_confirmed=eff_confirmed,
            is_starter=bool(int(f.get("is_starter", 0) or 0)),
            cfg=mcfg,
        )
        preds.rows_by_pid[pid] = r

    if gsm_enabled and gsm_rows:
        # Convert the signed minute deltas to real_score via each player's
        # per-minute rate, then fold into pred_real_score (D57). Bench up,
        # starters down; floored at 0.5 like every other predictor branch.
        deltas_min = redistribute_game_script_minutes(gsm_rows, gsm_cfg)
        n_bumped = sum(1 for d in deltas_min.values() if d > 0)
        n_trimmed = sum(1 for d in deltas_min.values() if d < 0)
        for pid_d, dmin in deltas_min.items():
            rate = rate_by_pid.get(pid_d, mcfg.league_rate)
            preds.pred_real_scores[pid_d] = max(
                0.5, preds.pred_real_scores[pid_d] + dmin * rate
            )
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

    if avail_enabled and preds.p_active_by_pid:
        # Two-part hurdle (D57, Tier 2): scale each active-conditional pred by
        # P(active). Cold-start darts collapse; established players ~unchanged.
        n_low = 0
        for pid_a, p_act in preds.p_active_by_pid.items():
            if pid_a in preds.pred_real_scores:
                preds.pred_real_scores[pid_a] = max(0.5, preds.pred_real_scores[pid_a] * p_act)
                if p_act < 0.5:
                    n_low += 1
        log.info(
            "availability_model", n_players=len(preds.p_active_by_pid), n_low_availability=n_low
        )

    return preds


def materialize_specs(
    adjusted: dict[int, float],
    *,
    preds: PlayerPredictions,
    settings: Settings,
    measured_drafts: dict[int, int],
    label_names: dict[int, str],
    K: float,
    volatility: dict[int, float],
) -> tuple[list[PlayerSamplingSpec], list[FieldPlayerSpec], dict[int, dict[str, Any]]]:
    """Build the (sampling, field, projection) triple from the final
    contrarian-adjusted predictions.

    ``K``/``volatility`` are the sampling-sigma inputs (D52/D55); ``adjusted``
    is ``preds.pred_real_scores`` after ``apply_contrarian_adjustment``.
    """
    samps: list[PlayerSamplingSpec] = []
    fields: list[FieldPlayerSpec] = []
    projection_by_pid: dict[int, dict[str, Any]] = {}
    for pid, pred in adjusted.items():
        r = preds.rows_by_pid[pid]
        team = str(r.get("team", "") or "")
        opp = str(r.get("opponent", "") or "")
        boost = float(r.get("card_boost", 0.0) or 0.0)
        mu_log = float(np.log(max(pred + K, 1.0)))
        # Convert the real_score-unit volatility to a log-scale sigma via the
        # delta method: std(real) ~= (pred + K) * sigma_log. Clamp to a sane
        # band so a single outlier game can't blow up the percentile bias.
        vol = preds.minutes_vol_by_pid.get(int(pid)) or volatility.get(int(pid), 1.17)
        sigma_log = min(0.6, max(0.12, vol / max(pred + K, 1e-6)))
        # D89 (Phase 4): environment-conditioned ceiling sigma boost. Widens
        # the per-player marginal sigma when the game has blowout
        # uncertainty (role volatility) and/or the player has limited
        # recent history (sample-size shrinkage). Both default to 0.0 so
        # the path is byte-identical until armed via env var.
        n_min_games = preds.n_min_games_by_pid.get(pid, 0)
        sigma_log = ceiling_adjusted_sigma_log(
            sigma_log,
            blowout_prob=preds.blowout_prob_by_pid.get(pid, 0.0),
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
                is_starter=preds.is_starter_by_pid.get(pid, False),
                blowout_prob=preds.blowout_prob_by_pid.get(pid, 0.0),
                is_anchor=preds.is_anchor_by_pid.get(pid, False),
                p_active=preds.p_active_by_pid.get(
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
                rank_pred_override=preds.rank_pred_by_pid.get(pid),
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
        hq = preds.head_quantiles_by_pid.get(pid)
        if hq is not None:
            proj["pred_real_score_p10"] = float(hq["p10"])
            proj["pred_real_score_p90"] = float(hq["p90"])
        mp = preds.pred_minutes_by_pid.get(pid)
        if mp is not None:
            p10m, p50m, p90m = mp
            proj["pred_minutes_p10"] = float(p10m)
            proj["pred_minutes_p50"] = float(p50m)
            proj["pred_minutes_p90"] = float(p90m)
        projection_by_pid[pid] = proj

    return samps, fields, projection_by_pid


def attach_archetypes(
    projection_by_pid: dict[int, dict[str, Any]],
    *,
    rows_by_pid: dict[int, dict],
    is_anchor_by_pid: dict[int, bool],
) -> None:
    """D105: attach the DFS value archetype to each player's projection dict,
    in place. Derived from the MLB highest-value archetype analysis:
    ceiling_anchor (high-usage starter on high-total team), efficient_producer
    (high-leverage stat concentration), leverage_spike (cheap confirmed
    starter), plus a streaking tag. Metadata-only -- does not change
    predictions or optimizer behaviour.
    """
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
    if not archetype_inputs:
        return
    archetype_labels = classify_pool(archetype_inputs)
    for pid, label in archetype_labels.items():
        if pid in projection_by_pid:
            projection_by_pid[pid]["archetype"] = label.primary
            if label.is_streaking:
                projection_by_pid[pid]["streak_driver"] = label.streak_driver
                projection_by_pid[pid]["streak_quality"] = label.streak_quality
            projection_by_pid[pid]["stat_leverage"] = label.stat_leverage

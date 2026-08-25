"""Model-kernel spec building: per-player prediction tiers, sampling/field specs,
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
from wnba_oracle.features.game_script_minutes import (
    GameScriptInput,
    GameScriptMinutesConfig,
    blowout_probability,
    redistribute_game_script_minutes,
)
from wnba_oracle.modeling.artifact import PickerArtifactLike, eb_predict_one
from wnba_oracle.modeling.policy import ModelPolicy
from wnba_oracle.modeling.scoring import (
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


@dataclass
class _PredictorMix:
    head: int = 0
    minutes: int = 0
    eb: int = 0
    history: int = 0
    heuristic: int = 0


@dataclass(frozen=True)
class _PredictionContext:
    policy: ModelPolicy
    artifact: PickerArtifactLike | None
    head_predictions: dict[int, dict[str, float]]
    player_history: dict[int, float] | None
    bonus: dict[int, float]
    game_script_minutes_enabled: bool
    game_script_minutes_cfg: GameScriptMinutesConfig
    game_script_cfg: GameScriptConfig
    minutes_cfg: MinutesConfig
    availability_enabled: bool
    availability_cfg: AvailabilityConfig


@dataclass
class _PredictionWork:
    predictions: PlayerPredictions = field(default_factory=PlayerPredictions)
    game_script_rows: list[GameScriptInput] = field(default_factory=list)
    rate_by_pid: dict[int, float] = field(default_factory=dict)
    mix: _PredictorMix = field(default_factory=_PredictorMix)


@dataclass(frozen=True)
class _PlayerContext:
    row: dict
    pid: int
    boost: float
    position: str
    total: float
    spread: float
    game_script_multiplier: float
    features: dict
    effective_confirmed: bool
    minutes: dict | None


def _register_player_state(
    player: _PlayerContext,
    context: _PredictionContext,
    work: _PredictionWork,
) -> None:
    predictions = work.predictions
    minutes = player.minutes
    is_starter = bool(int(player.features.get("is_starter", 0) or 0))
    predictions.n_min_games_by_pid[player.pid] = (
        int(minutes["n_min_games"]) if minutes is not None else 0
    )
    predictions.is_anchor_by_pid[player.pid] = (
        minutes is not None
        and minutes["n_min_games"] >= ANCHOR_MIN_GAMES
        and minutes["recent_minutes"] >= ANCHOR_MIN_MINUTES
    ) or (player.effective_confirmed and is_starter)

    if context.availability_enabled:
        predictions.p_active_by_pid[player.pid] = availability_probability(
            recent_minutes=float(minutes["recent_minutes"]) if minutes is not None else 0.0,
            minutes_vol=float(minutes["minutes_vol"]) if minutes is not None else 0.0,
            n_min_games=int(minutes["n_min_games"]) if minutes is not None else 0,
            rotowire_confirmed=player.effective_confirmed,
            is_starter=is_starter,
            cfg=context.availability_cfg,
        )

    if context.game_script_minutes_enabled and player.total > 0:
        predictions.blowout_prob_by_pid[player.pid] = blowout_probability(
            abs(player.spread), context.game_script_minutes_cfg
        )
        recent_minutes = float(minutes["recent_minutes"]) if minutes is not None else 0.0
        predictions.is_starter_by_pid[player.pid] = (
            is_starter or recent_minutes >= context.game_script_minutes_cfg.starter_minutes_floor
        )
        if minutes is not None and recent_minutes > 0.0:
            work.game_script_rows.append(
                GameScriptInput(
                    player.pid,
                    str(player.row.get("team", "") or ""),
                    recent_minutes,
                    abs(player.spread),
                )
            )
            work.rate_by_pid[player.pid] = float(minutes["per_min_rate"])


def _apply_head_tier(
    player: _PlayerContext,
    context: _PredictionContext,
    work: _PredictionWork,
) -> bool:
    head = context.head_predictions.get(player.pid)
    if head is None:
        return False

    policy = context.policy
    predictions = work.predictions
    p10 = head["p10"]
    p50 = head["p50"]
    p90 = head["p90"]
    starter_multiplier = _starter_multiplier(
        player.row.get("features_json"),
        enabled=policy.starter_signal_enabled,
        use_expected=policy.starter_signal_use_expected,
        unknown_fade=policy.starter_unknown_fade,
    )
    starter_multiplier *= _starter_minutes_lift(
        player.row.get("features_json"),
        enabled=policy.starter_minutes_lift_enabled,
        use_expected=policy.starter_signal_use_expected,
        norm=policy.starter_minutes_norm,
        weight=policy.starter_minutes_lift_weight,
        cap=policy.starter_minutes_lift_cap,
    )
    prop_multiplier = _prop_signal_multiplier(
        player.row.get("features_json"), scale=policy.prop_signal_scale
    )
    floor_multiplier = _floor_tilt_multiplier(
        p10,
        p50,
        player.boost,
        weight=policy.picker_floor_tilt_weight,
        max_boost=policy.picker_floor_tilt_max_boost,
    )
    predictions.pred_real_scores[player.pid] = max(
        0.5,
        p50
        * player.game_script_multiplier
        * starter_multiplier
        * prop_multiplier
        * floor_multiplier,
    )
    if policy.picker_boost_tail_lift and player.boost >= policy.boost_tail_lift_threshold:
        lift_factor = policy.boost_tail_lift_factor
        predictions.rank_pred_by_pid[player.pid] = max(
            0.5,
            p50
            * lift_factor
            * player.game_script_multiplier
            * starter_multiplier
            * prop_multiplier
            * floor_multiplier,
        )
    head_spread = max(0.0, p90 - p10) * starter_multiplier / 2.56
    predictions.minutes_vol_by_pid[player.pid] = max(0.5, head_spread)
    predictions.head_quantiles_by_pid[player.pid] = {
        "p10": p10 * starter_multiplier,
        "p50": p50 * starter_multiplier,
        "p90": p90 * starter_multiplier,
    }

    is_starter = bool(int(player.features.get("is_starter", 0) or 0))
    minutes = player.minutes
    if minutes is not None and minutes["n_min_games"] >= context.minutes_cfg.min_obs_for_history:
        projected_minutes = project_minutes_from_base(
            float(minutes["recent_minutes"]),
            has_history=True,
            rotowire_confirmed=player.effective_confirmed,
            is_starter=is_starter,
            injury_bonus_min=float(context.bonus.get(player.pid, 0.0)),
            blowout=False,
            cfg=context.minutes_cfg,
        )
        predictions.pred_minutes_by_pid[player.pid] = minutes_interval_from_projection(
            projected_minutes,
            float(minutes["minutes_vol"]),
            cfg=context.minutes_cfg,
        )
    else:
        predictions.pred_minutes_by_pid[player.pid] = minutes_interval_from_role(
            rotowire_confirmed=player.effective_confirmed,
            is_starter=is_starter,
            cfg=context.minutes_cfg,
        )
    predictions.rows_by_pid[player.pid] = player.row
    work.mix.head += 1
    return True


def _apply_minutes_tier(
    player: _PlayerContext,
    context: _PredictionContext,
    work: _PredictionWork,
) -> bool:
    minutes = player.minutes
    if minutes is None or minutes["n_min_games"] < context.minutes_cfg.min_obs_for_history:
        return False
    is_starter = bool(int(player.features.get("is_starter", 0) or 0))
    base = blended_real_score(
        recent_min=minutes["recent_minutes"],
        rate=minutes["per_min_rate"],
        n_games=minutes["n_min_games"],
        boost_prior=_heuristic_real_score(player.boost),
        rotowire_confirmed=player.effective_confirmed,
        is_starter=is_starter,
        injury_bonus_min=float(context.bonus.get(player.pid, 0.0)),
        blowout=False,
        cfg=context.minutes_cfg,
    )
    predictions = work.predictions
    predictions.pred_real_scores[player.pid] = max(0.5, base * player.game_script_multiplier)
    predictions.minutes_vol_by_pid[player.pid] = minutes["minutes_vol"] * minutes["per_min_rate"]
    projected_minutes = project_minutes_from_base(
        float(minutes["recent_minutes"]),
        has_history=True,
        rotowire_confirmed=player.effective_confirmed,
        is_starter=is_starter,
        injury_bonus_min=float(context.bonus.get(player.pid, 0.0)),
        blowout=False,
        cfg=context.minutes_cfg,
    )
    predictions.pred_minutes_by_pid[player.pid] = minutes_interval_from_projection(
        projected_minutes,
        float(minutes["minutes_vol"]),
        cfg=context.minutes_cfg,
    )
    predictions.rows_by_pid[player.pid] = player.row
    work.mix.minutes += 1
    return True


def _apply_fallback_tier(
    player: _PlayerContext,
    context: _PredictionContext,
    work: _PredictionWork,
) -> None:
    policy = context.policy
    starter_multiplier = _starter_multiplier(
        player.row.get("features_json"),
        enabled=policy.starter_signal_enabled,
        use_expected=policy.starter_signal_use_expected,
        unknown_fade=policy.starter_unknown_fade,
    )
    eb_prediction = eb_predict_one(context.artifact, player.pid, player.position)
    if eb_prediction is not None:
        base = eb_prediction
        work.mix.eb += 1
    elif context.player_history is not None and player.pid in context.player_history:
        base = max(0.5, context.player_history[player.pid])
        work.mix.history += 1
    else:
        base = _heuristic_real_score(player.boost)
        work.mix.heuristic += 1
    predictions = work.predictions
    predictions.pred_real_scores[player.pid] = max(
        0.5, base * player.game_script_multiplier * starter_multiplier
    )
    predictions.pred_minutes_by_pid[player.pid] = minutes_interval_from_role(
        rotowire_confirmed=player.effective_confirmed,
        is_starter=bool(int(player.features.get("is_starter", 0) or 0)),
        cfg=context.minutes_cfg,
    )
    predictions.rows_by_pid[player.pid] = player.row


def _apply_game_script_redistribution(
    context: _PredictionContext,
    work: _PredictionWork,
) -> None:
    if not (context.game_script_minutes_enabled and work.game_script_rows):
        return
    deltas = redistribute_game_script_minutes(
        work.game_script_rows,
        context.game_script_minutes_cfg,
    )
    n_bumped = sum(1 for delta in deltas.values() if delta > 0)
    n_trimmed = sum(1 for delta in deltas.values() if delta < 0)
    for pid, delta_minutes in deltas.items():
        rate = work.rate_by_pid.get(pid, context.minutes_cfg.league_rate)
        work.predictions.pred_real_scores[pid] = max(
            0.5,
            work.predictions.pred_real_scores[pid] + delta_minutes * rate,
        )
    log.info(
        "game_script_minutes",
        n_bumped=n_bumped,
        n_trimmed=n_trimmed,
        n_rows=len(work.game_script_rows),
    )


def _apply_availability_hurdle(
    context: _PredictionContext,
    work: _PredictionWork,
) -> None:
    probabilities = work.predictions.p_active_by_pid
    if not (context.availability_enabled and probabilities):
        return
    n_low = 0
    for pid, probability in probabilities.items():
        if pid in work.predictions.pred_real_scores:
            work.predictions.pred_real_scores[pid] = max(
                0.5,
                work.predictions.pred_real_scores[pid] * probability,
            )
            if probability < 0.5:
                n_low += 1
    log.info(
        "availability_model",
        n_players=len(probabilities),
        n_low_availability=n_low,
    )


def predict_players(
    enrichment: list[dict],
    *,
    policy: ModelPolicy,
    art: PickerArtifactLike | None,
    head_predictions: dict[int, dict[str, float]],
    player_history: dict[int, float] | None,
    bonus: dict[int, float],
) -> PlayerPredictions:
    """Build final pre-contrarian predictions through the ordered tier ladder."""
    game_script_minutes_enabled = policy.game_script_minutes_enabled
    context = _PredictionContext(
        policy=policy,
        artifact=art,
        head_predictions=head_predictions,
        player_history=player_history,
        bonus=bonus,
        game_script_minutes_enabled=game_script_minutes_enabled,
        game_script_minutes_cfg=policy.game_script_minutes,
        game_script_cfg=policy.game_script,
        minutes_cfg=policy.minutes,
        availability_enabled=policy.availability_model_enabled,
        availability_cfg=policy.availability,
    )
    work = _PredictionWork()

    for row in enrichment:
        raw_player_id = row.get("real_sports_player_id")
        if raw_player_id is None:
            continue
        try:
            player_id = int(raw_player_id)
        except (TypeError, ValueError):
            continue

        total, spread = _vegas_from_features(row.get("features_json"))
        features = _features_dict(row.get("features_json"))
        effective_confirmed = _effective_confirmed(
            features,
            use_expected=policy.starter_signal_use_expected,
        )
        minutes = (
            _minutes_features(row.get("features_json")) if policy.minutes_model_enabled else None
        )
        player = _PlayerContext(
            row=row,
            pid=player_id,
            boost=float(row.get("card_boost", 0.0) or 0.0),
            position=str(row.get("position", "") or ""),
            total=total,
            spread=spread,
            game_script_multiplier=(
                game_script_multiplier(total, spread, cfg=context.game_script_cfg)
                if total > 0
                else 1.0
            ),
            features=features,
            effective_confirmed=effective_confirmed,
            minutes=minutes,
        )
        _register_player_state(player, context, work)
        if _apply_head_tier(player, context, work):
            continue
        if _apply_minutes_tier(player, context, work):
            continue
        _apply_fallback_tier(player, context, work)

    _apply_game_script_redistribution(context, work)
    log.info(
        "predictor_mix",
        artifact_sha=policy.artifact_sha[:12] if policy.artifact_sha else "",
        n_head_predicted=work.mix.head,
        n_minutes_predicted=work.mix.minutes,
        n_eb_predicted=work.mix.eb,
        n_history_fallback=work.mix.history,
        n_heuristic_fallback=work.mix.heuristic,
    )
    _apply_availability_hurdle(context, work)
    return work.predictions


def materialize_specs(
    adjusted: dict[int, float],
    *,
    preds: PlayerPredictions,
    policy: ModelPolicy,
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
        features = _features_dict(r.get("features_json"))
        game_id = str(features.get("game_id") or "").strip()
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
            blowout_boost=policy.ceiling_sigma_blowout_boost,
            low_history_boost=policy.ceiling_sigma_low_history_boost,
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
                game_id=game_id,
            )
        )
        # D86: when enabled, attach the real measured draft count so the field
        # simulation samples opponent lineups from observed ownership instead of
        # a softmax of our own projections. measured_drafts was loaded above for
        # the contrarian penalty; here it also grounds the EV/leverage math.
        md = (
            float(measured_drafts[pid])
            if (policy.field_measured_ownership_enabled and pid in measured_drafts)
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
        if game_id:
            proj["game_id"] = game_id
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

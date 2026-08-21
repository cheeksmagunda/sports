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

from wnba_oracle.common.clock import slate_date as current_slate_date
from wnba_oracle.common.logging import configure_logging, get_logger
from wnba_oracle.common.settings import Settings, get_settings
from wnba_oracle.db.engine import get_engine
from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.picker.optimize import LineupRecommendation, OptimizeConfig, optimize_lineup
from wnba_oracle.picker.payout import default_curve_for_regime, load_curve_from_archive
from wnba_oracle.picker.popularity import ContrarianConfig, apply_contrarian_adjustment
from wnba_oracle.picker.sample import PlayerSamplingSpec
from wnba_oracle.predict.base import player_volatility

log = get_logger("oracle.job2")


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
from wnba_oracle.scheduler.job2_specs import (  # noqa: E402
    ANCHOR_MIN_GAMES,
    ANCHOR_MIN_MINUTES,
    PlayerPredictions,
    _compute_popularity_scores,
    attach_archetypes,
    materialize_specs,
    predict_players,
)
from wnba_oracle.scheduler.job2_timing import (  # noqa: E402
    _freeze_deadline_utc,
    _game_start_utc,
    _in_pre_freeze_window,
    _late_refreeze_allowed,
    scope_to_upcoming_games,
)

__all__ = [
    "ANCHOR_MIN_GAMES",
    "ANCHOR_MIN_MINUTES",
    "FREEZE_LEASE_TTL_SECONDS",
    "FROZEN_APPEND",
    "FROZEN_EXISTS",
    "FROZEN_OPERATION_EXISTS",
    "REPO_ROOT",
    "SLATE_LOCK_Q",
    "PlayerPredictions",
    "_build_per_player",
    "_cascade_bonuses",
    "_compute_popularity_scores",
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
    "attach_archetypes",
    "materialize_specs",
    "predict_players",
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

    Orchestrates the job2_specs pipeline: popularity scores, the tiered
    per-player predictor, the contrarian adjustment, spec/projection
    materialization, then archetype attachment -- in that order, matching
    the sequence the (formerly inline) implementation ran them in.

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

    measured_drafts = _load_measured_drafts(slate_date)
    popularity_scores = _compute_popularity_scores(enrichment, measured_drafts)

    bonus = injury_bonus_by_pid or {}
    preds = predict_players(
        enrichment,
        settings=settings,
        art=art,
        head_predictions=head_predictions,
        player_history=player_history,
        bonus=bonus,
    )

    # Apply contrarian adjustment
    adjusted = apply_contrarian_adjustment(preds.pred_real_scores, popularity_scores, contrarian_cfg)

    # Per-player sampling sigma from volatility (D52/D55). A flat sigma priced
    # every player the same; ceiling plays (high game-to-game variance) should
    # sample wider so the EV/percentile math sees their upside. Prefer the
    # minutes-derived volatility (minutes_vol x rate, D55) for matched players,
    # else fall back to realized real_score volatility. K and sigma share the
    # same score_offset the copula un-offsets.
    K = float(settings.sampling_score_offset)
    volatility = player_volatility(prior_by_player or {})

    samps, fields, projection_by_pid = materialize_specs(
        adjusted,
        preds=preds,
        settings=settings,
        measured_drafts=measured_drafts,
        label_names=label_names,
        K=K,
        volatility=volatility,
    )

    attach_archetypes(
        projection_by_pid,
        rows_by_pid=preds.rows_by_pid,
        is_anchor_by_pid=preds.is_anchor_by_pid,
    )

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

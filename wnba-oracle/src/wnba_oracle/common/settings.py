"""Pydantic-settings driven config. Single source of truth for env vars."""

from __future__ import annotations

import datetime as dt
from functools import lru_cache
from typing import Literal

from oracle_core.config import MissingRequiredEnvironmentError, RuntimeConfig, SecretValue
from pydantic import Field


class Settings(RuntimeConfig):
    """All environment-driven config with explicit role-specific validation."""

    # External APIs
    odds_api_key: SecretValue = Field(default=SecretValue(""), alias="ODDS_API_KEY")
    real_sports_username: SecretValue = Field(default=SecretValue(""), alias="REAL_SPORTS_USERNAME")
    real_sports_password: SecretValue = Field(default=SecretValue(""), alias="REAL_SPORTS_PASSWORD")
    realsports_storage_state_b64gz: SecretValue = Field(
        default=SecretValue(""), alias="REALSPORTS_STORAGE_STATE_B64GZ"
    )

    @property
    def odds_api_key_value(self) -> str:
        return self.odds_api_key.get_secret_value()

    @property
    def has_legacy_realsports_credentials(self) -> bool:
        return bool(
            self.real_sports_username.get_secret_value()
            and self.real_sports_password.get_secret_value()
        )

    # Operational toggles. Same alias-or-no-injection rule as above.
    job1_dry_run: bool = Field(default=False, alias="JOB1_DRY_RUN")
    job2_dry_run: bool = Field(default=False, alias="JOB2_DRY_RUN")
    # 2026-07-25: operator-directed pause of the picking pipeline (no new
    # picks for a few days). Both are ISO dates (inclusive); job1/job1late/
    # job2 no-op on any day in [start, end] (scheduler/cron.py), and the
    # /slate endpoint reports the pause so the frontend shows a clear
    # "picks are paused" message instead of a stuck countdown. dayclose and
    # backfill are unaffected -- the corpus keeps ingesting during the pause.
    # Unset (empty) on both ends disables the pause entirely.
    picks_pause_start: str = Field(default="", alias="PICKS_PAUSE_START")
    picks_pause_end: str = Field(default="", alias="PICKS_PAUSE_END")
    model_artifact_sha: str = Field(default="", alias="WNBA_ORACLE_MODEL_ARTIFACT_SHA")
    # Shadow-eval challenger. When set on cron-job2, run the challenger's
    # heads over the same enrichment and log a model_shadow_runs row; prod
    # freeze still uses model_artifact_sha. Dayclose backfills
    # realized_value_delta once slate_labels finalize.
    model_challenger_sha: str = Field(default="", alias="WNBA_ORACLE_MODEL_CHALLENGER_SHA")
    # 2026-07-04 knob-shadow. JSON overlay of picker knobs to shadow against
    # the incumbent settings at freeze time. Same model SHA on both sides;
    # the shadow row differentiates by a synthesized challenger_sha keyed on
    # the overlay JSON, and payload.overlay records the actual knobs applied.
    # Recognized keys: "starter_unknown_fade" (float, default 1.0),
    # "picker_boost_tail_lift" (bool, default False), "boost_tail_lift_threshold"
    # (float, default 2.0), "boost_tail_lift_factor" (float, default 1.5).
    # Empty string disables. Dayclose backfills the realized delta. See
    # src/wnba_oracle/scheduler/shadow.py:_maybe_run_knob_shadow.
    picker_knob_challenger_json: str = Field(default="", alias="PICKER_KNOB_CHALLENGER_JSON")

    # Lineup optimizer config
    payout_regime: Literal["top_50", "top_20", "top_1"] = Field(
        default="top_20", alias="PAYOUT_REGIME"
    )
    # D56: the prod defaults (5000 samples x 1000 field x C(30,5)=142506 combos)
    # could not finish inside the 15-min cron window -- job2 hung at stage2 and
    # was killed every tick, so NOTHING froze. The backtests that validated the
    # picker used ~300 samples / 50 field / C(20,5), so these reduced defaults
    # are still well above the validated range while completing in ~1-2 min.
    # D76: n_field raised from 120 to 500 based on Monte Carlo SE analysis.
    # At n=120, SE on P(top-20) = ±1.34% vs a signal of 0.22% -- noise 6x signal.
    # At n=500, SE = ±0.66% (3x). Laptop benchmark: +8.6s vs 120. Railway 3x slower
    # → +25s (still within the 15-min cron window). Raise to 1000 via env if VM allows.
    optimizer_n_samples: int = Field(default=1000, alias="OPTIMIZER_N_SAMPLES")
    optimizer_top_n_filter: int = Field(default=20, alias="OPTIMIZER_TOP_N_FILTER")
    optimizer_n_field_lineups: int = Field(default=500, alias="OPTIMIZER_N_FIELD_LINEUPS")
    # max_per_team: caps how many players from one team can appear in a
    # lineup ON 3+ GAME SLATES. 2 is the basketball-main default; 5 disables
    # the cap. Small slates are governed by dynamic_team_cap below.
    optimizer_max_per_team: int = Field(default=2, alias="OPTIMIZER_MAX_PER_TEAM")
    # dynamic_team_cap: relax max_per_team on small slates (D50). On 1-game
    # slates a hard cap of 2 is infeasible (forfeits the slate); on 2-game
    # slates ~32% of top-20 finishers stack 3+. Effective cap: 1 game -> 5,
    # 2 games -> max(max_per_team, 3), 3+ games -> max_per_team. Default
    # True. Set OPTIMIZER_DYNAMIC_TEAM_CAP=false to restore the old static
    # cap (rolls back under 2 minutes via env, no redeploy).
    optimizer_dynamic_team_cap: bool = Field(default=True, alias="OPTIMIZER_DYNAMIC_TEAM_CAP")
    # contrarian_strength: 0.0 disables the anti-popularity penalty; 0.2 is
    # basketball-main's default. Tune up to 0.3 for stronger contrarian tilt
    # in top-1 regime, down to 0.1 for cash games.
    contrarian_strength: float = Field(default=0.2, alias="CONTRARIAN_STRENGTH")
    contrarian_enabled: bool = Field(default=True, alias="CONTRARIAN_ENABLED")
    # caveat_is_skip: when True, demote 'enter_with_caveat' lineups to
    # 'skip'. Conservative interim guardrail for marginal-EV contests
    # (expected_payout in [skip_if, caveat_if)) until the per-slate live
    # calibration logger lands and the caveat threshold can be retuned
    # against placement data rather than the leakage-contaminated 16-slate
    # backtest. Default False preserves current behavior.
    caveat_is_skip: bool = Field(default=False, alias="CAVEAT_IS_SKIP")
    # never_skip: when True (the default), the optimizer never emits a
    # 'skip' recommendation. The product is designed to run every slate
    # and always present the best available lineup, so a marginal- or
    # negative-EV slate is surfaced as 'enter_with_caveat' rather than
    # 'skip'. This supersedes caveat_is_skip (a slate that would be
    # demoted to 'skip' is promoted back to 'enter_with_caveat'). The
    # expected_payout value is still persisted unchanged, so the EV
    # signal is preserved for anyone reading the lineup. Set NEVER_SKIP
    # to false to restore the legacy three-state skip behavior. See D67.
    never_skip: bool = Field(default=True, alias="NEVER_SKIP")
    # sampling_score_offset (K): log(real_score + K) sampling space. D52
    # recalibrated 10 -> 2 so the implied real_score std (~1.1) and right-skew
    # match the corpus. job2 builds mu and the copula un-offsets with this same
    # value. Set SAMPLING_SCORE_OFFSET=10 to restore the pre-D52 sampling.
    sampling_score_offset: float = Field(default=2.0, alias="SAMPLING_SCORE_OFFSET")
    # starter_signal_enabled: modulate predicted real_score by the RotoWire
    # confirmed-starter flag job1 persists (is_starter / rotowire_confirmed).
    # This is the one pre-game signal additive to card_boost (a lagging
    # average can't know tonight's starting five). Default on; set
    # STARTER_SIGNAL_ENABLED=false to disable. See D52.
    starter_signal_enabled: bool = Field(default=True, alias="STARTER_SIGNAL_ENABLED")
    # starter_unknown_fade: multiplicative fade applied to head predictions
    # for players with is_starter=0 AND rotowire_confirmed=0 (RotoWire has no
    # opinion). Calibrated 2026-07-04 against 21 slates of D71+ enrichment:
    # unknowns realize 0.685x the mean real_score of expected starters and DNP
    # at 5.8% vs 0.6%. With the current starter mult of 1.10, an unknown mult
    # of 0.75 matches the empirical ratio and pushes DNP-prone role players
    # down the stage-1 rank. 1.0 disables (pre-2026-07-04 behavior). Applies
    # symmetrically to the head p50 and the p10/p90 interval so the sampler's
    # sigma stays proportional. See scripts/calibrate_starter_and_boost.py.
    starter_unknown_fade: float = Field(default=0.75, alias="STARTER_UNKNOWN_FADE")
    # starter_signal_use_expected: act on RotoWire EXPECTED starters, not only
    # CONFIRMED ones. Confirmed lineups for every game on a slate are not all
    # posted by the T-40 freeze of the first tip (they land ~30-90 min before
    # each game), so a confirmed-only gate silently ignores the starting five on
    # the slate's later games. The expected lineup is available at the 13:00
    # job1 scrape, so we act on it; an expected NON-starter stays neutral (the
    # expected bench order is noisy) -- only a CONFIRMED bench is faded. Default
    # on; set STARTER_SIGNAL_USE_EXPECTED=false to restore confirmed-only. See D104.
    starter_signal_use_expected: bool = Field(default=True, alias="STARTER_SIGNAL_USE_EXPECTED")
    # starter_minutes_lift (2026-07-10, the Kuier/Harris fix): for expected
    # starters whose recent minutes lag the starter norm, lift the head's
    # quantiles by blended_minutes / recent_minutes (blended = pull toward
    # STARTER_MINUTES_NORM at STARTER_MINUTES_LIFT_WEIGHT), capped at
    # STARTER_MINUTES_LIFT_CAP. The Tier-0 head is blind to a same-day
    # promotion (its features carry pre-promotion minutes); Tier-1 already
    # anchors minutes on the confirmed role, so this closes the same gap on
    # the head path. Corpus: expected starters with recent_minutes < 21
    # realize 1.66x naive projection at the median (n=37); the class cost us
    # the slate on 2026-07-05 (Kuier), 07-07 (Kuier), and 07-09 (Harris).
    # Default off so bare Settings() is byte-identical; arm via
    # STARTER_MINUTES_LIFT_ENABLED=true on cron-job2.
    starter_minutes_lift_enabled: bool = Field(default=False, alias="STARTER_MINUTES_LIFT_ENABLED")
    starter_minutes_norm: float = Field(default=25.0, alias="STARTER_MINUTES_NORM")
    starter_minutes_lift_weight: float = Field(default=0.6, alias="STARTER_MINUTES_LIFT_WEIGHT")
    starter_minutes_lift_cap: float = Field(default=1.3, alias="STARTER_MINUTES_LIFT_CAP")
    # picker_floor_tilt (2026-07-10, the Ogunbowale-vs-Shepard fix): blend the
    # sampling/rank center of NON-spike candidates (card_boost <
    # PICKER_FLOOR_TILT_MAX_BOOST) toward their p10 floor:
    # center = (1-w)*p50 + w*p10. Winners' mid slots (1.8/1.6/1.4 multipliers)
    # are floor plays; a wide-interval ceiling candidate fades proportional to
    # its downside spread while a locked-in starter is barely touched. The
    # spike tier (boost >= max_boost) keeps its ceiling treatment. 0.0
    # disables (default); also exposed as a knob-shadow overlay key
    # ("floor_tilt_weight"/"floor_tilt_max_boost") for live A/B before arming.
    picker_floor_tilt_weight: float = Field(default=0.0, alias="PICKER_FLOOR_TILT_WEIGHT")
    picker_floor_tilt_max_boost: float = Field(default=2.0, alias="PICKER_FLOOR_TILT_MAX_BOOST")
    # minutes_model_enabled: use the D55 minutes x rate blended predictor for
    # players job1 matched to nba_api game logs. The one signal orthogonal to
    # card_boost (corr 0.554 vs boost 0.246 walk-forward). Default on; set
    # MINUTES_MODEL_ENABLED=false to fall back to the EB/heuristic predictor
    # for every player (rolls back via env, no redeploy).
    minutes_model_enabled: bool = Field(default=True, alias="MINUTES_MODEL_ENABLED")
    # game_script_minutes_enabled: role-aware blowout minutes redistribution
    # (D57, Tier 3). In a projected blowout, trims starters and pushes the freed
    # minutes to the bench, and feeds the regime-switching copula correlation.
    # Default OFF: this rides on top of the per-player minutes baseline and is a
    # prior to be tuned once the availability engine lands underneath, so it is
    # not enabled in live until validated. Set GAME_SCRIPT_MINUTES_ENABLED=true
    # to turn on (also disables the blunt team-wide blowout penalty to avoid
    # double-counting).
    game_script_minutes_enabled: bool = Field(default=False, alias="GAME_SCRIPT_MINUTES_ENABLED")
    # late_refreeze_enabled: when True, job2 fires after late_refreeze_after_utc
    # (HH:MM, default "23:00") will overwrite the earlier freeze with a fresh
    # optimizer run that reflects late lineup news. The Redis key
    # wnba.late_frozen.{slate_date} prevents multiple late re-freezes per day.
    # Default off. See D75.
    late_refreeze_enabled: bool = Field(default=False, alias="LATE_REFREEZE_ENABLED")
    late_refreeze_after_utc: str = Field(default="23:00", alias="LATE_REFREEZE_AFTER_UTC")
    # D83 lock gate: the late re-freeze must never replace the lineup the
    # operator acted on after the contest locks. When slate_meta carries a
    # lock time (or first-tip proxy), the re-freeze is allowed only until
    # lock minus refreeze_lock_buffer_min minutes. When no lock time is
    # known, late_refreeze_deadline_utc (HH:MM UTC) is a hard stop instead
    # of silently proceeding. 23:30 default = earliest typical WNBA tip.
    refreeze_lock_buffer_min: int = Field(default=10, alias="REFREEZE_LOCK_BUFFER_MIN")
    late_refreeze_deadline_utc: str = Field(default="23:30", alias="LATE_REFREEZE_DEADLINE_UTC")
    # Dynamic freeze gate (deep-dive E). WNBA slates tip at different clock
    # times each day, so the freeze is anchored to the slate's own first tip,
    # not a static UTC slot. job2 freezes at first_tip - freeze_lead_minutes
    # (T-40 by default): it skips fires before that and freezes once at/after
    # it. T-40 lands just after the confirmed-lineup refresh, so the single
    # freeze carries the latest news with ~40 min of margin before lock. The
    # watchdog also escalates a missing freeze relative to this deadline. Falls
    # back to the static late-refreeze cutoff only when slate_meta has no tip.
    # Requires cron-job2 to fire across the day (not just the evening window)
    # so a tick exists near T-40 for any tip time.
    freeze_lead_minutes: int = Field(default=40, alias="FREEZE_LEAD_MINUTES")
    # Pool scope: restrict the optimizer to players whose game has not tipped
    # yet. A WNBA slate spans several tip times; once the early game starts,
    # its players are no longer enterable, so an operator entering late needs
    # a lineup drawn only from the games still ahead. Fails closed: a pool row
    # with no known game start is dropped, because "not yet started" cannot be
    # verified for it. Off by default (the 13:00 pipeline drafts the whole
    # slate before any tip); job1 writes features_json["game_start_utc"].
    pool_exclude_started_games: bool = Field(default=False, alias="POOL_EXCLUDE_STARTED_GAMES")
    # D84 job1 pool sanity gate: a persisted pool below these floors is a
    # hard error (nonzero exit + critical watchdog event), not a quiet log
    # line. The 2026-06-08 morning fire persisted 1 row / 1 team and nothing
    # flagged it. A normal WNBA slate has 60+ players across 4+ teams; the
    # effective row floor is max(JOB1_MIN_POOL, 3 * n_teams).
    job1_min_pool: int = Field(default=12, alias="JOB1_MIN_POOL")
    job1_min_teams: int = Field(default=2, alias="JOB1_MIN_TEAMS")
    # D84 paging: optional healthchecks.io-style URL. When set, any critical
    # watchdog event triggers a best-effort GET to {url}/fail so the operator
    # is paged instead of discovering the failure from a screenshot.
    watchdog_ping_url: str = Field(default="", alias="WATCHDOG_PING_URL")
    # prop_signal_scale: how strongly sportsbook player prop over/under probabilities
    # adjust the head prediction (D78). Formula: pred *= (1 + (over_prob - 0.5) * scale).
    # At scale=0.3: over_prob=0.60 -> +3% adjustment; over_prob=0.40 -> -3%.
    # Only applies when job1 has fetched a prop line for the player. Default 0.0
    # (disabled) until calibrated against placement data. Set PROP_SIGNAL_SCALE=0.3
    # to enable modest prop-based prediction nudge. See D78.
    prop_signal_scale: float = Field(default=0.0, alias="PROP_SIGNAL_SCALE")
    # lineup_anchor_floor (D57, Tier 1 seatbelt): require at least this many
    # confirmed-minutes "anchor" players in the frozen lineup so it can't be all
    # cold-start darts (the 2026-06-01 all-longshot bust). 0 disables (default,
    # current behavior). 2 forces the floor+ceiling barbell the slate winners
    # used. Clamped to anchors present and relaxed if jointly infeasible with the
    # team cap, so it never forfeits a slate. Set LINEUP_ANCHOR_FLOOR=2 on
    # cron-job2 to arm it (env, no redeploy; reverse by unsetting).
    lineup_anchor_floor: int = Field(default=0, alias="LINEUP_ANCHOR_FLOOR")
    # availability_model_enabled (D57, Tier 2): multiply each player's
    # active-conditional predicted real_score by P(active) -- the probability
    # they are in tonight's rotation and log a meaningful shift. Collapses
    # cold-start darts (no rotation evidence -> low P(active)), the 2026-06-01
    # failure mode, while leaving established rotation players ~unchanged.
    # Default OFF; set AVAILABILITY_MODEL_ENABLED=true on cron-job2 to arm.
    availability_model_enabled: bool = Field(default=False, alias="AVAILABILITY_MODEL_ENABLED")
    # Cap the sum-of-card-boost across the 5 picked players. Historical winners
    # clustered near 7.5 total boost; recent busts hit 12-15 with thin minutes
    # history. 0.0 disables. The optimizer relaxes the cap with a warning if no
    # lineup is jointly feasible with the team cap.
    optimizer_boost_sum_cap: float = Field(default=0.0, alias="OPTIMIZER_BOOST_SUM_CAP")
    # Cap the single-pick card_boost. The highest boost bucket was a value trap
    # unless used sparingly. 0.0 disables; 2.5 refuses the 2.5-3.0 lottery tier.
    # Relaxed alongside the sum cap when jointly infeasible.
    optimizer_max_single_boost: float = Field(default=0.0, alias="OPTIMIZER_MAX_SINGLE_BOOST")
    # Game-stack bonus added to expected_payout per stack pair in the combo.
    # A stack pair is two picks in the same game, matched by unordered
    # {team, opponent}. Historical top-20 lineups often include a 2+ same-game
    # group. Default 0.0 disables.
    optimizer_game_stack_bonus: float = Field(default=0.0, alias="OPTIMIZER_GAME_STACK_BONUS")
    # Projections-first contextual balance. When enabled, the optimizer keeps
    # balanced alternatives from the same simulation and accepts the best one
    # within the configured objective margin. Larger advantages may still
    # justify a concentrated lineup. This switch also disables the legacy
    # unconditional stack bonus inside the objective.
    optimizer_contextual_stacking_enabled: bool = Field(
        default=True,
        alias="OPTIMIZER_CONTEXTUAL_STACKING_ENABLED",
    )
    optimizer_contextual_stack_ev_margin: float = Field(
        default=0.01,
        alias="OPTIMIZER_CONTEXTUAL_STACK_EV_MARGIN",
    )
    # D86: feed the real measured draft counts (slate_labels.drafts) into the
    # field-ownership simulation instead of re-deriving the field from our own
    # projections. The estimator builds a strawman field that drafts exactly
    # what our value model likes, so the optimizer cannot see real duplication
    # and underprices leverage (it ships chalk the live field also owns).
    # Default on; FIELD_MEASURED_OWNERSHIP_ENABLED=false reverts to the
    # pre-D86 estimator-only field with no redeploy.
    field_measured_ownership_enabled: bool = Field(
        default=True, alias="FIELD_MEASURED_OWNERSHIP_ENABLED"
    )
    # D87 (Phase 1, objective shaping). Explicit additive corrective terms on
    # top of the rank-based E[payout] objective, each in expected_payout units.
    # All default 0.0 so the optimizer is byte-identical to pre-D87 until armed
    # against placement data.
    #
    #  - LEVERAGE_WEIGHT       : rewards mean(-log own_i) over the 5 picks
    #                            (log-form penalises chalk asymmetrically).
    #  - CEILING_WEIGHT        : rewards (p90 - p50)/p50 of the candidate's
    #                            own lineup-score samples (top-heavy payouts).
    #  - DUPLICATION_WEIGHT    : penalises prod(own_i)*field_size, the expected
    #                            number of mirror entries against our 5-stack.
    optimizer_leverage_weight: float = Field(default=0.0, alias="OPTIMIZER_LEVERAGE_WEIGHT")
    optimizer_ceiling_weight: float = Field(default=0.0, alias="OPTIMIZER_CEILING_WEIGHT")
    optimizer_duplication_weight: float = Field(default=0.0, alias="OPTIMIZER_DUPLICATION_WEIGHT")
    # picker_boost_tail_lift: when True, the stage-1 ranker multiplies the
    # head's pred_p50 by boost_tail_lift_factor for players with card_boost
    # >= boost_tail_lift_threshold. Calibrated 2026-07-04
    # (scripts/calibrate_starter_and_boost.py): high-boost players realize
    # 1.57x their p50 in the corpus (mean_real 1.92 vs mean_pred 1.23 at
    # boost>=2.0), so ranking on the median median-under-values them. We use
    # a multiplicative lift matched to that ratio rather than swapping to
    # pred_p90 -- the head's p90 for role players is a noisy 10x ceiling
    # (their training rows are too sparse to bound the tail). Sampling
    # (mu, sigma) is untouched; only the ranker prefers ceiling for the
    # tail. Off by default so bare Settings() matches pre-fix behaviour.
    picker_boost_tail_lift: bool = Field(default=False, alias="PICKER_BOOST_TAIL_LIFT")
    boost_tail_lift_threshold: float = Field(default=2.0, alias="BOOST_TAIL_LIFT_THRESHOLD")
    boost_tail_lift_factor: float = Field(default=1.5, alias="BOOST_TAIL_LIFT_FACTOR")
    # D107 (Phase 4, ceiling-tilted slots): sort players by p90 percentile
    # instead of p50 median when assigning to slot multipliers. Prioritizes
    # upside in high-multiplier slots for top-heavy contests. Enabled by default
    # (validated with two years of placement data). Set OPTIMIZER_CEILING_TILT_SLOTS=false
    # to revert to rearrangement-inequality (p50-based) behavior.
    optimizer_ceiling_tilt_slots: bool = Field(default=True, alias="OPTIMIZER_CEILING_TILT_SLOTS")
    # D107 (Tier 2, mixture-variance sampling): gate each player's copula draw by
    # Bernoulli(P(active)) to model spike-at-zero (DNP risk) + tail instead of just
    # mean-shifting (expectation form). Creates true bimodal distribution. Enabled by
    # default (correctly models availability risk). Set OPTIMIZER_MIXTURE_VARIANCE_ENABLED=false
    # to revert to expectation-form mean scaling only.
    optimizer_mixture_variance_enabled: bool = Field(
        default=True, alias="OPTIMIZER_MIXTURE_VARIANCE_ENABLED"
    )
    # D88 (Phase 3, stack-aware field). Multiplicative boost on the marginal
    # weight of remaining-pool players that share a game (same-game) or team
    # (same-team) with already-picked field players. Captures the empirical
    # field-stack rate. Defaults of 1.0 leave the independent-pick sampler in
    # place byte-for-byte. Current starting values: same_game=1.4,
    # same_team=1.15.
    field_same_game_boost: float = Field(default=1.0, alias="FIELD_SAME_GAME_BOOST")
    field_same_team_boost: float = Field(default=1.0, alias="FIELD_SAME_TEAM_BOOST")
    # D88 (Phase 3, continued). When True, the optimizer prices duplication
    # directly inside the EV via E[payout(rank) / (1 + dup_count)], the
    # research-preferred treatment over the additive duplication_weight in
    # D87. Default False; arm via OPTIMIZER_DUPLICATION_AWARE_PAYOUT=true.
    optimizer_duplication_aware_payout: bool = Field(
        default=False, alias="OPTIMIZER_DUPLICATION_AWARE_PAYOUT"
    )
    # D89 (Phase 4, ceiling/variance modeling). Environment-conditioned
    # sigma scaling for the per-player lognormal marginal in the copula
    # sampler. The synthesis recommends widening sigma -- not just nudging
    # the mean -- to price upper-tail upside in top-heavy contests. Two
    # additive contributions:
    #
    #  - SIGMA_BLOWOUT_BOOST  : sigma *= (1 + boost * blowout_prob)
    #                           Adds upper-tail mass for games likely to swing
    #                           wide (garbage time, late substitutions).
    #
    #  - SIGMA_LOW_HISTORY_BOOST : sigma *= (1 + boost * (1 - n_games / 25))
    #                              Widens sigma for players with limited
    #                              recent samples so the optimizer's
    #                              percentile math reflects real uncertainty,
    #                              not a tight noisy-mean band.
    #
    # Defaults of 0.0 leave the existing per-player sigma untouched. Recommended
    # starting values from the synthesis: blowout 0.15, low_history 0.20.
    ceiling_sigma_blowout_boost: float = Field(
        default=0.0, alias="OPTIMIZER_CEILING_SIGMA_BLOWOUT_BOOST"
    )
    ceiling_sigma_low_history_boost: float = Field(
        default=0.0, alias="OPTIMIZER_CEILING_SIGMA_LOW_HISTORY_BOOST"
    )

    def picks_paused_on(self, day: dt.date) -> bool:
        """Whether the picking pipeline should no-op on `day`."""
        if not self.picks_pause_start or not self.picks_pause_end:
            return False
        try:
            start = dt.date.fromisoformat(self.picks_pause_start)
            end = dt.date.fromisoformat(self.picks_pause_end)
        except ValueError:
            return False
        return start <= day <= end

    def picks_resume_date(self) -> str | None:
        """The first day picks are expected to resume, or None if not paused."""
        if not self.picks_pause_end:
            return None
        try:
            end = dt.date.fromisoformat(self.picks_pause_end)
        except ValueError:
            return None
        return (end + dt.timedelta(days=1)).isoformat()

    def config_drift(self) -> list[tuple[str, object, object]]:
        """Knobs whose ACTIVE value differs from the validated production
        config (D102). Many code defaults are deliberately safe-off so the
        library is conservative when used bare; production turns them on via
        env. If the cron env is ever wiped/reset, every knob silently reverts
        to that safe-off default and the validated behavior is lost with no
        other signal. This returns (name, actual, expected) for each deviation
        so the watchdog can WARN -- code stays the library default, but drift
        from prod is no longer silent. Update EXPECTED_PROD_CONFIG when a knob
        is intentionally retuned in production.
        """
        out: list[tuple[str, object, object]] = []
        for name, expected in EXPECTED_PROD_CONFIG.items():
            actual = getattr(self, name)
            if isinstance(expected, float):
                if abs(float(actual) - expected) > 1e-9:
                    out.append((name, actual, expected))
            elif actual != expected:
                out.append((name, actual, expected))
        return out


# The validated production config (mirrors the STATUS.md env table, D70-D98).
# This is the source of truth for "what cron-job2's env should be"; the
# watchdog warns when the live settings drift from it (e.g. after an env reset).
EXPECTED_PROD_CONFIG: dict[str, object] = {
    "game_script_minutes_enabled": True,  # D57
    "availability_model_enabled": True,  # D73
    "late_refreeze_enabled": True,  # D75
    "lineup_anchor_floor": 2,  # D57/D58
    "prop_signal_scale": 0.3,  # D78
    "optimizer_boost_sum_cap": 9.0,  # D70/R2
    "optimizer_game_stack_bonus": 0.010,  # D70/R3, raised D98
    "optimizer_contextual_stacking_enabled": True,  # contextual-stacking-v1
    "optimizer_contextual_stack_ev_margin": 0.01,  # objective indifference band
    "field_same_game_boost": 3.0,  # D88/D91
    "field_same_team_boost": 2.0,  # D88/D91
    "ceiling_sigma_blowout_boost": 0.15,  # D89/D92
    "ceiling_sigma_low_history_boost": 0.20,  # D89/D92
    "optimizer_ceiling_tilt_slots": True,  # D107/Phase 4, validated with two years data
    "optimizer_mixture_variance_enabled": True,  # D107/Tier 2, Bernoulli availability gating
    "starter_unknown_fade": 0.75,  # 2026-07-04, calibrate_starter_and_boost.py
    # CAVEAT (2026-08-19): every loss_ledger delta quoted below (-93, +75,
    # +12.5, the -47.7 tilt cliff) was measured while score_lineup re-sorted
    # picks by realized value, which inflated swap gains. loss_ledger now scores
    # the committed slot order. Re-derive any of these with scripts/lab.py
    # before treating them as current; the signs may hold, the magnitudes will
    # not.
    # 2026-07-04 late: rolled back after loss_ledger --counterfactual showed a
    # -93 aggregate delta under live guardrails. Kept as a shadow overlay for
    # ex-post measurement. The 1.5x lift over-weighted DNP-prone role players
    # because the head under-predicts every boost tier, not just the tail.
    "picker_boost_tail_lift": False,
    # 2026-07-04 late: sweep_max_boost.py showed cap 3.0 aggregates +75 across
    # 23 slates over cap 2.5. Winners routinely use boost-3.0 lottery cards
    # (Madina Okot, Zia Cooke on 2026-06-22); OPTIMIZER_MAX_SINGLE_BOOST=2.5
    # excluded them entirely.
    "optimizer_max_single_boost": 3.0,
    # 2026-07-10 suite (loss_ledger --counterfactual suite, 23 slates): the
    # minutes-conditional starter lift fixes the recurring top-miss class
    # (Kuier 07-05/07-07, Harris 07-09; expected starters at 16-25 recent
    # minutes realize up to 2x the live center), and the 0.2 floor tilt
    # fades wide-interval ceiling plays out of the non-spike slots. Combined
    # +12.5 vs the fade-only incumbent with 14 up / 9 down. Tilt weight has
    # a cliff at 0.35 (-47.7, see scripts/loss_ledger.py) -- do not raise it
    # without re-running the sweep.
    "starter_minutes_lift_enabled": True,
    "picker_floor_tilt_weight": 0.2,
}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


_PRODUCTION_ROLE_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "api": ("DATABASE_URL",),
    "job1": ("DATABASE_URL", "REALSPORTS_STORAGE_STATE_B64GZ"),
    "job1games": ("DATABASE_URL", "REALSPORTS_STORAGE_STATE_B64GZ"),
    "job1late": ("DATABASE_URL",),
    "job2": ("DATABASE_URL", "REDIS_URL", "WNBA_ORACLE_MODEL_ARTIFACT_SHA"),
    "dayclose": ("DATABASE_URL", "REALSPORTS_STORAGE_STATE_B64GZ"),
    "backfill": ("DATABASE_URL",),
}


def validate_production_role(settings: Settings, role: str) -> None:
    """Validate only the resources a known production role cannot run without.

    This function is deliberately not called while importing settings. An
    application entry point may call it immediately before starting a specific
    production role, while development and test construction stay lightweight.
    Errors contain variable names only and never reveal configured values.
    """
    if settings.env != "prod":
        return
    try:
        required = _PRODUCTION_ROLE_REQUIREMENTS[role]
    except KeyError as exc:
        raise ValueError(f"Unknown WNBA production role: {role}") from exc

    configured: dict[str, str] = {
        "DATABASE_URL": settings.database_url,
        "REDIS_URL": settings.redis_url,
        "WNBA_ORACLE_MODEL_ARTIFACT_SHA": settings.model_artifact_sha,
        "REALSPORTS_STORAGE_STATE_B64GZ": (
            settings.realsports_storage_state_b64gz.get_secret_value()
        ),
    }
    missing = [name for name in required if not configured[name].strip()]
    if missing:
        raise MissingRequiredEnvironmentError(missing)

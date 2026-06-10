"""Pydantic-settings driven config. Single source of truth for env vars."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All env-driven config. Treats missing required values as a startup error."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # Identity / mode. Aliases are required because case_sensitive=True;
    # without the alias pydantic-settings only matches `env` / `log_level`
    # not `ENV` / `LOG_LEVEL` (the convention every container env follows).
    env: Literal["dev", "prod"] = Field(default="dev", alias="ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # External APIs
    odds_api_key: str = Field(default="", alias="ODDS_API_KEY")
    real_sports_username: str = Field(default="", alias="REAL_SPORTS_USERNAME")
    real_sports_password: str = Field(default="", alias="REAL_SPORTS_PASSWORD")

    # Storage
    database_url: str = Field(default="", alias="DATABASE_URL")
    redis_url: str = Field(default="", alias="REDIS_URL")

    # Operational toggles. Same alias-or-no-injection rule as above.
    job1_dry_run: bool = Field(default=False, alias="JOB1_DRY_RUN")
    job2_dry_run: bool = Field(default=False, alias="JOB2_DRY_RUN")
    model_artifact_sha: str = Field(default="", alias="WNBA_ORACLE_MODEL_ARTIFACT_SHA")

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
    # D70 (R2): cap the sum-of-card-boost across the 5 picked players.
    # Winners' anatomy (research/internal/01_winners_anatomy.md): median rank-1
    # total boost is 7.5; the 75th percentile is ~10. Our recent freezes hit
    # 12-15. The 2026-06-04 ~6000th finish was driven by five high-boost
    # cards with no minutes history. 0.0 disables (default off so the
    # rollout is reversible via env); set OPTIMIZER_BOOST_SUM_CAP=9.0 to
    # arm. The optimizer relaxes the cap (with a warning) if no lineup is
    # jointly feasible with the team cap.
    optimizer_boost_sum_cap: float = Field(default=0.0, alias="OPTIMIZER_BOOST_SUM_CAP")
    # D70 (R2): cap the single-pick card_boost. Boost economics
    # (research/internal/04_boost_economics.md) found the 3.0 bucket has
    # an 8.2% hit rate and Sharpe 1.21 vs the (2.0, 2.5] bucket at 50.4%
    # / 2.01 -- a value trap unless used sparingly. 0.0 disables (default
    # off); set OPTIMIZER_MAX_SINGLE_BOOST=2.5 to refuse the 2.5-3.0 lottery
    # tier entirely, or 2.75 to allow it but block the 3.0 wall. Relaxed
    # alongside the sum cap when jointly infeasible.
    optimizer_max_single_boost: float = Field(default=0.0, alias="OPTIMIZER_MAX_SINGLE_BOOST")
    # D70 (R3): game-stack bonus added to expected_payout per "stack pair"
    # in the combo. A stack pair is two picks in the same game (matched by
    # the unordered {team, opponent} pair). Per research/internal/01_winners_anatomy.md,
    # 87% of top-20 lineups have at least one 2+ same-game pick group; our
    # optimizer treats outcomes as independent today. Default 0.0 (off);
    # set OPTIMIZER_GAME_STACK_BONUS=0.005 to mildly prefer stacked lineups
    # at equal EV (a 2-stack adds 0.005 to ev, a 3-stack adds 0.010). The
    # cap relax/EV log paths from R2 are unaffected.
    optimizer_game_stack_bonus: float = Field(default=0.0, alias="OPTIMIZER_GAME_STACK_BONUS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

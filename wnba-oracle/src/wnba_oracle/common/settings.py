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
    optimizer_n_samples: int = Field(default=1000, alias="OPTIMIZER_N_SAMPLES")
    optimizer_top_n_filter: int = Field(default=20, alias="OPTIMIZER_TOP_N_FILTER")
    optimizer_n_field_lineups: int = Field(default=120, alias="OPTIMIZER_N_FIELD_LINEUPS")
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
    optimizer_dynamic_team_cap: bool = Field(
        default=True, alias="OPTIMIZER_DYNAMIC_TEAM_CAP"
    )
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
    starter_signal_enabled: bool = Field(
        default=True, alias="STARTER_SIGNAL_ENABLED"
    )
    # minutes_model_enabled: use the D55 minutes x rate blended predictor for
    # players job1 matched to nba_api game logs. The one signal orthogonal to
    # card_boost (corr 0.554 vs boost 0.246 walk-forward). Default on; set
    # MINUTES_MODEL_ENABLED=false to fall back to the EB/heuristic predictor
    # for every player (rolls back via env, no redeploy).
    minutes_model_enabled: bool = Field(
        default=True, alias="MINUTES_MODEL_ENABLED"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

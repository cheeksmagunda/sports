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
    optimizer_n_samples: int = Field(default=5000, alias="OPTIMIZER_N_SAMPLES")
    optimizer_top_n_filter: int = Field(default=30, alias="OPTIMIZER_TOP_N_FILTER")
    # max_per_team: caps how many players from one team can appear in a
    # lineup. 2 is the basketball-main default; 5 disables the cap.
    optimizer_max_per_team: int = Field(default=2, alias="OPTIMIZER_MAX_PER_TEAM")
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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

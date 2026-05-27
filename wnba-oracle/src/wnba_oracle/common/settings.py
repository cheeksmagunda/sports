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

    # Identity / mode
    env: Literal["dev", "prod"] = Field(default="dev")
    log_level: str = Field(default="INFO")

    # External APIs
    odds_api_key: str = Field(default="", alias="ODDS_API_KEY")
    real_sports_username: str = Field(default="", alias="REAL_SPORTS_USERNAME")
    real_sports_password: str = Field(default="", alias="REAL_SPORTS_PASSWORD")

    # Storage
    database_url: str = Field(default="", alias="DATABASE_URL")
    redis_url: str = Field(default="", alias="REDIS_URL")

    # Operational toggles
    job1_dry_run: bool = Field(default=False)
    job2_dry_run: bool = Field(default=False)
    model_artifact_sha: str = Field(default="", alias="WNBA_ORACLE_MODEL_ARTIFACT_SHA")

    # Lineup optimizer config
    payout_regime: Literal["top_50", "top_20", "top_1"] = Field(default="top_20")
    optimizer_n_samples: int = Field(default=5000)
    optimizer_top_n_filter: int = Field(default=30)
    # max_per_team: caps how many players from one team can appear in a
    # lineup. 2 is the basketball-main default; 5 disables the cap.
    optimizer_max_per_team: int = Field(default=2)
    # contrarian_strength: 0.0 disables the anti-popularity penalty; 0.2 is
    # basketball-main's default. Tune up to 0.3 for stronger contrarian tilt
    # in top-1 regime, down to 0.1 for cash games.
    contrarian_strength: float = Field(default=0.2)
    contrarian_enabled: bool = Field(default=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

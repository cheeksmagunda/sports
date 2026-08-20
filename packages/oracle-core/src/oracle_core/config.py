"""Runtime settings shared by applications without loading an env file."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

SecretValue = SecretStr


class MissingRequiredEnvironmentError(RuntimeError):
    """Raised when one or more required environment names are empty or absent."""

    def __init__(self, names: Iterable[str]) -> None:
        self.names = tuple(sorted(set(names)))
        super().__init__(f"Missing required environment variables: {', '.join(self.names)}")


class RuntimeConfig(BaseSettings):
    """Minimal environment-backed runtime configuration.

    Applications compose this class with their own settings. ``env_file=None``
    is intentional: callers receive values from the process environment or
    explicit constructor arguments only.
    """

    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        case_sensitive=True,
    )

    env: Literal["dev", "prod"] = Field(default="dev", alias="ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_url: str = Field(default="", alias="DATABASE_URL")
    redis_url: str = Field(default="", alias="REDIS_URL")


@lru_cache(maxsize=1)
def get_runtime_config() -> RuntimeConfig:
    """Return a cached process-environment snapshot of :class:`RuntimeConfig`."""

    return RuntimeConfig()


def clear_runtime_config_cache() -> None:
    """Clear the process-environment snapshot, primarily for tests."""

    get_runtime_config.cache_clear()


def validate_required_env(
    names: Iterable[str],
    *,
    environ: Mapping[str, str] | None = None,
) -> None:
    """Validate required environment names without reading their values back.

    The exception reports names only, never secret values. Whitespace-only
    values are considered missing so callers do not accidentally accept an
    unusable credential or endpoint.
    """

    source = os.environ if environ is None else environ
    missing = [name for name in names if not str(source.get(name, "")).strip()]
    if missing:
        raise MissingRequiredEnvironmentError(missing)

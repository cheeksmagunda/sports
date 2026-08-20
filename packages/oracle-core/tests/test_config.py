from __future__ import annotations

from pathlib import Path

import pytest
from oracle_core.config import (
    MissingRequiredEnvironmentError,
    RuntimeConfig,
    SecretValue,
    get_runtime_config,
    validate_required_env,
)


def test_runtime_config_uses_uppercase_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example")
    get_runtime_config.cache_clear()

    config = get_runtime_config()

    assert config.env == "prod"
    assert config.log_level == "DEBUG"
    assert config.database_url == "postgresql://example"


def test_runtime_config_does_not_load_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("ENV=prod\nLOG_LEVEL=DEBUG\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    config = RuntimeConfig()

    assert config.env == "dev"
    assert config.log_level == "INFO"


def test_runtime_config_rejects_unknown_environment() -> None:
    with pytest.raises(ValueError):
        RuntimeConfig(ENV="staging")  # type: ignore[arg-type]


def test_secret_value_never_exposes_value_in_string_forms() -> None:
    secret = SecretValue("not-for-logs")

    assert "not-for-logs" not in str(secret)
    assert "not-for-logs" not in repr(secret)
    assert secret.get_secret_value() == "not-for-logs"


def test_validate_required_env_reports_names_not_values() -> None:
    with pytest.raises(MissingRequiredEnvironmentError) as exc_info:
        validate_required_env(["PRESENT", "MISSING"], environ={"PRESENT": "ok"})

    assert exc_info.value.names == ("MISSING",)
    assert "ok" not in str(exc_info.value)


def test_validate_required_env_accepts_nonempty_values() -> None:
    validate_required_env(["ONE", "TWO"], environ={"ONE": "a", "TWO": "b"})

"""Pytest fixtures shared across the suite."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture(autouse=True)
def _stable_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin env vars unit tests rely on. Keeps tests hermetic from operator env."""
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    # Settings cache - reset between tests so monkeypatched vars take effect.
    from wnba_oracle.common.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def chdir_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


# Ensure pytest can import via package layout.
os.environ.setdefault("PYTHONPATH", str(Path(__file__).resolve().parent.parent / "src"))

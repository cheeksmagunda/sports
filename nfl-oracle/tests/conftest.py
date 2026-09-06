"""Shared pytest fixtures for nfl-oracle."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_stats() -> dict:
    return json.loads((FIXTURES / "stats_126323.json").read_text(encoding="utf-8"))


@pytest.fixture
def sample_players() -> dict:
    return json.loads((FIXTURES / "players_126323.json").read_text(encoding="utf-8"))


@pytest.fixture
def sample_feed() -> dict:
    return json.loads((FIXTURES / "feed_126323.json").read_text(encoding="utf-8"))

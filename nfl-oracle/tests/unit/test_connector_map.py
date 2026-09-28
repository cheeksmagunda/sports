"""The NFL connector map stays aligned with the serving feature contract (#604)."""

from __future__ import annotations

import re
from pathlib import Path

from nfl_oracle.baselines.value_model import MODEL_FEATURE_NAMES
from nfl_oracle.features.live import REQUIRED_LIVE_OK_CONTEXT_FEATURES

_MAP = Path(__file__).resolve().parents[2] / "CONNECTORS.md"

_STAY_OFF = (
    "base_boosted_value",
    "draft_stats_score",
    "draft_stats_rank",
    "did_not_play",
    "started",
    "minutes",
    "card_boost_post_settlement",
    "same_slate_final_value",
    "same_slate_ownership",
    "mostDrafted",
)

_ENV_ON = (
    "NFL_RECOMMENDATIONS_ENABLED",
    "NFL_OPTIMIZER_PROFILE",
    "NFL_PICKER_BOOST_RANK_BLEND",
    "NFL_PICKER_PROFILE",
    "NFL_DATABASE_URL",
    "REALSPORTS_STORAGE_STATE_B64GZ",
    "NFL_DEVICE_UUID",
    "NFL_DEVICE_NAME",
)


def _text() -> str:
    return _MAP.read_text(encoding="utf-8")


def _has_token(text: str, name: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", text) is not None


def test_map_exists_and_has_no_em_dash() -> None:
    text = _text()
    assert text.startswith("# NFL T-40 connector map")
    assert "\u2014" not in text


def test_map_lists_every_force_included_feature() -> None:
    text = _text()
    missing = [name for name in REQUIRED_LIVE_OK_CONTEXT_FEATURES if not _has_token(text, name)]
    assert missing == []
    missing_core = [name for name in MODEL_FEATURE_NAMES if not _has_token(text, name)]
    assert missing_core == []


def test_map_keeps_chalk_and_leakage_off_and_names_the_freeze_env() -> None:
    text = _text()
    assert "highestBoostedValuePlayers" in text
    assert "max_value" in text
    assert "total_value" in text
    for name in _STAY_OFF:
        assert _has_token(text, name), name
    for name in _ENV_ON:
        assert _has_token(text, name), name
    assert "SPORTS_OLLAMA_UNLOCK" in text
    assert "contest entry" in text.lower() or "Contest entry" in text

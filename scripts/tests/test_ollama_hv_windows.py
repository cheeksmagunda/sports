"""Offline tests for Ollama HV watcher window math and gate (#574)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from ollama_hv_watcher.gate import (
    UNLOCK_ENV,
    ensure_ollama_training_allowed,
    operator_unlock_enabled,
    training_allowed,
)
from ollama_hv_watcher.windows import (
    DayWatchPlan,
    SlateWindow,
    build_portfolio_window,
    load_windows_payload,
    portfolio_window,
)
from realsports_corpus.coverage_manifest import (
    OllamaForbiddenError,
    build_empty_manifest,
    record_family_status,
)
from realsports_corpus.layout import REQUIRED_VARIABLE_FAMILIES


def test_portfolio_arms_at_earliest_t40_and_closes_at_latest() -> None:
    t0 = datetime(2000, 1, 3, 18, 0, tzinfo=UTC)
    a = SlateWindow("wnba", "w1", t0, t0 + timedelta(hours=2))
    b = SlateWindow("nfl", "n1", t0 + timedelta(hours=1), t0 + timedelta(hours=5))
    window = build_portfolio_window([a, b])
    assert window is not None
    assert window.arm_at == a.t40_at
    assert window.close_at == b.close_at
    assert window.is_active(a.t40_at)
    assert window.is_active(b.close_at)
    assert not window.is_active(a.t40_at - timedelta(seconds=1))
    assert not window.is_active(b.close_at + timedelta(seconds=1))


def test_empty_portfolio_is_none() -> None:
    assert build_portfolio_window([]) is None
    assert portfolio_window([]) is None


def test_slate_requires_aware_datetimes() -> None:
    naive = datetime(2000, 1, 3, 18, 0)  # noqa: DTZ001 - intentional naive
    with pytest.raises(ValueError):
        SlateWindow("nba", "x", naive, naive + timedelta(hours=1))


def test_duplicate_session_id_rejected() -> None:
    t0 = datetime(2000, 1, 3, 18, 0, tzinfo=UTC)
    a = SlateWindow("wnba", "dup", t0, t0 + timedelta(hours=2))
    b = SlateWindow("wnba", "dup", t0 + timedelta(minutes=30), t0 + timedelta(hours=3))
    with pytest.raises(ValueError, match="duplicate_session_id"):
        DayWatchPlan(slates=(a, b))


def test_load_windows_payload() -> None:
    payload = {
        "slates": [
            {
                "sport": "nba",
                "slate_id": "2026-10-01",
                "freeze_or_kickoff_at": "2026-10-01T23:00:00Z",
                "close_at": "2026-10-02T06:00:00Z",
            }
        ]
    }
    plan = load_windows_payload(payload)
    assert plan.slates[0].sport == "nba"


def test_gate_forbidden_without_unlock() -> None:
    manifest = build_empty_manifest()
    assert training_allowed(manifest, environ={}) is False
    assert operator_unlock_enabled({UNLOCK_ENV: "0"}) is False
    with pytest.raises(OllamaForbiddenError, match="FORBIDDEN"):
        ensure_ollama_training_allowed(manifest, environ={})


def test_gate_operator_unlock() -> None:
    reason = ensure_ollama_training_allowed(
        build_empty_manifest(), environ={UNLOCK_ENV: "1"}
    )
    assert reason == "operator_unlock"


def test_gate_coverage_complete() -> None:
    manifest = build_empty_manifest()
    for sport in ("wnba", "nfl", "nba", "nhl"):
        for family in REQUIRED_VARIABLE_FAMILIES:
            manifest = record_family_status(
                manifest,
                sport=sport,  # type: ignore[arg-type]
                family=family,
                status="present",
                artifact_count=1,
            )
    assert ensure_ollama_training_allowed(manifest, environ={}) == "coverage_complete"

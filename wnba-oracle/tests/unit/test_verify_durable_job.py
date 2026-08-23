"""Tests for bounded durable job verification."""

from __future__ import annotations

import importlib.util
import pathlib
import sys

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts"


def _load_verifier():
    common_spec = importlib.util.spec_from_file_location(
        "ops_common", SCRIPTS_DIR / "ops_common.py"
    )
    assert common_spec is not None
    assert common_spec.loader is not None
    common = importlib.util.module_from_spec(common_spec)
    sys.modules[common_spec.name] = common
    common_spec.loader.exec_module(common)

    verifier_spec = importlib.util.spec_from_file_location(
        "verify_durable_job", SCRIPTS_DIR / "verify_durable_job.py"
    )
    assert verifier_spec is not None
    assert verifier_spec.loader is not None
    verifier = importlib.util.module_from_spec(verifier_spec)
    sys.modules[verifier_spec.name] = verifier
    verifier_spec.loader.exec_module(verifier)
    return verifier


def _payload(*, status: str = "success", started_at: str = "2026-08-22T20:01:00Z"):
    return {
        "jobs": {
            "backfill": {
                "role": "backfill",
                "status": status,
                "exit_code": 0 if status == "success" else 1,
                "started_at": started_at,
                "completed_at": "2026-08-22T20:05:00Z",
            }
        }
    }


def test_matching_success_requires_a_new_successful_completion() -> None:
    verifier = _load_verifier()

    assert (
        verifier.classify_outcome(
            _payload(),
            role="backfill",
            started_after="2026-08-22T20:00:00Z",
        )
        == "success"
    )
    assert (
        verifier.classify_outcome(
            _payload(started_at="2026-08-22T19:59:59Z"),
            role="backfill",
            started_after="2026-08-22T20:00:00Z",
        )
        == "pending"
    )
    assert (
        verifier.classify_outcome(
            _payload(status="failed"),
            role="backfill",
            started_after="2026-08-22T20:00:00Z",
        )
        == "failed"
    )


def test_wait_is_bounded_and_accepts_later_success(monkeypatch) -> None:
    verifier = _load_verifier()
    responses = iter(
        [
            (200, _payload(status="failed", started_at="2026-08-22T19:59:59Z")),
            (200, _payload()),
        ]
    )
    times = iter([0.0, 0.0, 1.0])
    sleeps: list[float] = []
    monkeypatch.setattr(verifier, "get_json", lambda _url: next(responses))

    assert (
        verifier.wait_for_outcome(
            "https://api.example",
            role="backfill",
            started_after="2026-08-22T20:00:00Z",
            timeout_seconds=10,
            interval_seconds=1,
            monotonic=lambda: next(times),
            sleep=sleeps.append,
        )
        == "success"
    )
    assert sleeps == [1]


def test_wait_stops_on_new_terminal_failure(monkeypatch) -> None:
    verifier = _load_verifier()
    sleeps: list[float] = []
    monkeypatch.setattr(verifier, "get_json", lambda _url: (200, _payload(status="failed")))

    assert (
        verifier.wait_for_outcome(
            "https://api.example",
            role="backfill",
            started_after="2026-08-22T20:00:00Z",
            timeout_seconds=600,
            interval_seconds=10,
            monotonic=lambda: 0.0,
            sleep=sleeps.append,
        )
        == "failed"
    )
    assert sleeps == []

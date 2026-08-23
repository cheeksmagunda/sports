"""Durable, credential-free evidence for scheduled day-close verification."""

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
        "dayclose_verify", SCRIPTS_DIR / "dayclose_verify.py"
    )
    assert verifier_spec is not None
    assert verifier_spec.loader is not None
    verifier = importlib.util.module_from_spec(verifier_spec)
    sys.modules[verifier_spec.name] = verifier
    verifier_spec.loader.exec_module(verifier)
    return common, verifier


def _window(common):
    return common.RunWindow.from_strings(
        role="dayclose",
        slate_date="2026-08-22",
        started_at="2026-08-23T05:45:00Z",
        ended_at="2026-08-23T07:00:00Z",
    )


def _payload(*, status: str = "success", exit_code: int = 0):
    substeps = {
        "contest_discovery": {"status": "success"},
        "historical_backfill": {"status": "success"},
        "label_coverage": {"status": "success"},
        "placement_capture": {"status": "success"},
        "game_log_refresh": {"status": "success"},
        "shadow_results": {"status": "success"},
    }
    return {
        "jobs": {
            "dayclose": {
                "role": "dayclose",
                "status": status,
                "exit_code": exit_code,
                "started_at": "2026-08-23T06:00:00Z",
                "completed_at": "2026-08-23T06:10:00Z",
                "details": {
                    "processed_slate_date": "2026-08-22",
                    "substeps": substeps,
                },
            }
        }
    }


def test_success_requires_complete_durable_substeps(monkeypatch) -> None:
    common, verifier = _load_verifier()
    monkeypatch.setattr(verifier, "get_json", lambda _url: (200, _payload()))

    checks = verifier._durable_dayclose_checks("https://api.example", _window(common))

    assert len(checks) == 1
    assert checks[0].status == "ok"


def test_degraded_outcome_is_visible_without_becoming_false_success(monkeypatch) -> None:
    common, verifier = _load_verifier()
    payload = _payload(status="degraded", exit_code=2)
    payload["jobs"]["dayclose"]["details"]["degraded_substeps"] = ["shadow_results"]
    payload["jobs"]["dayclose"]["details"]["substeps"]["shadow_results"] = {"status": "degraded"}
    monkeypatch.setattr(verifier, "get_json", lambda _url: (200, payload))

    checks = verifier._durable_dayclose_checks("https://api.example", _window(common))

    assert len(checks) == 1
    assert checks[0].status == "warn"
    assert "shadow_results" in checks[0].summary


def test_missing_required_substep_fails_closed(monkeypatch) -> None:
    common, verifier = _load_verifier()
    payload = _payload()
    del payload["jobs"]["dayclose"]["details"]["substeps"]["placement_capture"]
    monkeypatch.setattr(verifier, "get_json", lambda _url: (200, payload))

    checks = verifier._durable_dayclose_checks("https://api.example", _window(common))

    assert len(checks) == 1
    assert checks[0].status == "alert"
    assert "placement_capture" in checks[0].summary


def test_terminal_failure_is_reported_immediately(monkeypatch) -> None:
    common, verifier = _load_verifier()
    monkeypatch.setattr(
        verifier,
        "get_json",
        lambda _url: (200, _payload(status="failed", exit_code=1)),
    )

    checks = verifier._durable_dayclose_checks("https://api.example", _window(common))

    assert len(checks) == 1
    assert checks[0].status == "alert"
    assert "failed" in checks[0].summary


def test_mismatched_processed_slate_fails_closed(monkeypatch) -> None:
    common, verifier = _load_verifier()
    payload = _payload()
    payload["jobs"]["dayclose"]["details"]["processed_slate_date"] = "2026-08-21"
    monkeypatch.setattr(verifier, "get_json", lambda _url: (200, payload))

    checks = verifier._durable_dayclose_checks("https://api.example", _window(common))

    assert len(checks) == 1
    assert checks[0].status == "alert"
    assert "processed slate" in checks[0].summary


def test_success_cannot_hide_a_degraded_required_substep(monkeypatch) -> None:
    common, verifier = _load_verifier()
    payload = _payload()
    payload["jobs"]["dayclose"]["details"]["substeps"]["label_coverage"] = {"status": "degraded"}
    monkeypatch.setattr(verifier, "get_json", lambda _url: (200, payload))

    checks = verifier._durable_dayclose_checks("https://api.example", _window(common))

    assert len(checks) == 1
    assert checks[0].status == "alert"
    assert "conflicts" in checks[0].summary

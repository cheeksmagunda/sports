"""Discover open/upcoming slate windows for the HV watcher (#574).

Sport applications own live calendars. Default path is LIVE ONLY: explicit
``--windows-json`` or ``SPORTS_OLLAMA_WINDOWS_JSON``. Fixture calendars are
opt-in for offline tests via ``include_fixtures=True`` / ``--allow-fixtures``.
Never invent placeholder kickoff/close times. No sport-app imports.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ollama_hv_watcher.live import LiveDataRequiredError
from ollama_hv_watcher.windows import (
    DayWatchPlan,
    SlateWindow,
    build_day_plan,
    load_windows_payload,
)

WINDOWS_ENV = "SPORTS_OLLAMA_WINDOWS_JSON"
PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_FIXTURE_CALENDARS = PACKAGE_DIR / "fixtures" / "calendars"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_windows_file(path: Path) -> DayWatchPlan:
    payload = _load_json(Path(path))
    if not isinstance(payload, (dict, list)):
        raise TypeError(f"windows_json_invalid_root:{path}")
    return load_windows_payload(payload)


# Alias used by __main__ / older call sites
load_windows_json = load_windows_file


def load_fixture_calendars(root: Path | None = None) -> DayWatchPlan | None:
    """Merge ``*.json`` calendar stubs under fixtures/calendars if present.

    Offline tests only. Production watchers must not call this unless the
    operator explicitly passed ``--allow-fixtures``.
    """

    calendars = Path(root) if root is not None else DEFAULT_FIXTURE_CALENDARS
    if not calendars.is_dir():
        return None
    windows: list[SlateWindow] = []
    for path in sorted(calendars.glob("*.json")):
        payload = _load_json(path)
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict) and isinstance(payload.get("slates"), list):
            rows = payload["slates"]
        else:
            raise LiveDataRequiredError(
                "slates",
                context=f"fixture_calendar={path}",
            )
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise LiveDataRequiredError(
                    f"slates[{index}]",
                    context=f"fixture_calendar={path}",
                )
            windows.append(SlateWindow.from_dict(row))
    if not windows:
        return None
    return build_day_plan(windows)


def fixture_example_payload() -> dict[str, Any]:
    """Offline example for docs only; NEVER treat as live calendar data."""

    plan = load_fixture_calendars()
    if plan is not None:
        return {
            "slates": [s.to_dict() for s in plan.slates],
            "WARNING": "fixture_only_not_live",
        }
    raise LiveDataRequiredError("fixture_calendars", context="docs_example")


def discover_day_plan(
    *,
    windows_json: Path | None = None,
    include_fixtures: bool = False,
    environ: dict[str, str] | None = None,
) -> DayWatchPlan:
    """Resolve a LIVE day plan from explicit JSON or env path.

    Precedence: ``windows_json`` argument, then ``SPORTS_OLLAMA_WINDOWS_JSON``.
    Fixture calendars only when ``include_fixtures=True`` (tests / explicit
    ``--allow-fixtures``). Raises ``LiveDataRequiredError`` when nothing
    live resolves - never invents placeholder kickoffs.
    """

    env = environ if environ is not None else os.environ
    candidates: list[Path] = []
    if windows_json is not None:
        candidates.append(Path(windows_json))
    env_path = str(env.get(WINDOWS_ENV, "")).strip()
    if env_path:
        candidates.append(Path(env_path))

    missing_candidates: list[str] = []
    for path in candidates:
        if path.is_file():
            return load_windows_file(path)
        missing_candidates.append(str(path))

    if include_fixtures:
        plan = load_fixture_calendars()
        if plan is not None:
            return plan

    searched = ", ".join(str(p) for p in candidates) or "(none)"
    raise LiveDataRequiredError(
        "slate_windows",
        context=(
            f"provide --windows-json or set {WINDOWS_ENV} with LIVE freeze/"
            f"kickoff+close per sport; fixtures off by default "
            f"(searched={searched}; missing={missing_candidates})"
        ),
    )

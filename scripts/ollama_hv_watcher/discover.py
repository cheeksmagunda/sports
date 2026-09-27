"""Discover open/upcoming slate windows for the HV watcher (#574).

Sport applications own live calendars. This module stays import-safe: it
loads an explicit windows JSON (operator/CI/fixture) and optionally merges
static calendar stubs under ``fixtures/calendars/``. No sport-app imports.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ollama_hv_watcher.windows import DayWatchPlan, SlateWindow, build_day_plan, load_windows_payload

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
    """Merge ``*.json`` calendar stubs under fixtures/calendars if present."""

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
            continue
        for row in rows:
            if isinstance(row, dict):
                windows.append(SlateWindow.from_dict(row))
    if not windows:
        return None
    return build_day_plan(windows)


def fixture_example_payload() -> dict[str, Any]:
    """Offline example used by docs/CLI ``--example``; not live calendar data."""

    plan = load_fixture_calendars()
    if plan is not None:
        return {"slates": [s.to_dict() for s in plan.slates]}
    return {
        "slates": [
            {
                "sport": "nfl",
                "slate_id": "2026-09-27-main",
                "freeze_or_kickoff_at": "2026-09-27T17:00:00Z",
                "close_at": "2026-09-28T04:00:00Z",
                "lead_minutes": 40,
            }
        ]
    }


def discover_day_plan(
    *,
    windows_json: Path | None = None,
    include_fixtures: bool = True,
    environ: dict[str, str] | None = None,
) -> DayWatchPlan:
    """Resolve a day plan from explicit JSON, env path, and/or fixtures.

    Precedence: ``windows_json`` argument, then ``SPORTS_OLLAMA_WINDOWS_JSON``,
    then fixture calendars. Raises ``FileNotFoundError`` when nothing resolves.
    """

    env = environ if environ is not None else os.environ
    candidates: list[Path] = []
    if windows_json is not None:
        candidates.append(Path(windows_json))
    env_path = str(env.get(WINDOWS_ENV, "")).strip()
    if env_path:
        candidates.append(Path(env_path))

    for path in candidates:
        if path.is_file():
            return load_windows_file(path)

    if include_fixtures:
        plan = load_fixture_calendars()
        if plan is not None:
            return plan

    searched = ", ".join(str(p) for p in candidates) or "(none)"
    raise FileNotFoundError(
        "no_slate_windows_found: provide --windows-json or set "
        f"{WINDOWS_ENV} (searched={searched})"
    )

"""CLI for the Ollama HV/TDV slate helper (#574).

Modes (mutually exclusive)::

    PYTHONPATH=scripts python -m ollama_hv_watcher --status
    PYTHONPATH=scripts python -m ollama_hv_watcher --once
    PYTHONPATH=scripts python -m ollama_hv_watcher --windows-from-apps \\
        --day YYYY-MM-DD --sports nfl,wnba
    PYTHONPATH=scripts python -m ollama_hv_watcher --daemon \\
        --day YYYY-MM-DD --sports nfl,wnba

``--daemon`` polls each sport app for every armed slate and writes one
advisory tick per app freeze whose five equals the app's five. The helper
only reads the apps; it never changes, blocks, or delays their freeze.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from realsports_corpus.coverage_manifest import (
    OllamaForbiddenError,
    ollama_helper_allowed,
)

from ollama_hv_watcher.adapters import app_api
from ollama_hv_watcher.app_daemon import AppDaemonConfig, run_app_daemon
from ollama_hv_watcher.boards import (
    armed_board_paths,
    load_history_board_summary,
    load_pregame_board_summary,
)
from ollama_hv_watcher.client import DEFAULT_MODEL
from ollama_hv_watcher.discover import discover_day_plan
from ollama_hv_watcher.gate import (
    UNLOCK_ENV,
    load_manifest_or_empty,
    operator_unlock_enabled,
)
from ollama_hv_watcher.learn import atomic_write_json, run_learn
from ollama_hv_watcher.live import LiveDataRequiredError
from ollama_hv_watcher.pick import FIVE_PLAYER_LINEUP_SIZE
from ollama_hv_watcher.serve import (
    DEFAULT_HOST,
    DEFAULT_PIDFILE,
    ensure_ollama_serve,
    health_check,
)
from ollama_hv_watcher.windows import load_windows_payload

DEFAULT_DATA_ROOT = Path("data/ollama_hv")
# Slate days follow the US Eastern calendar the sport apps use.
SLATE_DAY_TZ = ZoneInfo("America/New_York")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def default_day() -> str:
    return datetime.now(SLATE_DAY_TZ).date().isoformat()


def _sports(raw: str | None) -> list[str]:
    return [s.strip().lower() for s in str(raw or "").split(",") if s.strip()]


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def cmd_status(args: argparse.Namespace) -> int:
    health = health_check(args.host)
    manifest = load_manifest_or_empty(Path(args.manifest) if args.manifest else None)
    plan_error: str | None = None
    plan_payload: dict[str, object] | None = None
    try:
        plan = discover_day_plan(
            windows_json=Path(args.windows_json) if args.windows_json else None,
            include_fixtures=bool(getattr(args, "allow_fixtures", False)),
        )
        plan_payload = plan.to_dict()
    except LiveDataRequiredError as exc:
        plan_error = str(exc)
    _print_json(
        {
            "health": health,
            "unlock_env": UNLOCK_ENV,
            "operator_unlock": operator_unlock_enabled(),
            "coverage_complete": ollama_helper_allowed(manifest),
            "training_allowed": ollama_helper_allowed(manifest)
            or operator_unlock_enabled(),
            "default_model": DEFAULT_MODEL,
            "five_player_lineup_size": FIVE_PLAYER_LINEUP_SIZE,
            "live_only": not bool(getattr(args, "allow_fixtures", False)),
            "data_root": str(Path(args.data_root)),
            "plan": plan_payload,
            "plan_error": plan_error,
        }
    )
    if plan_error is not None:
        return 4
    return 0 if health.get("ok") else 1


def cmd_serve(args: argparse.Namespace) -> int:
    result = ensure_ollama_serve(
        host=args.host,
        pidfile=Path(args.pidfile),
        logfile=Path(args.data_root) / "ollama_serve.log",
    )
    _print_json(result)
    return 0 if result.get("health", {}).get("ok") else 1


def cmd_plan(args: argparse.Namespace) -> int:
    try:
        plan = discover_day_plan(
            windows_json=Path(args.windows_json) if args.windows_json else None,
            include_fixtures=bool(getattr(args, "allow_fixtures", False)),
        )
    except LiveDataRequiredError as exc:
        _print_json({"error": "LIVE_DATA_REQUIRED", "detail": str(exc)})
        return 4
    now = _utc_now()
    payload = plan.to_dict()
    payload["now"] = now.isoformat().replace("+00:00", "Z")
    payload["should_run"] = plan.should_run(now)
    payload["active_sessions"] = [s.session_id for s in plan.active_sessions(now)]
    payload["pending_sessions"] = [s.session_id for s in plan.pending_sessions(now)]
    payload["closed_sessions"] = [s.session_id for s in plan.closed_sessions(now)]
    _print_json(payload)
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    try:
        plan = discover_day_plan(
            windows_json=Path(args.windows_json) if args.windows_json else None,
            include_fixtures=bool(getattr(args, "allow_fixtures", False)),
        )
    except LiveDataRequiredError as exc:
        _print_json({"error": "LIVE_DATA_REQUIRED", "detail": str(exc)})
        return 4
    data_root = Path(args.data_root)
    data_root.mkdir(parents=True, exist_ok=True)
    poll = max(1.0, float(args.poll_seconds))

    if args.ensure_serve:
        serve_result = ensure_ollama_serve(
            host=args.host,
            pidfile=Path(args.pidfile),
            logfile=data_root / "ollama_serve.log",
        )
        if not serve_result.get("health", {}).get("ok"):
            _print_json({"error": "ollama_serve_unhealthy", "serve": serve_result})
            return 2

    while True:
        now = _utc_now()
        if now < plan.arm_at:
            sleep_s = min(poll, max(1.0, (plan.arm_at - now).total_seconds()))
            _print_json(
                {
                    "phase": "waiting_for_earliest_t40",
                    "now": now.isoformat().replace("+00:00", "Z"),
                    "arm_at": plan.arm_at.isoformat().replace("+00:00", "Z"),
                    "sleep_s": sleep_s,
                    "pending": [s.session_id for s in plan.pending_sessions(now)],
                }
            )
            if args.once:
                return 0
            time.sleep(sleep_s)
            continue

        if now >= plan.release_at:
            _print_json(
                {
                    "phase": "released",
                    "now": now.isoformat().replace("+00:00", "Z"),
                    "release_at": plan.release_at.isoformat().replace("+00:00", "Z"),
                    "closed": [s.session_id for s in plan.closed_sessions(now)],
                }
            )
            return 0

        active = plan.active_sessions(now)
        _print_json(
            {
                "phase": "armed",
                "now": now.isoformat().replace("+00:00", "Z"),
                "arm_at": plan.arm_at.isoformat().replace("+00:00", "Z"),
                "release_at": plan.release_at.isoformat().replace("+00:00", "Z"),
                "active_sessions": [s.session_id for s in active],
                "pending_sessions": [s.session_id for s in plan.pending_sessions(now)],
            }
        )
        if args.once:
            return 0
        time.sleep(poll)


def cmd_learn(args: argparse.Namespace) -> int:
    """Learn ticks. Live: armed slates only. History: explicit file only."""

    manifest = load_manifest_or_empty(Path(args.manifest) if args.manifest else None)
    data_root = Path(args.data_root)
    history = bool(args.history_board)
    if history:
        paths = [Path(args.history_board)]
    elif args.board:
        paths = [Path(args.board)]
    else:
        try:
            plan = discover_day_plan(
                windows_json=Path(args.windows_json) if args.windows_json else None,
                include_fixtures=bool(getattr(args, "allow_fixtures", False)),
            )
        except LiveDataRequiredError as exc:
            _print_json({"error": "LIVE_DATA_REQUIRED", "detail": str(exc)})
            return 4
        # Live discovery: only data_root/<sport>/<slate_id>/hv_board.json for
        # slates armed right now. Never data_root/boards/** (history).
        paths = armed_board_paths(data_root, plan.active_sessions(_utc_now()))
    if not paths:
        _print_json({"error": "no_armed_hv_boards_found", "data_root": str(data_root)})
        return 1

    dry_run = not args.execute
    written: list[str] = []
    blocked: str | None = None
    for path in paths:
        try:
            summary = (
                load_history_board_summary(path)
                if history
                else load_pregame_board_summary(path)
            )
        except LiveDataRequiredError as exc:
            _print_json({"error": "LIVE_DATA_REQUIRED", "detail": str(exc)})
            return 4
        try:
            out = run_learn(
                summary,
                data_root=data_root / "history" if history else data_root,
                manifest=manifest,
                host=args.host,
                model=args.model,
                dry_run=dry_run,
            )
            written.append(str(out))
        except OllamaForbiddenError as exc:
            blocked = str(exc)
            break

    payload: dict[str, object] = {
        "dry_run": dry_run,
        "mode": "history" if history else "pregame",
        "written": written,
        "boards_seen": [str(p) for p in paths],
    }
    if blocked:
        payload["blocked"] = blocked
        payload["hint"] = (
            f"Set {UNLOCK_ENV}=1 for Codespace helper override, or wait for "
            "coverage_manifest.historical_capture_complete (#526)."
        )
        _print_json(payload)
        return 3
    _print_json(payload)
    return 0


def cmd_windows_from_apps(args: argparse.Namespace) -> int:
    """Write data_root/windows/<day>.json from each sport app's API."""

    sports = _sports(args.sports)
    if not sports:
        _print_json({"error": "LIVE_DATA_REQUIRED", "detail": "--sports required"})
        return 4
    day = args.day or default_day()
    try:
        payload = app_api.windows_payload(day, sports)
    except LiveDataRequiredError as exc:
        _print_json({"error": "LIVE_DATA_REQUIRED", "detail": str(exc)})
        return 4
    if not payload["slates"]:
        _print_json({"error": "LIVE_DATA_REQUIRED", **payload})
        return 4
    load_windows_payload(payload)  # validate before writing
    out = atomic_write_json(Path(args.data_root) / "windows" / f"{day}.json", payload)
    _print_json({"written": str(out), **payload})
    return 0


def cmd_daemon(args: argparse.Namespace) -> int:
    """Poll each sport app for armed slates; tick once per app freeze."""

    sports = tuple(_sports(args.sports))
    if not sports and not args.windows_json:
        _print_json(
            {
                "error": "LIVE_DATA_REQUIRED",
                "detail": "--daemon needs --sports (app windows) or --windows-json",
            }
        )
        return 4
    for sport in sports:
        try:
            app_api.base_url(sport)
        except LiveDataRequiredError as exc:
            _print_json({"error": "LIVE_DATA_REQUIRED", "detail": str(exc)})
            return 4
    data_root = Path(args.data_root)
    if args.ensure_serve:
        # Best effort only: an Ollama outage still records the app's five.
        ensure_ollama_serve(
            host=args.host,
            pidfile=Path(args.pidfile),
            logfile=data_root / "ollama_serve.log",
        )
    cfg = AppDaemonConfig(
        day=args.day or default_day(),
        sports=sports,
        data_root=data_root,
        windows_json=Path(args.windows_json) if args.windows_json else None,
        coverage_manifest=Path(args.manifest) if args.manifest else None,
        host=args.host,
        model=args.model,
        execute=bool(args.execute),
        poll_seconds=max(1.0, float(args.poll_seconds)),
    )
    result = run_app_daemon(cfg, max_iterations=args.max_iterations)
    _print_json(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ollama_hv_watcher",
        description="Ollama HV/TDV helper on each sport app's frozen picks (#574)",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status", action="store_true", help="Health + gate + window")
    mode.add_argument("--once", action="store_true", help="Single watch tick then exit")
    mode.add_argument(
        "--daemon",
        action="store_true",
        help="Poll sport apps for armed slates; tick once per app freeze",
    )
    mode.add_argument(
        "--windows-from-apps",
        action="store_true",
        help="Write data_root/windows/<day>.json from the sport app APIs",
    )
    parser.add_argument("--day", default="", help="Slate day YYYY-MM-DD (ET today)")
    parser.add_argument("--sports", default="", help="Comma list, e.g. nfl,wnba")
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--manifest", default="", help="Path to coverage_manifest.json")
    parser.add_argument("--windows-json", default="")
    parser.add_argument(
        "--allow-fixtures",
        action="store_true",
        help="Opt-in offline fixture calendars (tests only). Default is LIVE ONLY.",
    )
    parser.add_argument("--poll-seconds", type=float, default=30.0)
    parser.add_argument("--ensure-serve", action="store_true")
    parser.add_argument("--pidfile", default=str(DEFAULT_PIDFILE))
    parser.add_argument(
        "--board", default="", help="Explicit PREGAME board for --once --learn"
    )
    parser.add_argument(
        "--history-board",
        default="",
        help="Explicit post-game board (history path; never used for live ticks)",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Call Ollama generate (requires unlock); default is a dry-run tick",
    )
    parser.add_argument(
        "--learn",
        action="store_true",
        help="With --once: run learn on armed-slate pregame boards first",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "windows_json", "") == "":
        args.windows_json = None
    if getattr(args, "manifest", "") == "":
        args.manifest = None
    if getattr(args, "board", "") == "":
        args.board = None
    if getattr(args, "history_board", "") == "":
        args.history_board = None
    if args.status:
        return cmd_status(args)
    if args.windows_from_apps:
        return cmd_windows_from_apps(args)
    if args.once:
        args.once = True
        if args.learn or args.history_board:
            code = cmd_learn(args)
            if code not in (0, 3):
                return code
        return cmd_watch(args)
    if args.daemon:
        args.once = False
        return cmd_daemon(args)
    parser.error(
        "one of --status / --once / --daemon / --windows-from-apps is required"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

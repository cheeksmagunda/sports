"""CLI for the Ollama HV/TDV slate watcher (#574).

Modes (mutually exclusive)::

    PYTHONPATH=scripts python -m ollama_hv_watcher --status
    PYTHONPATH=scripts python -m ollama_hv_watcher --once
    PYTHONPATH=scripts python -m ollama_hv_watcher --daemon
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from realsports_corpus.coverage_manifest import (
    OllamaForbiddenError,
    ollama_helper_allowed,
)

from ollama_hv_watcher.boards import (
    discover_board_paths,
    load_board_summary,
)
from ollama_hv_watcher.client import DEFAULT_MODEL
from ollama_hv_watcher.discover import discover_day_plan
from ollama_hv_watcher.gate import (
    UNLOCK_ENV,
    load_manifest_or_empty,
    operator_unlock_enabled,
)
from ollama_hv_watcher.learn import run_learn
from ollama_hv_watcher.pick import FIVE_PLAYER_LINEUP_SIZE
from ollama_hv_watcher.serve import (
    DEFAULT_HOST,
    DEFAULT_PIDFILE,
    ensure_ollama_serve,
    health_check,
)

DEFAULT_DATA_ROOT = Path("data/ollama_hv")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def cmd_status(args: argparse.Namespace) -> int:
    health = health_check(args.host)
    manifest = load_manifest_or_empty(Path(args.manifest) if args.manifest else None)
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
            "data_root": str(Path(args.data_root)),
        }
    )
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
    plan = discover_day_plan(
        windows_json=Path(args.windows_json) if args.windows_json else None,
        include_fixtures=not args.no_fixtures,
    )
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
    plan = discover_day_plan(
        windows_json=Path(args.windows_json) if args.windows_json else None,
        include_fixtures=not args.no_fixtures,
    )
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
    manifest = load_manifest_or_empty(Path(args.manifest) if args.manifest else None)
    board_root = Path(args.board_root)
    paths = discover_board_paths(board_root)
    if args.board:
        paths = [Path(args.board)]
    if not paths:
        _print_json({"error": "no_hv_boards_found", "board_root": str(board_root)})
        return 1

    dry_run = not args.execute
    written: list[str] = []
    blocked: str | None = None
    for path in paths:
        summary = load_board_summary(path)
        try:
            out = run_learn(
                summary,
                data_root=Path(args.data_root),
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ollama_hv_watcher",
        description="Ollama HV/TDV self-learning slate watcher (#574)",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status", action="store_true", help="Health + gate + window")
    mode.add_argument("--once", action="store_true", help="Single watch tick then exit")
    mode.add_argument("--daemon", action="store_true", help="Watch until latest close")
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--manifest", default="", help="Path to coverage_manifest.json")
    parser.add_argument("--windows-json", default="")
    parser.add_argument("--no-fixtures", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=30.0)
    parser.add_argument("--ensure-serve", action="store_true")
    parser.add_argument("--pidfile", default=str(DEFAULT_PIDFILE))
    parser.add_argument("--board-root", default=".")
    parser.add_argument("--board", default="")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="With learn path: call Ollama generate (requires unlock)",
    )
    parser.add_argument(
        "--learn",
        action="store_true",
        help="During --once/--daemon armed tick, also run HV board learn",
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
    if args.status:
        return cmd_status(args)
    if args.once:
        args.once = True
        if args.learn and args.board:
            # one-shot learn then watch tick
            code = cmd_learn(args)
            if code not in (0, 3):
                return code
        return cmd_watch(args)
    if args.daemon:
        args.once = False
        return cmd_watch(args)
    parser.error("one of --status / --once / --daemon is required")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

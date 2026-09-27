"""CLI for the Ollama HV/TDV slate watcher (#574).

Commands:
  status   — Ollama health + model list
  plan     — discover day windows and print arm/release
  watch    — sleep until earliest T-40; stay until latest close
  learn    — offline HV board learn tick (gated; dry-run by default)
  serve    — ensure ``ollama serve`` is healthy (nohup + pidfile)

Examples::

    python -m ollama_hv_watcher status
    python -m ollama_hv_watcher plan --windows-json path/to/windows.json
    SPORTS_OLLAMA_UNLOCK=1 python -m ollama_hv_watcher learn --board hv.json
    SPORTS_OLLAMA_UNLOCK=1 nohup python -m ollama_hv_watcher watch \\
        --windows-json windows.json --ensure-serve \\
        >data/ollama_hv/watcher.log 2>&1 &
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

from ollama_hv_watcher.boards import discover_board_paths, load_board_summary  # noqa: E402
from ollama_hv_watcher.discover import discover_day_plan  # noqa: E402
from ollama_hv_watcher.gate import (  # noqa: E402
    UNLOCK_ENV,
    load_manifest_or_empty,
    operator_unlock_enabled,
)
from ollama_hv_watcher.learn import DEFAULT_MODEL, run_learn  # noqa: E402
from ollama_hv_watcher.serve import (  # noqa: E402
    DEFAULT_HOST,
    DEFAULT_PIDFILE,
    ensure_ollama_serve,
    health_check,
)
from realsports_corpus.coverage_manifest import (  # noqa: E402
    OllamaForbiddenError,
    ollama_helper_allowed,
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
            "training_allowed": ollama_helper_allowed(manifest) or operator_unlock_enabled(),
            "default_model": DEFAULT_MODEL,
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
    parser.add_argument(
        "--data-root",
        default=str(DEFAULT_DATA_ROOT),
        help="Durable artifact root (default: data/ollama_hv)",
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--manifest", default="", help="Path to coverage_manifest.json")
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="Ollama health + gate status")
    p_status.set_defaults(func=cmd_status)

    p_serve = sub.add_parser("serve", help="Ensure ollama serve is up")
    p_serve.add_argument("--pidfile", default=str(DEFAULT_PIDFILE))
    p_serve.set_defaults(func=cmd_serve)

    p_plan = sub.add_parser("plan", help="Print day arm/release plan")
    p_plan.add_argument("--windows-json", default="")
    p_plan.add_argument("--no-fixtures", action="store_true")
    p_plan.set_defaults(func=cmd_plan)

    p_watch = sub.add_parser("watch", help="Arm at earliest T-40 until latest close")
    p_watch.add_argument("--windows-json", default="")
    p_watch.add_argument("--no-fixtures", action="store_true")
    p_watch.add_argument("--poll-seconds", type=float, default=30.0)
    p_watch.add_argument("--once", action="store_true", help="Single status tick then exit")
    p_watch.add_argument("--ensure-serve", action="store_true")
    p_watch.add_argument("--pidfile", default=str(DEFAULT_PIDFILE))
    p_watch.set_defaults(func=cmd_watch)

    p_learn = sub.add_parser("learn", help="Offline HV learn tick (gated)")
    p_learn.add_argument("--board-root", default=".")
    p_learn.add_argument("--board", default="", help="Single HV board JSON path")
    p_learn.add_argument("--model", default=DEFAULT_MODEL)
    p_learn.add_argument(
        "--execute",
        action="store_true",
        help="Call Ollama generate (requires unlock or coverage complete)",
    )
    p_learn.set_defaults(func=cmd_learn)

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
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

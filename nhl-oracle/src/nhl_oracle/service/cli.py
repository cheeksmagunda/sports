"""CLI entrypoints for NHL staging API serve and idle worker roles."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from nhl_oracle.scheduler.readiness import empty_snapshot_readiness

# Between slates the runner refreshes the preview this often. Inside
# [t40_open - RUNNER_LEAD, lock_at) it runs every worker poll until frozen.
RUNNER_IDLE_SECONDS = 600
RUNNER_LEAD = timedelta(minutes=5)


def _serve(host: str, port: int) -> int:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn_required", file=sys.stderr)
        return 1
    uvicorn.run(
        "nhl_oracle.service.app:create_app",
        factory=True,
        host=host,
        port=port,
        access_log=False,
    )
    return 0


def _readiness_payload() -> dict[str, object]:
    """No injected slate: report the closed gate. Do not invent a five."""

    return empty_snapshot_readiness().to_dict()


def runner_enabled() -> bool:
    """Kill switch: ``NHL_T40_RUNNER=0`` returns the worker to a heartbeat."""

    value = os.environ.get("NHL_T40_RUNNER", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _log(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, default=str), flush=True)


class _Runner:
    """Decides when to run a T-40 cycle and persists each outcome."""

    def __init__(self) -> None:
        from nhl_oracle.service import lineup_store

        self.store = lineup_store
        self.engine = lineup_store.engine_from_env()
        if self.engine is not None:
            lineup_store.ensure_schema(self.engine)
        self.last_run: datetime | None = None
        self.last: dict[str, Any] | None = None

    def due(self, now: datetime) -> bool:
        if self.last_run is None or self.last is None:
            return True
        lock = self.last.get("lock_at")
        opened = self.last.get("t40_open")
        if self.last.get("status") != "frozen" and lock and opened:
            lock_at = datetime.fromisoformat(lock)
            open_at = datetime.fromisoformat(opened)
            if open_at - RUNNER_LEAD <= now < lock_at:
                return True
        return now - self.last_run >= timedelta(seconds=RUNNER_IDLE_SECONDS)

    def tick(self, now: datetime) -> None:
        from nhl_oracle.scheduler.live_cycle import run_cycle

        self.last_run = now
        outcome = asyncio.run(run_cycle())
        if outcome is None:
            self.last = None
            _log({"role": "worker", "status": "no_nhl_draft", "message": "no NHL draft on Real"})
            return
        payload = outcome.to_dict()
        stored = payload["status"]
        if self.engine is not None:
            stored = self.store.save_outcome(self.engine, payload)
        payload["stored_status"] = stored
        self.last = payload
        names = ", ".join(f"{p['slot']}:{p['name']}" for p in payload["lineup"]) or "none"
        _log(
            {
                "role": "worker",
                "status": stored,
                "day": payload["day"],
                "contest_id": payload["contest_id"],
                "pool_size": payload["pool_size"],
                "t40_open": payload["t40_open"],
                "blocked_reasons": payload["readiness"]["blocked_reasons"],
                "persisted": self.engine is not None,
                "message": f"nhl t40 {stored} {payload['day']} lineup {names}",
            }
        )


def _worker(*, once: bool, poll_seconds: int) -> int:
    """T-40 runner loop, or the observation heartbeat when the runner is off.

    The runner collects the Real pool, projects it, and persists a preview or
    frozen five (``scheduler.runner``). ``contest_entry`` stays false.
    """

    poll_seconds = max(1, poll_seconds)
    runner = _Runner() if runner_enabled() else None
    while True:
        if runner is not None:
            now = datetime.now(UTC)
            if runner.due(now):
                try:
                    runner.tick(now)
                except Exception as exc:  # one bad cycle must not stop the loop
                    _log(
                        {
                            "role": "worker",
                            "status": "cycle_error",
                            "error": type(exc).__name__,
                            "message": f"nhl t40 cycle error {type(exc).__name__}: {exc}"[:500],
                        }
                    )
        else:
            readiness = _readiness_payload()
            # Railway parses a JSON log line and shows `message`. Without it the
            # heartbeat renders as a blank line.
            message = (
                "nhl-worker observation heartbeat; freeze_ready stays false "
                "until a complete live slate is inside T-40"
            )
            _log(
                {
                    "role": "worker",
                    "status": "idle",
                    "observation_only": True,
                    "contest_entry": False,
                    "checked_at": datetime.now(UTC).isoformat(),
                    "freeze_ready": readiness["freeze_ready"],
                    "readiness": readiness,
                    "message": message,
                    "detail": message,
                }
            )
        if once:
            return 0
        time.sleep(poll_seconds)


def _cycle() -> int:
    """Run one live cycle and print it. Does not persist."""

    from nhl_oracle.scheduler.live_cycle import run_cycle

    outcome = asyncio.run(run_cycle())
    if outcome is None:
        print(json.dumps({"status": "no_nhl_draft"}), flush=True)
        return 0
    print(json.dumps(outcome.to_dict(), indent=2, default=str), flush=True)
    return 0


def _readiness() -> int:
    print(json.dumps(_readiness_payload()), flush=True)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nhl-pipeline")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="run the read-only staging API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    worker = commands.add_parser(
        "worker",
        help="T-40 runner loop (NHL_T40_RUNNER=0 for the idle heartbeat); no contest entry",
    )
    worker.add_argument("--once", action="store_true")
    worker.add_argument("--poll-seconds", type=int, default=60)
    commands.add_parser(
        "cycle",
        help="collect the Real pool, project, and print the five (no persist, no entry)",
    )
    commands.add_parser(
        "readiness",
        help="print T-40 win-freeze readiness (no live slate; contest_entry false)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "serve":
        return _serve(args.host, args.port)
    if args.command == "worker":
        return _worker(once=args.once, poll_seconds=args.poll_seconds)
    if args.command == "readiness":
        return _readiness()
    if args.command == "cycle":
        return _cycle()
    raise AssertionError(f"unhandled command {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())

"""CLI entrypoints for NHL staging API serve and idle worker roles."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime

from nhl_oracle.scheduler.readiness import empty_snapshot_readiness


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


def _worker(*, once: bool, poll_seconds: int) -> int:
    """Observation heartbeat. No provider calls; no contest entry.

    ``readiness.freeze_ready`` stays false until a caller injects a complete
    live slate inside the T-40 window. This loop does not collect that slate.
    """

    poll_seconds = max(1, poll_seconds)
    while True:
        readiness = _readiness_payload()
        payload = {
            "role": "worker",
            "status": "idle",
            "observation_only": True,
            "contest_entry": False,
            "checked_at": datetime.now(UTC).isoformat(),
            "freeze_ready": readiness["freeze_ready"],
            "readiness": readiness,
            "detail": (
                "nhl-worker observation heartbeat; freeze_ready stays false "
                "until a complete live slate is inside T-40"
            ),
        }
        print(json.dumps(payload), flush=True)
        if once:
            return 0
        time.sleep(poll_seconds)


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
        help="idle observation-only worker heartbeat (no provider / no entry)",
    )
    worker.add_argument("--once", action="store_true")
    worker.add_argument("--poll-seconds", type=int, default=60)
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
    raise AssertionError(f"unhandled command {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())

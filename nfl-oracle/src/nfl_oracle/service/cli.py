"""Run the read-only nfl-oracle research service."""

from __future__ import annotations

import argparse
import importlib
from typing import Any


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nfl-research-serve")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    args = parser.parse_args(argv)
    try:
        uvicorn: Any = importlib.import_module("uvicorn")
    except ImportError:
        print("uvicorn not installed; pip/uv add uvicorn to run the research server")
        return 2
    uvicorn.run(
        "nfl_oracle.service.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

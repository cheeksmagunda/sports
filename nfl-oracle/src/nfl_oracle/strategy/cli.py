"""CLI for strategy schema document (offline)."""

from __future__ import annotations

import argparse
import json
import sys

from nfl_oracle.strategy.document import strategy_document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nfl-strategy-schema")
    parser.add_argument(
        "--schema-only",
        action="store_true",
        default=True,
        help="Print the strategy scaffold document as JSON (default).",
    )
    parser.parse_args(argv)
    print(json.dumps(strategy_document(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Walk a JSON payload and emit every key path (corpus dump scaffold, #526).

Usage (offline, no credentials):
  python scripts/rs_corpus/dump_exposed_keys.py path/to/fixture.json

Writes a sorted unique key-path list to stdout. Nested lists use ``[]``.
Capture raw RS payloads in the separate corpus repo; inventory every
exposed key here for offline replay. Never mint credentials.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def walk_keys(node: Any, prefix: str = "") -> Iterator[str]:
    if isinstance(node, dict):
        if not node and prefix:
            yield prefix
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield path
            yield from walk_keys(value, path)
    elif isinstance(node, list):
        path = f"{prefix}[]" if prefix else "[]"
        if not node:
            yield path
            return
        for item in node[:50]:
            yield from walk_keys(item, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="JSON fixture paths")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON object {path: [keys...]} instead of flat lines",
    )
    args = parser.parse_args(argv)
    by_file: dict[str, list[str]] = {}
    for path in args.paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        keys = sorted(set(walk_keys(payload)))
        by_file[str(path)] = keys
    if args.json:
        json.dump(by_file, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        for path, keys in by_file.items():
            sys.stdout.write(f"# {path}\n")
            for key in keys:
                sys.stdout.write(f"{key}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Locate an nflverse context snapshot for offline Actions (#338).

Prints the resolved path and exits 0 when a snapshot exists. Exits 2 when
none is present so a race workflow can continue-on-error without inventing
context. Honors ``NFL_CONTEXT_SNAPSHOT`` when set.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from nfl_oracle.common.paths import resolve_project_root


def resolve_context_snapshot(
    project_root: Path, *, explicit: str | None = None
) -> Path | None:
    """Return the newest on-disk context snapshot, or an explicit override."""

    env_override = os.environ.get("NFL_CONTEXT_SNAPSHOT", "")
    override = (explicit if explicit is not None else env_override).strip()
    if override:
        path = Path(override).expanduser()
        if not path.is_file():
            raise FileNotFoundError("NFL_CONTEXT_SNAPSHOT_missing")
        return path
    paths = list((project_root / "data" / "artifacts" / "context").glob("*.json"))
    paths.extend((project_root / "data" / "artifacts" / "context").glob("**/*.json"))
    unique = {path.resolve(): path for path in paths if path.is_file()}
    if not unique:
        return None
    return max(unique.values(), key=lambda path: path.stat().st_mtime)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="nfl-oracle project root (default: resolve from this script)",
    )
    args = parser.parse_args(argv)
    project_root = args.project_root or resolve_project_root(__file__)
    try:
        path = resolve_context_snapshot(project_root)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if path is None:
        print("context snapshot: missing", file=sys.stderr)
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

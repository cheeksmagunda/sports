#!/usr/bin/env python3
"""Validate a verified NFL corpus backup snapshot.

Validation-only by design. NFL's frozen-lineup payload is a nested JSON
structure (unlike wnba-oracle's flat per-player rows), so a lossy CSV-to-
database reconstruction here would be strictly worse than the full-fidelity
path that already exists: `nfl-pipeline backup-export` / `backup-restore`
round-trip the exact original JSON with digest-chain verification. These CSVs
exist for historical analysis (easy to load into pandas, Excel, or a
warehouse), not as a disaster-recovery restore path. Use `nfl-pipeline
backup-restore` for that.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from nfl_corpus_backup_common import SnapshotValidationError, validate_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", required=True)
    args = parser.parse_args()

    snapshot_dir = pathlib.Path(args.snapshot_dir)
    try:
        manifest = validate_snapshot(snapshot_dir)
    except SnapshotValidationError as exc:
        print(f"ERROR: backup verification failed: {exc}", file=sys.stderr)
        return 1

    tables = manifest["tables"]
    print(
        "verified corpus backup:",
        ", ".join(f"{name}={tables[name]['rows']}" for name in sorted(tables)),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

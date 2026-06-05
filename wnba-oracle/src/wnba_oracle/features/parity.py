"""Train-serve parity audit.

Given the same (slate_date, pool, game_logs, team_stats, odds, lineups,
resolver) inputs, the train and serve feature pipelines must produce
identical DataFrames. Because both pipelines call into `build_slate_features`,
parity reduces to:

1. Run `build_slate_features` twice with the same inputs and the same
   feature module sha.
2. Assert column-set equality, row-count equality, and value equality
   on every column (after sorting by player_id).

Used both as a unit test (against fixtures) and as a runtime gate the
training CLI calls before pickling the artifact.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import polars as pl


class ParityFailure(AssertionError):
    """Train-serve parity check failed."""


def assert_parity(left: pl.DataFrame, right: pl.DataFrame) -> None:
    if left.shape != right.shape:
        raise ParityFailure(
            f"shape mismatch: train={left.shape} serve={right.shape}"
        )
    if set(left.columns) != set(right.columns):
        diff_l = set(left.columns) - set(right.columns)
        diff_r = set(right.columns) - set(left.columns)
        raise ParityFailure(
            f"column set mismatch: train_only={sorted(diff_l)} serve_only={sorted(diff_r)}"
        )
    left_sorted = left.sort("player_id").select(sorted(left.columns))
    right_sorted = right.sort("player_id").select(sorted(right.columns))
    if not left_sorted.equals(right_sorted):
        # Find the first mismatching column for a useful error message
        for col in left_sorted.columns:
            if not left_sorted[col].equals(right_sorted[col]):
                # Surface the row count of mismatches
                left_vals = left_sorted[col].to_list()
                right_vals = right_sorted[col].to_list()
                mism = [
                    (i, lv, rv)
                    for i, (lv, rv) in enumerate(zip(left_vals, right_vals, strict=False))
                    if lv != rv
                ][:5]
                raise ParityFailure(
                    f"value mismatch in column {col!r} (first 5): {mism}"
                )
        raise ParityFailure("frames differ but per-column equality could not localize it")


def feature_module_sha() -> str:
    """SHA over the feature-pipeline source. Pickled alongside the artifact
    so reloading verifies the build path hasn't drifted."""
    from pathlib import Path

    h = hashlib.blake2b(digest_size=16)
    for name in (
        "allowlist.py",
        "build.py",
        "rolling.py",
        "spec.py",
        "game_features.py",
        "corpus.py",
    ):
        p = Path(__file__).parent / name
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()


def feature_inputs_signature(
    *,
    slate_date: str,
    pool_count: int,
    game_logs_count: int,
    team_stats_count: int,
    odds_count: int,
    lineups_count: int,
) -> str:
    """Stable signature of the *inputs* used for parity comparison.
    Logged alongside the feature_module_sha for diagnostics."""
    payload: dict[str, Any] = {
        "slate_date": slate_date,
        "pool": pool_count,
        "game_logs": game_logs_count,
        "team_stats": team_stats_count,
        "odds": odds_count,
        "lineups": lineups_count,
    }
    return hashlib.blake2b(
        json.dumps(payload, sort_keys=True).encode(), digest_size=10
    ).hexdigest()

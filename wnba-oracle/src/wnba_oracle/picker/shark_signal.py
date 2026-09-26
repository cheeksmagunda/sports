"""Prior-only shark draft-rate signal.

"Sharks" are users who finish in the top-N of contest leaderboards on multiple
prior slates.  Their historical draft rates per player form a point-in-time
signal available before lock: a shark's lineups from slates strictly before the
target slate are aggregated, never the target slate itself.

Inputs are ordinary pandas DataFrames (no network, no database, no secrets),
so the helper can be unit-tested offline and reused by scripts, backtests, or
the optimizer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd

REQUIRED_LEADERBOARD_COLUMNS = frozenset({"slate_date", "rank", "user_id", "lineup"})


class SharkSignalError(ValueError):
    """Raised for malformed fixtures or unsupported configuration."""


def _validate_leaderboards(df: pd.DataFrame) -> pd.DataFrame:
    # Empty fixtures have no columns; callers still need config validation.
    if df.empty:
        return df
    missing = REQUIRED_LEADERBOARD_COLUMNS - set(df.columns)
    if missing:
        raise SharkSignalError(f"leaderboards missing columns: {sorted(missing)}")
    return df


def _validate_labels(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    required = {"slate_date", "platform_player_id"}
    missing = required - set(df.columns)
    if missing:
        raise SharkSignalError(f"labels missing columns: {sorted(missing)}")
    return df


def _parse_lineup(raw: object) -> list[int]:
    """Return the player ids in one leaderboard lineup, in committed order."""
    picks = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(picks, list) or len(picks) != 5:
        raise SharkSignalError("lineup must be a list of exactly 5 picks")
    out: list[int] = []
    for p in picks:
        if not isinstance(p, dict):
            raise SharkSignalError("each lineup pick must be an object")
        out.append(int(p["playerId"]))
    return out


def _explode_leaderboards(
    leaderboards: pd.DataFrame,
    *,
    top_n: int,
) -> pd.DataFrame:
    """One row per (slate_date, user_id, player_id) for top-N finishers."""
    if leaderboards.empty:
        return pd.DataFrame(columns=["slate_date", "user_id", "player_id"])
    rows = []
    for rec in leaderboards.itertuples(index=False):
        if int(rec.rank) > top_n:
            continue
        try:
            player_ids = _parse_lineup(rec.lineup)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SharkSignalError(
                f"unparseable lineup for slate={rec.slate_date} rank={rec.rank}: {exc}"
            ) from exc
        rows.extend(
            {
                "slate_date": str(rec.slate_date),
                "user_id": str(rec.user_id),
                "player_id": player_id,
            }
            for player_id in player_ids
        )
    return pd.DataFrame(rows)


def _identify_sharks(
    exploded: pd.DataFrame,
    *,
    target_slate_date: str,
    min_prior_appearances: int,
) -> set[str]:
    """Return raw user_ids that qualify as sharks from strictly prior slates."""
    prior = exploded[exploded["slate_date"] < target_slate_date]
    if prior.empty:
        return set()
    appearances = (
        prior.groupby("user_id")["slate_date"]
        .nunique()
        .loc[lambda s: s >= min_prior_appearances]
    )
    return set(appearances.index)


def _apply_lookback(
    exploded: pd.DataFrame,
    target_slate_date: str,
    max_lookback_slates: int | None,
) -> pd.DataFrame:
    """Restrict prior slates to the most recent ``max_lookback_slates``."""
    prior = exploded[exploded["slate_date"] < target_slate_date].copy()
    if prior.empty or max_lookback_slates is None:
        return prior
    distinct = sorted(prior["slate_date"].unique(), reverse=True)
    keep = set(distinct[:max_lookback_slates])
    return prior[prior["slate_date"].isin(keep)]


@dataclass(frozen=True)
class SharkSignalResult:
    """Typed result container for ``compute_shark_draft_rates``."""

    rates: pd.DataFrame
    sharks: set[str]
    total_shark_lineups: int
    prior_slates: list[str]


def compute_shark_draft_rates(
    leaderboards: pd.DataFrame,
    labels: pd.DataFrame,
    target_slate_date: str,
    *,
    top_n: int = 20,
    min_prior_appearances: int = 3,
    max_lookback_slates: int | None = None,
) -> SharkSignalResult:
    """Compute prior-only shark draft rates for a target slate.

    Parameters
    ----------
    leaderboards:
        DataFrame with columns ``slate_date``, ``rank``, ``user_id``,
        ``lineup``.  ``lineup`` is the platform's JSON array of five picks
        (each with ``playerId``) as stored in ``contest_leaderboards``.
    labels:
        DataFrame with columns ``slate_date`` and ``platform_player_id``.  Used
        to align output to the target slate's player pool.  Other columns are
        ignored.
    target_slate_date:
        ISO date string (e.g., ``"2026-09-27"``).  Only slates strictly before
        this date contribute to shark identification and draft rates.
    top_n:
        Finishers with ``rank <= top_n`` are considered for shark status.
    min_prior_appearances:
        A user must finish top-N on at least this many distinct prior slates
        to be treated as a shark.
    max_lookback_slates:
        If set, only the most recent N prior slates are used.  This lets
        callers decay older shark behavior.

    Returns
    -------
    SharkSignalResult with:
        rates:
            One row per player in the target slate pool.  Columns:
            ``platform_player_id``, ``shark_draft_count``,
            ``total_shark_lineups``, ``shark_draft_rate``.
        sharks:
            The set of qualifying raw ``user_id`` values.
        total_shark_lineups:
            Number of prior top-N lineups contributed by sharks.
        prior_slates:
            ISO date strings of the prior slates actually used.
    """
    if top_n < 1:
        raise SharkSignalError("top_n must be >= 1")
    if min_prior_appearances < 1:
        raise SharkSignalError("min_prior_appearances must be >= 1")
    _validate_leaderboards(leaderboards)
    _validate_labels(labels)

    exploded = _explode_leaderboards(leaderboards, top_n=top_n)
    prior = _apply_lookback(exploded, target_slate_date, max_lookback_slates)

    sharks = _identify_sharks(
        prior,
        target_slate_date=target_slate_date,
        min_prior_appearances=min_prior_appearances,
    )

    shark_rows = prior[prior["user_id"].isin(sharks)]
    # Count distinct prior top-N lineups (slate, user), not exploded player rows.
    total_shark_lineups = (
        int(shark_rows.groupby(["slate_date", "user_id"], sort=False).ngroups)
        if not shark_rows.empty
        else 0
    )
    prior_slates = sorted(shark_rows["slate_date"].unique()) if not shark_rows.empty else []

    target_pool = labels[labels["slate_date"] == target_slate_date][
        "platform_player_id"
    ].unique()

    if not sharks or not len(target_pool):
        rates = pd.DataFrame(
            {
                "platform_player_id": sorted(int(p) for p in target_pool),
                "shark_draft_count": 0,
                "total_shark_lineups": total_shark_lineups,
                "shark_draft_rate": 0.0,
            }
        )
        return SharkSignalResult(
            rates=rates,
            sharks=sharks,
            total_shark_lineups=total_shark_lineups,
            prior_slates=prior_slates,
        )

    counts = (
        shark_rows.groupby("player_id")
        .size()
        .rename("shark_draft_count")
        .reindex(target_pool, fill_value=0)
        .astype(int)
        .reset_index()
        .rename(columns={"player_id": "platform_player_id"})
    )
    counts["total_shark_lineups"] = total_shark_lineups
    counts["shark_draft_rate"] = (
        counts["shark_draft_count"] / total_shark_lineups
        if total_shark_lineups
        else 0.0
    )
    counts = counts.sort_values("platform_player_id").reset_index(drop=True)

    return SharkSignalResult(
        rates=counts,
        sharks=sharks,
        total_shark_lineups=total_shark_lineups,
        prior_slates=prior_slates,
    )


def shark_draft_rate_array(
    leaderboards: pd.DataFrame,
    labels: pd.DataFrame,
    target_slate_date: str,
    *,
    top_n: int = 20,
    min_prior_appearances: int = 3,
    max_lookback_slates: int | None = None,
) -> pd.Series:
    """Convenience wrapper returning a ``player_id -> shark_draft_rate`` Series.

    Useful when wiring the signal into the optimizer or a backtest loop.
    """
    result = compute_shark_draft_rates(
        leaderboards,
        labels,
        target_slate_date,
        top_n=top_n,
        min_prior_appearances=min_prior_appearances,
        max_lookback_slates=max_lookback_slates,
    )
    return result.rates.set_index("platform_player_id")["shark_draft_rate"]


def identify_sharks(
    leaderboards: pd.DataFrame,
    target_slate_date: str,
    *,
    top_n: int = 20,
    min_prior_appearances: int = 3,
) -> set[str]:
    """Standalone helper: return raw user_ids that qualify as sharks."""
    if top_n < 1:
        raise SharkSignalError("top_n must be >= 1")
    if min_prior_appearances < 1:
        raise SharkSignalError("min_prior_appearances must be >= 1")
    _validate_leaderboards(leaderboards)
    exploded = _explode_leaderboards(leaderboards, top_n=top_n)
    return _identify_sharks(
        exploded,
        target_slate_date=target_slate_date,
        min_prior_appearances=min_prior_appearances,
    )

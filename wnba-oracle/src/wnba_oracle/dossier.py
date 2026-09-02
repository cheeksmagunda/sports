"""Build dossier entries for finalized slates.

Dossier entries capture our committed pick, the best observed field entry,
and the theoretical ceiling under realized player values and contest rules.
Computation is driven by frozen_lineups, contest_leaderboards, and slate_labels.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import dataclass

import numpy as np
import sqlalchemy as sa
from oracle_core import (
    CensoringReason,
    Dossier,
    DossierEntry,
    EntryKind,
    Exactness,
    Gap,
)
from sqlalchemy import text

from wnba_oracle.db.engine import get_api_engine
from wnba_oracle.db.reads import read_slate_labels
from wnba_oracle.eval.contest_score import (
    DEFAULT_SLOT_BASES,
    committed_order_score,
)

DEFAULT_SLOTS = tuple(DEFAULT_SLOT_BASES)


def _extract_player_ids(lineup_data: object) -> list | None:
    """Pull the five committed platform player IDs out of a frozen lineup.

    ``frozen_lineups.lineup`` is a JSONB **object** written by job2's freeze
    (``{"player_ids": [...], "slot_multipliers": [...], "per_player": [...],
    ...}``); psycopg deserializes JSONB to a Python ``dict``. Earlier callers
    assumed the column was a bare JSON array of IDs, so iterating the dict with
    ``lineup_data[:5]`` raised ``TypeError`` and turned every live ``/dossier``
    request into a 500. Accept the real dict shape, a legacy bare list, and a
    JSON string of either. Returns None when no ID list can be recovered.
    """
    if isinstance(lineup_data, str):
        try:
            lineup_data = json.loads(lineup_data)
        except (json.JSONDecodeError, TypeError):
            return None
    if isinstance(lineup_data, dict):
        player_ids = lineup_data.get("player_ids")
        return list(player_ids) if isinstance(player_ids, list) else None
    if isinstance(lineup_data, list):
        return lineup_data
    return None


def _realized_oracle(pool_rows: list[dict[str, float]], cap: int) -> float:
    """Theoretical highest-value lineup under cap constraint.

    Brute force enumeration of top-26 pruned pool over C(n,5) combos,
    respecting the contest's per-team cap. Returns the best achievable score
    when sorted hindsight-optimal (by realized value).

    Args:
        pool_rows: List of dicts with keys real_score, card_boost, team_key
        cap: Maximum number of players from the same team

    Returns:
        Best achievable score under constraints, or -1.0 if infeasible
    """
    # Prune to top-26 by realized ceiling contribution
    pool_rows_sorted = sorted(
        pool_rows,
        key=lambda r: -(float(r["real_score"]) * (2.0 + float(r.get("card_boost", 0.0)))),
    )[:26]

    if len(pool_rows_sorted) < 5:
        return -1.0

    vals = np.array([float(r["real_score"]) for r in pool_rows_sorted], dtype=float)
    boosts = np.array([float(r.get("card_boost", 0.0)) for r in pool_rows_sorted], dtype=float)
    teams = np.array([str(r["team_key"]) for r in pool_rows_sorted])

    best = -1.0
    for combo in itertools.combinations(range(len(pool_rows_sorted)), 5):
        idx = list(combo)
        _, c = np.unique(teams[idx], return_counts=True)
        if c.max() > cap:
            continue
        v, b = vals[idx], boosts[idx]
        o = np.argsort(v)[::-1]
        score = float(np.sum(v[o] * (np.array(DEFAULT_SLOTS) + b[o])))
        best = max(best, score)

    return best


@dataclass
class _DossierWork:
    """Intermediate computation state for a slate's dossier."""

    slate_date: str
    committed_entry: DossierEntry | None = None
    committed_censor: CensoringReason | None = None
    field_entry: DossierEntry | None = None
    field_censor: CensoringReason | None = None
    ceiling_entry: DossierEntry | None = None
    ceiling_censor: CensoringReason | None = None


def build_dossier(
    slate_date: str,
    engine: sa.Engine | None = None,
    team_cap: int = 2,
) -> Dossier | None:
    """Build dossier for a finalized slate.

    Extracts our committed entry from frozen_lineups, field winner from
    contest_leaderboards, and theoretical ceiling from slate_labels +
    realized_oracle. Handles censoring when leaderboard depth or label
    coverage is incomplete.

    Args:
        slate_date: Slate date (YYYY-MM-DD format)
        engine: Database engine (defaults to API engine)
        team_cap: Per-team player cap for theoretical ceiling computation

    Returns:
        Dossier if all three entries can be computed; None if missing required data
    """
    eng = engine or get_api_engine()
    work = _DossierWork(slate_date=slate_date)

    with eng.connect() as conn:
        # Fetch our committed entry (most recent freeze for this slate).
        # frozen_lineups has no lineup_json column; the committed lineup lives
        # in the `lineup` JSONB object. Selecting a nonexistent column here was
        # the root of the live /dossier 500 (UndefinedColumn before any row
        # shape mattered).
        lineup_row = conn.execute(
            text(
                "SELECT lineup FROM frozen_lineups "
                "WHERE slate_date = :sd ORDER BY frozen_at DESC, id DESC LIMIT 1"
            ),
            {"sd": slate_date},
        ).first()

        # Fetch leaderboard top-1 (field winner)
        leaderboard_row = conn.execute(
            text(
                "SELECT entry_id, rank, score, lineup::text, num_brawlers "
                "FROM contest_leaderboards WHERE slate_date = :sd "
                "ORDER BY rank ASC LIMIT 1"
            ),
            {"sd": slate_date},
        ).first()

    # Read label corpus for scoring our entry and computing ceiling.
    # read_slate_labels returns every slate; scope to this slate before either
    # the committed lookup or the ceiling enumeration so the theoretical
    # ceiling is drawn only from players who actually played this slate (a
    # cross-slate pool would enumerate an impossible lineup) and so the
    # label-coverage censoring threshold counts this slate's rows, not the
    # whole season's.
    labels_df = read_slate_labels(engine=eng)
    if labels_df.is_empty():
        return None

    slate_rows = [row for row in labels_df.to_dicts() if row["slate_date"] == slate_date]
    if not slate_rows:
        return None

    labels_by_player = {
        (row["platform_player_id"], row["slate_date"]): {
            "real_score": row["real_score"],
            "card_boost": row.get("card_boost", 0.0),
            "team_key": row["team_key"],
        }
        for row in slate_rows
    }

    # Build our committed entry
    if lineup_row:
        lineup_list = _extract_player_ids(lineup_row.lineup)
        if lineup_list is None:
            return None

        our_values = []
        our_boosts = []
        for player_id in lineup_list[:5]:
            label = labels_by_player.get((player_id, slate_date))
            if not label or label.get("real_score") is None:
                work.committed_censor = CensoringReason.INCOMPLETE_LABELS
                break
            our_values.append(label["real_score"])
            our_boosts.append(label["card_boost"])

        if len(our_values) == 5:
            work.committed_entry = DossierEntry(
                kind=EntryKind.COMMITTED,
                score=committed_order_score(our_values, our_boosts),
                achievable=True,
                slot_order_basis="committed",
                censor_reason=work.committed_censor,
            )
        elif work.committed_censor and our_values:
            partial_score = committed_order_score(
                our_values + [0.0] * (5 - len(our_values)),
                our_boosts + [0.0] * (5 - len(our_boosts)),
            )
            work.committed_entry = DossierEntry(
                kind=EntryKind.COMMITTED,
                score=partial_score,
                achievable=False,
                slot_order_basis="committed",
                censor_reason=work.committed_censor,
            )

    # Build field winner entry
    if leaderboard_row:
        # Winner is exact only if rank 1 was captured
        winner_censor = None if leaderboard_row.rank == 1 else CensoringReason.LEADERBOARD_DEPTH

        work.field_entry = DossierEntry(
            kind=EntryKind.FIELD_BEST,
            score=float(leaderboard_row.score),
            achievable=True,
            slot_order_basis="as_entered",
            censor_reason=winner_censor,
        )

    # Build theoretical ceiling entry (slate-scoped pool only)
    pool_rows = [
        {
            "real_score": row["real_score"],
            "card_boost": row.get("card_boost", 0.0),
            "team_key": row["team_key"],
        }
        for row in slate_rows
        if row.get("real_score") is not None
    ]

    if pool_rows:
        ceiling_score = _realized_oracle(pool_rows, cap=team_cap)
        if ceiling_score > -1.0:
            ceiling_censor = CensoringReason.INCOMPLETE_LABELS if len(slate_rows) < 37 else None
            work.ceiling_entry = DossierEntry(
                kind=EntryKind.THEORETICAL_CEILING,
                score=ceiling_score,
                achievable=False,
                slot_order_basis="optimal_resort",
                censor_reason=ceiling_censor,
            )

    # Ensure we have all three entries
    if not all([work.committed_entry, work.field_entry, work.ceiling_entry]):
        return None

    assert work.committed_entry is not None
    assert work.field_entry is not None
    assert work.ceiling_entry is not None

    committed = work.committed_entry
    field = work.field_entry
    ceiling = work.ceiling_entry

    # Build gaps
    gap_to_field = Gap(
        from_kind=EntryKind.COMMITTED,
        to_kind=EntryKind.FIELD_BEST,
        value=field.score - committed.score,
        exactness=_gap_exactness(
            committed.censor_reason,
            field.censor_reason,
        ),
        from_censor=committed.censor_reason,
        to_censor=field.censor_reason,
    )

    gap_field_to_ceiling = Gap(
        from_kind=EntryKind.FIELD_BEST,
        to_kind=EntryKind.THEORETICAL_CEILING,
        value=ceiling.score - field.score,
        exactness=_gap_exactness(
            field.censor_reason,
            ceiling.censor_reason,
            involves_pruned_ceiling=True,
        ),
        from_censor=field.censor_reason,
        to_censor=ceiling.censor_reason,
    )

    gap_to_ceiling = Gap(
        from_kind=EntryKind.COMMITTED,
        to_kind=EntryKind.THEORETICAL_CEILING,
        value=ceiling.score - committed.score,
        exactness=_gap_exactness(
            committed.censor_reason,
            ceiling.censor_reason,
            involves_pruned_ceiling=True,
        ),
        from_censor=committed.censor_reason,
        to_censor=ceiling.censor_reason,
    )

    return Dossier(
        slate_date=slate_date,
        entries={
            EntryKind.COMMITTED: committed,
            EntryKind.FIELD_BEST: field,
            EntryKind.THEORETICAL_CEILING: ceiling,
        },
        gap_to_field=gap_to_field,
        gap_field_to_ceiling=gap_field_to_ceiling,
        gap_to_ceiling=gap_to_ceiling,
    )


def _gap_exactness(
    from_censor: CensoringReason | None,
    to_censor: CensoringReason | None,
    *,
    involves_pruned_ceiling: bool = False,
) -> Exactness:
    """Determine gap exactness from endpoint censoring.

    A gap is exact only if both endpoints are exact (uncensored) AND neither
    endpoint is the theoretical ceiling. ``_realized_oracle`` prunes the pool
    to the top 26 candidates by an upper-bound heuristic before enumerating
    every 5-player combination under the team cap; that prefix is not proven
    to contain the cap-constrained optimum (a binding cap can force the true
    best lineup to include a candidate ranked below 26), so the ceiling is at
    best a lower bound on the true theoretical ceiling even when every label
    is uncensored. If either endpoint is censored, the gap is at least a
    lower_bound (unless unknown).
    """
    if from_censor == CensoringReason.UNKNOWN_PLACEMENT or (
        to_censor == CensoringReason.UNKNOWN_PLACEMENT
    ):
        return Exactness.UNKNOWN
    if from_censor is None and to_censor is None and not involves_pruned_ceiling:
        return Exactness.EXACT
    return Exactness.LOWER_BOUND

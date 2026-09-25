"""Point-in-time helpers for offline replay and walk-forward evaluation.

Live freezes never see same-slate ``slate_labels.drafts`` (day-close writes
them the morning after; pregame ``draftStats`` is empty). Benchmarks and
tournaments must not feed a slate its own realized ownership into measured
ownership / leverage / contrarian paths. See #289 / #38.
"""

from __future__ import annotations


def causal_drafts_for_slate(
    slate_date: str,
    drafts_by_slate: dict[str, dict[int, int]],
    pool_pids: set[int] | None = None,
) -> dict[int, int]:
    """Each player's draft count from the most recent slate STRICTLY BEFORE
    ``slate_date``.

    Players with no prior observation are omitted (consumers treat missing
    as zero penalty / estimator fallback). Never returns drafts from
    ``slate_date`` or any later slate.
    """
    out: dict[int, int] = {}
    for sd in sorted(drafts_by_slate, reverse=True):
        if sd >= slate_date:
            continue
        for pid, n in drafts_by_slate[sd].items():
            if pid in out:
                continue
            if pool_pids is not None and pid not in pool_pids:
                continue
            out[pid] = n
    return out

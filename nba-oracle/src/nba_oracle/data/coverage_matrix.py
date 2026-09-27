"""Build an honest multi-year coverage matrix before any Real Sports load."""

from __future__ import annotations

from datetime import date
from typing import Any

from nba_oracle.calendar.season import tracked_seasons
from nba_oracle.data.coverage import SeasonCoverageRow


def empty_gap_matrix(
    *,
    now: date | None = None,
    blocked_reason: str = "realsports_auth_unavailable",
) -> list[SeasonCoverageRow]:
    """Every tracked season starts blocked until an honest ingest proves otherwise."""

    return [
        SeasonCoverageRow(
            season=season,
            status="blocked",
            game_ids=(),
            value_presence_note="no_nba_corpus_g_rows_verified",
            blocked_reason=blocked_reason,
        )
        for season in tracked_seasons(now)
    ]


def matrix_to_dict(rows: list[SeasonCoverageRow]) -> dict[str, Any]:
    return {
        "sport": "nba",
        "schema": "nba_oracle.coverage_matrix.v1",
        "seasons": [row.to_dict() for row in rows],
        "gap_summary": {
            "blocked": sum(1 for row in rows if row.status == "blocked"),
            "unknown": sum(1 for row in rows if row.status == "unknown"),
            "known": sum(1 for row in rows if row.status == "known"),
            "first_season": rows[0].season if rows else None,
            "last_season": rows[-1].season if rows else None,
        },
    }

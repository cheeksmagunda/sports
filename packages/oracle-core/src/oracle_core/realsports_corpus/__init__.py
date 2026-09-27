"""Provider-neutral Real Sports history corpus layout (issue #526).

Durable offline history for WNBA / NFL / NBA / NHL so models train and serve
from (1) today's slate + boost pool and (2) this corpus, without a daily
full-history Real Sports re-scrape.

Layout under a **separate** GitHub-tracked corpus repo root
(``cheeksmagunda/sports-realsports-corpus`` preferred)::

    {sport}/{season}/{slate_or_game_id}/{artifact}.json
    coverage/manifest.json

Artifacts (append-only; overwrite only when content sha changes)::

    hv_board.json       Total Value / highestBoostedValuePlayers leaderboard
    draft_stats.json    all draftStats sections
    pool_card.json      contest/pool card snapshot
    game_stats.json     box / game stats payload
    matchups.json       home/away, opponent, pace/context
    feed.json           play feed (when captured)

This package stays domain-free: sport codes and slate/game ids are opaque
strings; sport apps own parsing and auth. Never store secrets or
storage_state material in corpus files.
"""

from __future__ import annotations

from oracle_core.realsports_corpus.layout import (
    ARTIFACT_NAMES,
    ArtifactName,
    SportCode,
    artifact_path,
    season_from_iso_date,
    slate_or_game_key,
)
from oracle_core.realsports_corpus.manifest import (
    COVERAGE_MANIFEST_RELPATH,
    CoverageEntry,
    CoverageManifest,
    load_coverage_manifest,
    upsert_coverage_entry,
    write_coverage_manifest,
)
from oracle_core.realsports_corpus.store import (
    append_artifact,
    artifact_sha256,
    write_json_artifact,
)

__all__ = [
    "ARTIFACT_NAMES",
    "ArtifactName",
    "COVERAGE_MANIFEST_RELPATH",
    "CoverageEntry",
    "CoverageManifest",
    "SportCode",
    "append_artifact",
    "artifact_path",
    "artifact_sha256",
    "load_coverage_manifest",
    "season_from_iso_date",
    "slate_or_game_key",
    "upsert_coverage_entry",
    "write_coverage_manifest",
    "write_json_artifact",
]

"""NFL Real Sports ingest surfaces (Corpus G first)."""

from nfl_oracle.ingest.backfill import backfill_season, load_cursor, save_cursor
from nfl_oracle.ingest.corpus_g import CorpusGStore, GameIngestResult, ingest_game
from nfl_oracle.ingest.redact import redact_corpus_payload

__all__ = [
    "CorpusGStore",
    "GameIngestResult",
    "backfill_season",
    "ingest_game",
    "load_cursor",
    "redact_corpus_payload",
    "save_cursor",
]

"""NBA Real Sports ingest surfaces (Corpus G gate first)."""

from nba_oracle.ingest.auth import AuthPresence, auth_presence
from nba_oracle.ingest.backfill import main, run

__all__ = ["AuthPresence", "auth_presence", "main", "run"]

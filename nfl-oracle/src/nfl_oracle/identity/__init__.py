"""Player identity scaffolding (Real Sports id primary)."""

from nfl_oracle.identity.density import IdentityDensity, summarize_identity_density
from nfl_oracle.identity.from_corpus import upsert_from_players_payload
from nfl_oracle.identity.map import IdentityMap, IdentityRecord

__all__ = [
    "IdentityDensity",
    "IdentityMap",
    "IdentityRecord",
    "summarize_identity_density",
    "upsert_from_players_payload",
]

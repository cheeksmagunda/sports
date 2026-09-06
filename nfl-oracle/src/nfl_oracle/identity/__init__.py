"""Player identity scaffolding (Real Sports id primary)."""

from nfl_oracle.identity.aliases import (
    apply_alias_table,
    merge_external_ids,
    name_match_keys,
    normalize_alias_key,
    normalize_display_name,
    reconcile_alias_collisions,
    suggest_dedup_candidates,
    upsert_with_aliases,
)
from nfl_oracle.identity.density import IdentityDensity, summarize_identity_density
from nfl_oracle.identity.from_corpus import upsert_from_players_payload
from nfl_oracle.identity.load import (
    identity_players_file,
    load_identity_map_from_players_file,
    research_identity_summary,
)
from nfl_oracle.identity.map import IdentityMap, IdentityRecord

__all__ = [
    "IdentityDensity",
    "IdentityMap",
    "IdentityRecord",
    "apply_alias_table",
    "identity_players_file",
    "load_identity_map_from_players_file",
    "merge_external_ids",
    "name_match_keys",
    "normalize_alias_key",
    "normalize_display_name",
    "reconcile_alias_collisions",
    "research_identity_summary",
    "suggest_dedup_candidates",
    "summarize_identity_density",
    "upsert_from_players_payload",
    "upsert_with_aliases",
]

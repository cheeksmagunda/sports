# Design: canonical player identity persistence (#30)

Status: design-only, not implemented, per explicit scope decision on 2026-08-30

## Problem

`wnba_oracle.ingest.identity.Resolver.resolve()` already resolves a Real
Sports `player_id` to an `nba_api`/stats.wnba.com player id, via three
methods in priority order: (1) an explicit override
(`data/identity_overrides.csv`), (2) the platform-provided `nbaId` when
present, (3) normalized-name matching against the static WNBA player
catalog, falling back to `None` on ambiguity or no match. This resolution
happens live, in-process, every time it's needed (job1 enrichment, dossier
computation) -- there is no persisted, canonical, cross-corpus identity
table. Consequences:

- Prediction-to-outcome analysis across corpora (`job1_enrichment` uses
  Real Sports ids, `wnba_game_logs` uses stats.wnba.com ids) falls back to
  name matching at query time instead of a stable join key.
- Resolution method and confidence are not recorded anywhere -- a name-match
  resolution and a `nbaId`-trusted resolution are indistinguishable once
  the `int` comes back, so nothing downstream can tell "resolved with high
  confidence" from "resolved via the weakest fallback."
- An ambiguous or failed resolution (`None`) is only visible in
  `write_unresolved_log`'s output file, not queryable alongside the rest of
  the corpus.

## Proposed schema

```sql
CREATE TABLE player_identity (
    real_sports_player_id VARCHAR(32) PRIMARY KEY,
    wnba_player_id BIGINT,              -- nba_api id; NULL if unresolved
    resolution_method VARCHAR(16) NOT NULL,  -- 'override' | 'nba_id' | 'name_match' | 'unresolved'
    display_name VARCHAR(128) NOT NULL, -- Real Sports name at resolution time
    matched_name VARCHAR(128),           -- catalog name it matched, if name_match
    team_key VARCHAR(8),
    first_resolved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_confirmed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (resolution_method = 'unresolved' AND wnba_player_id IS NULL)
        OR (resolution_method != 'unresolved' AND wnba_player_id IS NOT NULL)
    )
);
CREATE INDEX ix_player_identity_wnba_player_id ON player_identity (wnba_player_id);
```

Keyed by `real_sports_player_id` (stable per the provider, per
`job1_enrichment.real_sports_player_id`'s existing usage) rather than by
`wnba_player_id`, since the resolution direction is always Real-Sports-in,
stats.wnba.com-out, and a `wnba_player_id` can legitimately be `NULL`
(unresolved) while `real_sports_player_id` never is.

## Key design decisions

- **Persist the method, not just the answer.** `resolution_method` is the
  whole point of this table over "just cache the `int`" -- it lets
  downstream consumers (this session's `frozen_lineups`, the dossier, any
  future cross-sport identity work) filter or weight by confidence, and
  lets a future audit find every player who was ever resolved by the
  weakest path (name-match) for re-verification.
- **Upsert with `last_confirmed_at`, not append-only.** Unlike
  `contest_placements`/`frozen_lineups` (audit trails where every write
  matters), identity is a single current-truth fact per player --
  `first_resolved_at` preserves when it was first established,
  `last_confirmed_at` advances on every subsequent job1 run that resolves
  the same `real_sports_player_id` the same way, and *changes* only when
  `resolution_method` or `wnba_player_id` actually differ from the stored
  row (a real re-resolution, worth its own log line, not silent).
- **Wire it as a read-through cache in `Resolver`, not a parallel path.**
  `Resolver.resolve()` gains an optional `conn` parameter: check
  `player_identity` first (by `real_sports_player_id`), and only fall
  through to the existing override/nba_id/name-match ladder on a cache
  miss, persisting the result before returning. This keeps exactly one
  resolution algorithm (the existing one) with persistence as a side
  effect, rather than two implementations that could drift.
- **Unresolved players get a row too.** A `resolution_method='unresolved'`
  row (with `wnba_player_id NULL`) is written on a genuine miss, not just
  logged to `write_unresolved_log`'s file. This makes "how many players are
  we currently failing to resolve, and who are they" a query instead of a
  log-scrape, and naturally de-dupes repeated misses for the same player
  across slates (the CHECK constraint keeps the two states mutually
  exclusive at the schema level).

## What this does NOT do (explicitly out of scope for the design)

- Does not change `data/identity_overrides.csv` as the override mechanism
  -- overrides stay operator-editable CSV, feeding into `player_identity`
  as `resolution_method='override'` rather than being replaced by it.
- Does not attempt automatic re-resolution of existing `unresolved` rows on
  a schedule -- that's a reasonable follow-up (a scheduled job re-running
  the ladder against players still unresolved after N days, in case the
  static catalog updates), but is a separate, smaller design once this
  table exists.
- Does not touch `wnba_game_logs`' own team/identity vocabulary
  (`wnba-oracle/AGENTS.md`'s explicit boundary: gamelog and label corpora
  need an explicit identity map, not a silent join) -- this table
  *provides* that map's player-id half; joining game logs to labels through
  it is a consumer decision, not part of this schema.

## Migration sketch

A new alembic revision adding the single table above. Backfill (a script
running the existing `Resolver` over every distinct
`real_sports_player_id` already seen in `job1_enrichment`, populating
`player_identity` from data already in the corpus) is a natural first use
once implemented, but is backfill work for the implementation pass, not
part of this design.

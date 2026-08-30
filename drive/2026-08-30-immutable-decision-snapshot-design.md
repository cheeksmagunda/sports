# Design: immutable decision-input snapshot (#35 Phase 2)

Status: design-only, not implemented, per explicit scope decision on 2026-08-30
(F2 stays design-only; F6 was implemented in full this session, see STATUS.md)

## Problem

`ScoringProvenance` (already shipped) captures hashes of the compiled model
policy, the enrichment sequence, and the finalized optimizer inputs at
freeze time -- strong evidence that a given freeze is reproducible in
principle. What it does not do is preserve the actual raw/derived values
those hashes are *of*. `job1_enrichment` is a mutable per-slate table: a
later Job 1 re-capture (or the #32 pool-card-rollover bug this session
fixed) can overwrite the exact rows Job 2 read at freeze time. Today,
reconstructing "what did the model actually see" for a past freeze requires
trusting that `job1_enrichment`'s current contents still match what existed
at freeze time -- which is exactly the assumption #32 showed can be false.

## Proposed schema

One new append-only table, `freeze_decision_snapshot`, written once per
freeze (same trigger point as `frozen_lineups` and the new
`player_slate_ownership` projected-write added this session in job2.py):

```sql
CREATE TABLE freeze_decision_snapshot (
    id BIGSERIAL PRIMARY KEY,
    slate_date VARCHAR(16) NOT NULL,
    model_sha VARCHAR(64) NOT NULL,
    freeze_seq INTEGER NOT NULL,        -- matches frozen_lineups.freeze_seq
    enrichment_rows_json JSONB NOT NULL,      -- exact rows Job 2 scored, verbatim
    prediction_components_json JSONB NOT NULL, -- per-player tier + intermediate adjustments
    optimizer_inputs_json JSONB NOT NULL,      -- already computed for ScoringProvenance
    identity_resolution_json JSONB,            -- per-player method + status (see F5)
    enrichment_sha256 CHAR(64) NOT NULL,        -- must equal ScoringProvenance's hash
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (slate_date, model_sha, freeze_seq)
);
CREATE INDEX ix_freeze_decision_snapshot_slate_date ON freeze_decision_snapshot (slate_date);
```

Written from `job2._freeze_recommendation` (or immediately after, same
non-fatal-wrapper pattern this session used for `player_slate_ownership`)
using data already assembled in `run()`'s scope: `enrichment_raw` /
`enrichment` (post-cascade), `preds` (per-player prediction components from
`predict_players`), and the existing `scoring_provenance.optimizer_inputs`.
No new capture logic needed -- this is a serialization step over values
`run()` already holds by the time `_freeze_recommendation` returns.

## Key design decisions

- **Verbatim rows, not a diff.** `enrichment_rows_json` stores the full row
  set, not a diff against some baseline. A slate-day's enrichment is small
  (60-90 rows), so the storage cost is trivial next to the reconstruction
  value; a diff format would need its own schema-versioning story for no
  real savings.
- **`enrichment_sha256` cross-checks `ScoringProvenance`.** The snapshot's
  hash of its own `enrichment_rows_json` must equal
  `scoring_provenance.enrichment_sha256` (already persisted in
  `frozen_lineups.metadata_json`). A test asserting this equality is the
  wiring guarantee -- if it ever drifts, the snapshot is not describing the
  freeze it claims to.
- **Keyed by (slate_date, model_sha, freeze_seq), not by frozen_lineups.id.**
  Matches the existing audit-trail convention (`contest_placements`'
  `freeze_seq` parameter, `frozen_lineups`' own append-only design) so a
  late re-freeze produces a second snapshot row rather than overwriting the
  first.
- **Content-addressed, not deduplicated across slates.** The brief's
  "avoid duplicating large payloads... if content-addressed snapshots/hashes
  plus immutable rows provide an equivalent reconstruction contract" is
  satisfied by storing the hash *alongside* the payload in the same row,
  not by a separate blob store -- there is no cross-slate duplication to
  dedupe (each slate's enrichment is already unique), so a content-addressed
  store would add operational complexity (garbage collection, referential
  integrity) without a real storage win at this scale (~90 rows/slate,
  ~180 slates/season).

## What this does NOT do (explicitly out of scope for the design)

- Does not change `job1_enrichment`'s mutability -- that table stays a
  working/serving table; this snapshot is the audit copy, not a proposal to
  make `job1_enrichment` append-only (that would be a much larger change
  touching every writer).
- Does not retroactively backfill past freezes -- the snapshot only exists
  from the freeze it ships in forward one. A past freeze's exact
  enrichment state, if already overwritten, is not recoverable regardless
  of this design.
- Does not define the identity-resolution status format in detail -- see
  the companion F5 design doc; `identity_resolution_json` here is a
  placeholder for whatever that design settles on.

## Migration sketch

A new alembic revision adding the single table above, following the same
pattern as `20260613_0007_contest_placements.py` (two related append-only
tables added together was precedent; this is a similar-weight addition).
Not written as part of this design pass -- writing the migration without
implementing the writer risks a schema nobody's code path matches yet.

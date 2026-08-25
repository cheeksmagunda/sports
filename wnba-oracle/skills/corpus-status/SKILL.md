---
name: wnba-oracle-corpus-status
description: >
  Audit the WNBA Oracle training corpus and model artifact. Verifies that
  the backups branch is current, the model artifact SHA matches STATUS.md,
  and the game-log corpus covers the expected date range. Use before a
  training run, before promoting a new model artifact, or after a production
  incident to verify corpus integrity.
  Authoritative stores: Postgres (wnba_game_logs), GitHub backups branch,
  STATUS.md (artifact SHA pin).
license: proprietary
---

## What is the corpus?

The corpus has two separate grains:
1. **wnba_game_logs** (Postgres): per-player per-game ground truth for
   minutes, box-score stats, and real_score. Written by dayclose and
   backfill. This is the label corpus for training.
2. **player_pool / player_features** (Postgres): per-player per-slate
   enrichment written by job1/job1-late. This is the feature corpus.

These grains have different identifiers (game_date vs slate_date,
player_id vs nba_api player identity). Do not join them without the
WNBA-owned identity map (`ingest/identity.py`).

## Step 1: Check corpus coverage in Postgres

```sh
uv run --package wnba-oracle python -c "
from wnba_oracle.db.engine import get_engine
from sqlalchemy import text

engine = get_engine()
with engine.connect() as conn:
    # Game-log coverage
    row = conn.execute(text(
        '''SELECT MIN(game_date)::text AS earliest,
                  MAX(game_date)::text AS latest,
                  COUNT(DISTINCT game_date) AS n_game_dates,
                  COUNT(DISTINCT player_id) AS n_players,
                  COUNT(*) AS n_rows
           FROM wnba_game_logs'''
    )).fetchone()
    print('Game log corpus:')
    print(f'  Dates: {row.earliest} to {row.latest} ({row.n_game_dates} game dates)')
    print(f'  Players: {row.n_players}, Rows: {row.n_rows}')

    # Slate label coverage
    row2 = conn.execute(text(
        '''SELECT MIN(slate_date)::text AS earliest,
                  MAX(slate_date)::text AS latest,
                  COUNT(DISTINCT slate_date) AS n_slates,
                  COUNT(CASE WHEN real_score IS NOT NULL THEN 1 END) AS n_labeled
           FROM slate_labels'''
    )).fetchone()
    print('Slate labels:')
    print(f'  Slates: {row2.earliest} to {row2.latest} ({row2.n_slates} total, {row2.n_labeled} labeled)')
"
```

## Step 2: Verify model artifact identity

Check the current `STATUS.md` artifact SHA against the loaded artifact:

```sh
# From wnba-oracle/
uv run --package wnba-oracle python scripts/compare_artifacts.py
```

This script reads the SHA from `STATUS.md` and compares it to the artifact
loaded by job2. A mismatch means either:
- A new artifact was trained but STATUS.md was not updated, or
- The artifact file was replaced without a PR.

Correct path: update STATUS.md in a PR with the new artifact SHA and a
commit-SHA link. Never rotate the artifact without a tracked STATUS.md change.

## Step 3: Check the GitHub backups branch

The `backups` branch holds JSON exports of the corpus. This is non-canonical
(Postgres is canonical), but it is the off-site recovery path for training.

```sh
# List recent backup objects on the backups branch
git fetch origin backups
git log origin/backups --oneline -10
```

If the last backup is more than 7 days old, the GitHub Actions corpus backup
workflow may have failed. Check the Actions run log for `corpus-backup`.

To trigger a manual backup:

```sh
gh workflow run corpus-backup.yml --ref main
```

## Step 4: Snapshot training inputs for a new model run

Before training, snapshot the feature and label corpus from Postgres:

```sh
# From wnba-oracle/
uv run --package wnba-oracle python scripts/snapshot_training_inputs.py \
  --output runs/training-snapshot-$(date +%Y%m%d)/
```

The snapshot writes to `runs/` (gitignored). Record the snapshot date and
Postgres row counts in the training PR, not in STATUS.md.

## Step 5: Run the training pipeline (offline, not on a game day)

Training uses the snapshotted corpus, not a live Postgres connection:

```sh
# From wnba-oracle/ -- only run when no live contest is active
uv run --package wnba-oracle python -m wnba_oracle.train.cli \
  --corpus runs/training-snapshot-<date>/ \
  --output models/
```

After training, verify the new artifact with:

```sh
uv run --package wnba-oracle python scripts/validate_minutes_model.py \
  --artifact models/<new-artifact>.pkl
```

If validation passes, update `STATUS.md` with the new artifact SHA and
open a PR. The PR must include a `make test-contract` run from `wnba-oracle/`.

## Constraints

- The model artifact SHA in `STATUS.md` is the canonical identity. The
  `WNBA_ORACLE_MODEL_ARTIFACT_SHA` Railway env var must match it on every
  production service.
- `wnba_game_logs` and `player_pool/player_features` have different grains.
  Do not join them without `ingest/identity.py`.
- Training must not run on a game-day job2 Railway service. Use a local or
  Codespace environment with a Postgres connection to the production DB (read
  operations only during training data export).
- Local `models/` and `runs/` are non-canonical. The artifact identity is the
  SHA, not the filename.

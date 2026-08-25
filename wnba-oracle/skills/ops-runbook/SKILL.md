---
name: wnba-oracle-ops-runbook
description: >
  Operational runbook for WNBA Oracle. Step-by-step procedures for common
  game-day operations, incident response, service health checks, and
  controlled configuration changes. Use this as the first reference when
  something is wrong or when making a production change.
  This skill cites the authoritative store for every check.
license: proprietary
---

## Data flow reference

```
providers (Real Sports, Odds API, RotoWire)
    -> job1 (13:00 ET) -> Postgres (player_pool, player_features, slate_meta)
    -> job1-late (T-120) -> Postgres (player_features: starter flags update)
    -> job2 (T-40 from first tip) -> Redis (lease) + Postgres (frozen_lineups)
    -> api (always live) -> reads Postgres only
    -> dayclose (post-game) -> Postgres (slate_labels, wnba_game_logs, contest_placements)
    -> GitHub Actions (corpus-backup, watchdog, pre-freeze, day-close verify)
```

Redis is coordination only. Postgres is the source of truth for all
player, lineup, and label data.

## Game day checklist

Run from `wnba-oracle/`:

```sh
# 1. Verify job1 ran and pool is non-empty
uv run --package wnba-oracle python -c "
from wnba_oracle.common.clock import slate_date
from wnba_oracle.db.engine import get_engine
from sqlalchemy import text
sd = slate_date()
engine = get_engine()
with engine.connect() as conn:
    n = conn.execute(text(
        'SELECT COUNT(*) FROM player_pool WHERE slate_date = :sd'
    ), {'sd': sd}).scalar()
    print('Pool size for', sd, ':', n)
"

# 2. Verify freeze completed
uv run --package wnba-oracle python -c "
from wnba_oracle.common.clock import slate_date
from wnba_oracle.db.engine import get_engine
from sqlalchemy import text
sd = slate_date()
engine = get_engine()
with engine.connect() as conn:
    row = conn.execute(text(
        'SELECT recommendation, ev_estimate, created_at FROM frozen_lineups WHERE slate_date = :sd ORDER BY sequence DESC LIMIT 1'
    ), {'sd': sd}).fetchone()
    if row:
        print('Freeze:', row.recommendation, 'ev=', row.ev_estimate, 'at', row.created_at)
    else:
        print('No freeze for', sd, '-- check job2 logs')
"

# 3. API health
curl -s https://<WNBA_API_BASE>/healthz
curl -s https://<WNBA_API_BASE>/watchdog/today | python3 -m json.tool | head -40
```

## Procedure: job2 did not freeze

1. Check the job2 Railway logs for the failed run.
2. Check `job_runs` in Postgres for the last job2 entry:

```sh
uv run --package wnba-oracle python -c "
from wnba_oracle.db.engine import get_engine
from sqlalchemy import text
engine = get_engine()
with engine.connect() as conn:
    rows = conn.execute(text(
        'SELECT job_name, started_at, finished_at, status, error_summary FROM job_runs ORDER BY started_at DESC LIMIT 5'
    )).fetchall()
    for r in rows:
        print(r)
"
```

3. If the Redis lease is stuck (job2 exited before releasing), check the
   Redis TTL. The lease has a bounded TTL and will expire automatically.
   Do not flush Redis manually unless the TTL is confirmed stuck and the
   contest has not locked.

4. Manual re-fire after diagnosing the cause (not before):

```sh
uv run --package wnba-oracle python scripts/manual_fire.py --job job2 --dry-run
# After reviewing dry-run output:
uv run --package wnba-oracle python scripts/manual_fire.py --job job2
```

## Procedure: pool is empty after job1

1. Check `slate_meta` to confirm job1 saw the slate:

```sh
uv run --package wnba-oracle python -c "
from wnba_oracle.common.clock import slate_date
from wnba_oracle.db.engine import get_engine
from sqlalchemy import text
sd = slate_date()
engine = get_engine()
with engine.connect() as conn:
    row = conn.execute(text(
        'SELECT * FROM slate_meta WHERE slate_date = :sd'
    ), {'sd': sd}).fetchone()
    print(row)
"
```

2. If `slate_meta` is empty, Real Sports may not have published the contest
   yet, or the scraper session has expired. Check the Real Sports provider
   status:

```sh
uv run --package wnba-oracle python scripts/probe_realsports.py --offline-check
```

3. If the session has expired, follow the session recovery procedure in
   `wnba-oracle/STATUS.md` (Ops > Incident history). Session files require
   mode 0600. Do not commit them.

## Procedure: API returns 404 for /lineup/{date}

Before the freeze, `/lineup/{date}` returns 404 by design. The frontend
shows a countdown using `/slate/{date}`. After job2 freezes, the endpoint
becomes available. If it returns 404 after the expected freeze time:

1. Confirm the freeze exists in Postgres (see game day checklist step 2).
2. Confirm the API service is reading from the correct DATABASE_URL.
3. Check the API health endpoint and Railway service logs.

## Procedure: rotate a Railway environment variable

```sh
railway variables set <KEY>=<VALUE> \
  --service <service-name> \
  --environment production
```

Variable changes take effect on the next service restart or deploy. For
cron services, the next scheduled run picks up the new value automatically.

Rollback: set the previous value. No redeploy needed for pure-env-var
knob changes (Settings reads from the process environment at startup).

## Procedure: promote a new model artifact

1. Train offline (see corpus-status skill).
2. Validate the new artifact:

```sh
uv run --package wnba-oracle python scripts/validate_minutes_model.py \
  --artifact models/<artifact>.pkl
uv run --package wnba-oracle python scripts/compare_artifacts.py \
  --new models/<artifact>.pkl
```

3. Upload the artifact to the Railway volume or object store (per the
   mechanism in STATUS.md > Production > Model artifact).
4. Update `STATUS.md`: new artifact filename, SHA, date, commit SHA.
5. Open a PR. `make test-contract` must pass.
6. After merging, set `WNBA_ORACLE_MODEL_ARTIFACT_SHA=<new-sha>` on all
   Railway services that load the model (job2, api).
7. Retain the previous deployment for rollback. Do not delete the old
   artifact until the new one has survived 3+ live slates.

## Procedure: pause picks

Set both Railway env vars on all services (api, job1, job1-late, job2):

```sh
railway variables set PICKS_PAUSE_START=<YYYY-MM-DD> PICKS_PAUSE_END=<YYYY-MM-DD> \
  --service <service> --environment production
```

The API `/slate/{date}` will return `picks_paused: true` and `resumes_on`
for any date in [start, end]. dayclose and backfill are unaffected.

To clear the pause: set both vars to empty string.

## Auth and capability checks

```sh
# From monorepo root
scripts/auth-check wnba-oracle --offline
scripts/auth-check wnba-oracle --live
```

These commands must not print secrets, tokens, or connection URLs.

## What not to do

- Do not flush Redis during a live contest window; the distributed lease
  protects against double-freeze.
- Do not delete or rewrite rows in `frozen_lineups`. It is append-only.
- Do not run training scripts on a Railway job2 service.
- Do not set `DATABASE_URL` to the production connection string in local
  scripts that write; use `DATABASE_PUBLIC_URL` (read) or a local DB.
- Do not copy Railway credentials into the repo or into this document.

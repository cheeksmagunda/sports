# Sports Oracle: Portfolio Overview

Generated reference doc. Purpose: give any session, on any surface, full
structural context on first read, i.e. what exists and what it does. It does
**not** cover auth, credentials, process, or operational status; those live
in root `AGENTS.md` (portfolio rules + sync process) and each app's
`AGENTS.md` / `STATUS.md` (domain rules + live state), which this doc points
to rather than duplicates. For an exhaustive per-file listing, see `FILES.md`
(generated, not hand-maintained).

## What this is

A Python monorepo: one domain-free shared platform (`oracle-core`) plus four
independent sport applications (`wnba-oracle`, `nfl-oracle`, `nba-oracle`,
`nhl-oracle`). Each app owns its models, features, strategy, scoring,
calendar, and provider adapters. Dependency direction is one-way: sport
application to `oracle-core`. Sport apps never import each other or
`oracle-core` domain code back.

## oracle-core (`packages/oracle-core/src/oracle_core/`): 14 files, flat

Domain-free technical infrastructure shared by every app:

| File | Purpose |
|---|---|
| `artifacts.py`, `dossier.py` | Artifact/snapshot handling |
| `cache.py` | Caching primitives |
| `config.py` | Configuration loading |
| `dayclose.py` | Generic day-close sweep orchestration (grade a target day, retry a bounded catch-up window, isolate one day's failure), shared by every sport's day-close job |
| `http.py` | HTTP transport |
| `jobs.py` | Job execution / scheduling primitives |
| `logging.py`, `redaction.py` | Structured logging with secret redaction |
| `service.py` | Service scaffolding (e.g. FastAPI wiring) |
| `storage.py` | Persistence primitives |
| `testing.py` | Shared test helpers/fakes |

## wnba-oracle: production, most mature app

The only app with a live production deployment (Railway: api, two cron
workers, dayclose, backfill-enrichment, frontend, redis, postgres). Has a
real frontend build (`frontend/`, Vite + React).

`src/wnba_oracle/` subpackages (file counts):

| Subpackage | Files | Purpose |
|---|---|---|
| `scheduler/` | 24 | Job scheduling, the largest subpackage |
| `features/`, `ingest/` | 10 each | Feature engineering; provider data ingest |
| `picker/`, `predict/` | 8 each | Lineup selection; inference |
| `common/` | 7 | Shared app-local utilities |
| `api/`, `eval/`, `modeling/`, `train/` | 6 each | HTTP API; model evaluation; model definitions; training |
| `assurance/`, `db/` | 3 each | Data/model assurance checks; DB access |
| `audit/`, `schemas/` | 2 each | Audit trail; schema definitions |
| `monitoring/` | 1 | Monitoring hooks |

## nfl-oracle: actively developed, pre-production-proven

No live production traffic verified yet as of this doc; day-close/backup
infra recently went live. Frontend is a single static `index.html` (no
build pipeline). `src/nfl_oracle/` subpackages (file counts):

| Subpackage | Files | Purpose |
|---|---|---|
| `strategy/` | 16 | Five-card legality gates, clocks, scoring algebra, lineup optimizer, dry-run |
| `recommendations/` | 14 | The live pipeline: `pipeline.py` (prepare/publish/lock), `optimizer.py`, `provider.py` (read-only collection), `store.py`, `dayclose.py`, `grading.py`, `model.py`, CLI |
| `baselines/` | 10 | Value-prediction baselines: ridge, priors, walk-forward eval, CLI |
| `contests/` | 9 | Real-contest archive parsing (scoring-law verification) |
| `data/`, `ingest/` | 7 each | Coverage/catalog helpers; Corpus G (raw game data) ingest |
| `identity/` | 6 | Player identity resolution, alias/dedup |
| `valuelaw/` | 5 | Reverse-engineered box-score to contest-value model (the "solved" half of prediction) |
| `providers/` | 5 | Provider adapters/stubs |
| `features/`, `calendar/` | 4 each | Feature schema/rows; season/week resolution |
| `service/`, `replay/`, `labels/`, `common/` | 3 each | Research API routes; historical contest replay harness; value-label schema; shared utilities |

Also: `scripts/` (14 files, CLIs/ops scripts), `frontend/` (3 files, static
page), `config/`, `data/` (catalogs, gitignored raw payloads), `artifacts/`
(checked-in sample reports).

## nba-oracle: scaffold only

`src/nba_oracle/__init__.py` and nothing else. Wired into root test/lint/
typecheck/build/boundary checks; no provider, model, or scheduling code
exists yet.

## nhl-oracle: early scaffold, pre-provider

`src/nhl_oracle/` subpackages: `contract/` (3, candidate contest-format
shape + audit checklist), `identity/` (3), `ingest/` (2, corpus store +
provenance), `scheduler/` (2, freeze-cycle step ordering). All exercised
only against synthetic fixtures; no live provider contacted, no credential
created.

## Root-level files

`README.md`, `AGENTS.md` (+ `CLAUDE.md` symlink): portfolio purpose and
agent rules. `CONTRIBUTING.md`, `ENTRY_POINTS.md`, `APPLICATION_GUIDE.md`,
`BENCHMARK_TASK.md`: process/onboarding docs (not duplicated here).
`Makefile`, `pyproject.toml`, `uv.lock`: build/dependency root.
`scripts/` (11 files): portfolio-wide tooling (auth-check, write-path-check,
boundary/application checks, secret helpers). `.github/workflows/` (15):
CI/CD. `.devcontainer/`: Codespace environment definition. `drive/` (29
files): a self-documented scratch space for task briefs/handoffs; see its
own `drive/README.md` for conventions.

## Keeping this synchronized

`FILES.md` is regenerated by `scripts/generate_file_manifest.py` (extracts
each Python file's first docstring line / each Markdown file's H1); it is
never hand-edited. Run `scripts/generate_file_manifest.py --check` to verify
it is current; run it without `--check` to rewrite it. This document
(`OVERVIEW.md`) is hand-maintained prose; treat a new top-level subpackage or
app as a signal to update it. Neither file covers auth, credentials, or
operational status; see `AGENTS.md` and each app's `STATUS.md` for that.

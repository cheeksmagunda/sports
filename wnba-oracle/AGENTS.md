# WNBA Oracle Instructions

These are the stable operating rules for the WNBA application. Root
`../AGENTS.md` is authoritative for portfolio boundaries, security, and shared
infrastructure. Read both files, this project's `README.md`, and `STATUS.md`
before acting. Reverify mutable facts in `STATUS.md` against code and live
authoritative sources before production work.

## Purpose and ownership

WNBA Oracle collects the available Real Sports WNBA pool and pre-tip signals,
predicts player distributions, optimizes a five-player lineup, freezes the
lineup before the applicable lock, and serves read-only slate and lineup data.

WNBA owns all league models, feature engineering, strategy, scoring, calendars,
provider adapters, provider payloads, database schemas, migrations, job names,
schedules, pause rules, freeze rules, API routers, and recovery procedures.
Only provider-neutral technical primitives belong in `oracle-core`.

Do not change frontend source, dependencies, styling, components, tests, or
build configuration during backend work. If another contributor is working on
the frontend, import their final commit mechanically and verify tree identity.

## Exact local commands

Run workspace commands from the monorepo root:

```sh
uv sync --all-packages --all-extras
make test-core
make test-wnba
make test-contract
make lint
make typecheck
make build
make check-boundaries
```

Run WNBA commands from this directory:

```sh
make install
make test
make test-contract
make lint
make typecheck
make fmt
make dev
make migrate
make determinism-check
```

`make test` deliberately runs `uv run --package wnba-oracle --extra dev
python -m pytest tests/ -q`. Do not replace it with bare `uv run pytest`, which
can omit project dependencies in a workspace.

Commands normally use the existing process environment and native CLI sessions.
Run capability checks from the monorepo root:

```sh
scripts/auth-check wnba-oracle --offline
scripts/auth-check wnba-oracle --live
```

If an operator chose optional encrypted local storage, inject only those values
into the child process:

```sh
scripts/with-secrets wnba-oracle -- make dev
scripts/with-secrets wnba-oracle -- ../scripts/auth-check wnba-oracle --live
```

## Verification bar

- Backend code is not complete until the relevant focused tests pass, followed
  by `make test`, `make lint`, and `make typecheck` from this directory.
- Prediction, feature, model-loading, optimizer, or freeze changes also require
  `make test-contract` and a compatibility check against the served artifact.
- Migration changes require an upgrade from an empty PostgreSQL database and an
  upgrade against a representative existing schema. Preserve table names, row
  mappings, and application-owned migrations.
- API changes require route, response-shape, and OpenAPI compatibility tests.
- Workspace or packaging changes require root package builds, import-boundary
  checks, and backend container smoke tests for the API and every cron role.
- Operational scripts require failure-path tests and value-free logs. Production
  changes require live verification after each service and a retained previous
  deployment for rollback.

## Domain and data invariants

- Preserve the five-player draft and committed slot order. Never reorder a
  frozen lineup using realized outcomes.
- `frozen_lineups` is append-only audit history. A re-freeze appends a new
  sequence and must never delete or rewrite earlier freezes.
- Freeze and late re-freeze gates are business rules owned here. Fail closed
  when lock or game-start eligibility cannot be established.
- Canonical runtime data is PostgreSQL. Redis coordinates caches and leases but
  is not the durable source of truth.
- The gamelog corpus and label corpus have different grains and identifiers.
  Do not join or substitute them without an explicit WNBA-owned identity map.
- Domain tables, SQL migrations, provider row mappings, artifact formats, CLI
  names, API paths, and existing environment variable names are compatibility
  boundaries.
- Keep slate-calendar and timezone decisions local. Inject clocks in tests and
  cover UTC and WNBA slate-date boundaries.

## Configuration and secrets

- Runtime configuration comes only from the process environment. Do not load or
  parse `.env`, `.envrc`, `.claude/settings.local.json`, or
  `.claude/credentials.env`.
- Variable names and purposes are declared without values in `.env.example`.
  SOPS files are optional local at-rest storage, not a runtime requirement.
  Native `gh` and Railway CLI sessions stay in their native credential stores.
  Do not duplicate them in SOPS. Separately scoped HTTP automation credentials
  come from the process environment.
- Backend provider credentials, database URLs, Redis URLs, webhook URLs, and
  derived Real Sports sessions are secrets. Never print them, include them in
  arguments, or place them in a URL visible to logs or process listings.
- Frontend login passwords stay only in iCloud Passwords. Do not copy them into
  SOPS, environment variables, browser scripts, agent configuration, or chat.
- Standard `gh` and Railway CLI logins are valid ordinary interfaces. The
  Railway GraphQL helper uses `RAILWAY_WORKSPACE_TOKEN` from the environment.
  Never copy that workspace value into `RAILWAY_TOKEN`. A deliberately scoped
  Railway project token may use `RAILWAY_TOKEN` for this application.

## Providers

- Provider URLs, authentication, anti-bot constraints, retries, parsing,
  contracts, rate limits, and fallback behavior remain in this application.
- Provider requests must use bounded timeouts and retries, honor bounded
  `Retry-After`, and redact sensitive headers, query values, URLs, and exception
  text.
- Real Sports derived storage state is a secret. Write
  `scraper/storage_state.json` atomically with mode `0600`; never commit it.
- Real Sports scripted login is known to be rejected. Session recovery requires
  the operator to sign in using an ordinary interactive browser and iCloud
  Autofill where applicable, then export the derived storage state without
  displaying it. Browser automation or MCP may assist but cannot be the only
  documented path.
- Do not silently turn provider authentication failures into successful jobs.
  Use explicit skipped, degraded, retryable-failure, or terminal-failure status.

## Jobs and production operations

- Job names, role guards, schedules, pause windows, preconditions, and
  watchdog semantics remain WNBA-owned. `WNBA_CRON_ROLE` must match the selected
  job in production.
- A successful exit means required durable work completed. Optional provider
  degradation may be reported as degraded, but database, freeze, role, or
  artifact-integrity failures must return nonzero.
- Use structured start, completion, and failure events. Watchdog and scheduled
  guards must evaluate the current expected run window, not stale deployments
  or logs.
- Use `scripts/rwgql.sh` for scripted Railway GraphQL and standard Railway CLI
  login for supported interactive operations. Send GraphQL variables on
  standard input with `--variables-stdin`; never put secret values in arguments.
- Repoint Railway services sequentially: API, job1, job1-late, job2, day-close,
  backfill, automation, then frontend source only after its final commit is
  imported. Verify each service before continuing and retain rollback.
- Never repoint a live cron to the backfill role. Never mutate billing, delete a
  service or database, rotate a credential, or alter a schedule without the
  authority supplied by the task.

## Incidents and recovery

- Diagnose with code, current API responses, database facts, Railway deployment
  state and logs, then `STATUS.md`. Do not infer health from a stale schedule or
  deployment record.
- API and guard checks may use HTTPS. Database verification uses ordinary
  SQLAlchemy, PostgreSQL, or documented CLI access when available. No operation
  may require a desktop connector.
- Real Sports 401 responses across authenticated endpoints indicate a stale or
  invalid derived session. Escalate for interactive reseeding; do not attempt a
  scripted password login.
- A cron redeploy re-arms its schedule but does not replay a missed run. Any
  catch-up action must be scoped, reversible, and followed by restoration and
  verification.
- Production model SHA validation is fail-closed. Preserve the previous model
  and deployment until a complete game-day cycle, day-close, backup, watchdog,
  and scheduled guard cycle have succeeded.

## Documentation

- `README.md` explains the stable application shape and local entry points.
- `STATUS.md` contains mutable artifacts, commits, service identifiers,
  schedules, incidents, measurements, and known production gaps.
- Keep decision rationale in code, tests, and commits. Do not recreate handoff,
  results, needs-agent, or other markdown ledgers.

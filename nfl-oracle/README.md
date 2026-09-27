# nfl-oracle

Real Sports NFL research application. Current track: Corpus G (historical
games/box/play archive with Real `value` labels) and honest coverage audits.

Current scope includes read-only ingest, redacted persistence, the gated
recommendation and freeze/grade pipeline, and Railway-hosted operations.
Contest submission and live contest entry remain hard-forbidden by policy.

## Connection surfaces

Use root `../ENTRY_POINTS.md` for the portfolio-wide Codespace, agent, auth,
and cloud project rules. For NFL work, open or rejoin the repo's GitHub
Codespace, read root `../AGENTS.md`, this app's `AGENTS.md`, this `README.md`,
and `STATUS.md`, then run from the monorepo root:

```sh
make test-app APP=nfl-oracle
scripts/auth-check nfl-oracle --offline
```

Railway state is NFL-owned and recorded in `STATUS.md`; current Slice 1 work is
read-only and does not authorize contest submission, production secret
injection, or standing per-agent PATs. Use native `gh` and Railway sessions in
the Codespace or an operator-authorized one-session login only. Cloud projects
must include the root snapshot bundle plus `nfl-oracle/AGENTS.md`,
`nfl-oracle/README.md`, and `nfl-oracle/STATUS.md`, then verify against live
`main` before material work.

## Auth (headers_or_capture / storage_state)

Reuse the WNBA-derived Real Sports session pattern without importing WNBA
domain code. Live calls go through `nfl_oracle.ingest.realsports.headers_or_capture`:

1. Prefer a fresh `request_token_cache.json` under `nfl-oracle/scraper/` (mode 0600).
2. Otherwise capture live `real-request-token` / `real-auth-info` headers with
   Playwright using a private `storage_state.json`.
3. Call `https://web.realapp.com` read-only.

`scripts/auth-check nfl-oracle --live` reports Real Sports session presence
and structure validity, value-free, the same way it reports GitHub and
Railway liveness. It is a fast, browser-free structure check by design: the
operator-seeded session is durable and not assumed to expire on a schedule,
so this check never launches a browser or calls the provider. For a deeper,
live verification, follow `wnba-oracle/scripts/probe_realsports.py`'s pattern
(Playwright reload against realsports.io) rather than folding that into the
routine check.

Environment (see `.env.example`):

| Variable | Purpose |
| --- | --- |
| `NFL_REALSPORTS_STORAGE_STATE` | Absolute path to a private Playwright storage state file |
| `REALSPORTS_STORAGE_STATE_PATH` | Alias for the same path |
| `REALSPORTS_STORAGE_STATE_B64GZ` | Base64(gzip(storage_state.json)) for ephemeral bootstrap (CI/staging) |
| `REALSPORTS_TOKEN_CACHE_PATH` / `NFL_REALSPORTS_TOKEN_CACHE` | Optional token cache path override |
| `NFL_ORACLE_SCRAPER_DIR` | Override the private `scraper/` directory |
| `NFL_DEVICE_UUID` | Device UUID used when harvesting Real Sports headers (`realsports.py`) |
| `NFL_DEVICE_NAME` | Device name used when harvesting headers (default `nfl-oracle-dev-01`) |

Code reads `NFL_DEVICE_UUID` / `NFL_DEVICE_NAME` (with optional `WNBA_DEVICE_*`
fallbacks). The legacy `NFL_REALSPORTS_DEVICE_*` names were never read and were
removed from Railway on 2026-09-19 (#239).

Default local storage path: `nfl-oracle/scraper/storage_state.json`.
Never commit `scraper/`, cookies, tokens, or payloads containing `userId`.

Seed from `REALSPORTS_STORAGE_STATE_B64GZ`:

```sh
uv run --package nfl-oracle python nfl-oracle/scripts/seed_storage_state.py
```

NFL does not independently capture its own Real Sports session; it is a copy
of the one portfolio-wide credential root `AGENTS.md` defines. `nfl-oracle`'s
Railway copy (`nfl-oracle-worker`) is deliberately unsealed (not the
historical default) so it can be hash-compared against the canonical value
with `railway run --service nfl-oracle-worker`; compare by `sha256[:8]`,
never by printing values.

If NFL ever needs its own independently-captured session (a separate Real
Sports account, for example), open a headed browser on an operator machine and
sign in normally (password manager/autofill is fine):

```sh
uv run --package nfl-oracle python nfl-oracle/scripts/capture_storage_state.py
```

Press Enter in the terminal after the page is visibly signed in. The helper
writes `nfl-oracle/scraper/storage_state.json` with mode `0600`; it never prints
or uploads the session. The resulting file can be compressed and base64
encoded for a Railway variable:

```sh
gzip -c nfl-oracle/scraper/storage_state.json | base64 | pbcopy
```

Paste that clipboard value into Railway's `REALSPORTS_STORAGE_STATE_B64GZ`
variable for the worker service only. Do not paste it into chat, commit it,
or set it on the read-only API service. Scripted login is rejected by the
provider regardless of path; this is always an ordinary interactive browser
sign-in.

## Train vs live clock / config boundaries

Per the NFL strategy playbook (training/live clocks and leakage blacklist):

- **Training / research**: may attach post-game Real `value`, boxes, and plays as
  **labels** after they are finalized. Fit only on earlier available records with
  matured labels; hold out contests that share games in the evaluation block.
- **Live / prospective decisions**: use only features with
  `source_available_at` and `captured_at` ≤ `decision_at` (pre-lock). Same-slate
  final Real value, plays, boxes, snap counts, TDs, bonus, ranks, or ownership
  backdated to pre-lock are blacklisted as features.
- This package does **not** implement contest submission or entry. Capture-only /
  shadow modes come later under separate authorization.

### Clock fields on Corpus G artifacts

Persisted on provenance sidecars and `manifest.json` (historical backfill sets
`decision_at` to null):

| Field | Applies to | Meaning |
|---|---|---|
| `event_time` | every game artifact | Kickoff / event time (`game.dateTime`) |
| `source_available_at` | every game artifact | Provider finalization clock when known (`postProcessedAt` → `gameEndDateTime` → `closedAt`); null on older seasons rather than inventing availability |
| `captured_at` | every artifact | When nfl-oracle fetched and wrote the redacted payload |
| `decision_at` | live decision snapshots only | Pre-lock decision wall-clock; null on Corpus G research backfill |

Live features require `source_available_at` and `captured_at` ≤ `decision_at`.

## Corpus G

Routes:

- `GET /games/{game_id}/sport/nfl/stats`
- `GET /games/{game_id}/sport/nfl/players`
- `GET /games/{game_id}/sport/nfl/feed?version=2&view=all&viewFrame=default`

Payloads are redacted (no `userId` / `user`) and stored under
`data/raw/corpus_g/{season}/{game_id}/` with sha256 provenance sidecars.
Coverage and resume cursors live under `data/catalog/` (gitignored except seed
`season_game_ids.json`).

## First-season proof

```sh
# from monorepo root, with storage_state available
uv run --package nfl-oracle nfl-corpus-g-backfill --season 2002 --game-ids 126323
```

## Real `value` labels + walk-forward baselines (shadow)

Corpus G `playerBoxScores[].value` is treated as a **train/research label** after
finalization. Same-slate finals are blacklisted as live features. Schema fields
and train/live clock boundaries live in `nfl_oracle.labels.schema` (also printed
by the CLI).

Offline baselines (no network, no contest entry):

- `global_mean`: historical mean Real value from earlier seasons
- `position_mean` / `position_median`: per-position priors with global fallback
- optional `player_mean` / `feature_ridge`: player priors or leakage-safe ridge on
  live_ok prior features (stdlib only; not in the default method set)

Walk-forward evaluation is season-based: train on seasons strictly earlier than
the held-out season, then score MAE / RMSE / bias on the held-out anchors.

```sh
# schema only
uv run --package nfl-oracle nfl-value-baselines --schema-only

# fixtures (CI-safe)
uv run --package nfl-oracle nfl-value-baselines \
  --root nfl-oracle/tests/fixtures/value_labels --json

# local Corpus G raw root (gitignored payloads; operator machine only)
uv run --package nfl-oracle nfl-value-baselines --json

# baselines vs feature_ridge eval report → artifacts/ (sample checked in)
make -C nfl-oracle walk-forward-report
# or: uv run --package nfl-oracle nfl-walk-forward-report
```

See [`artifacts/walk_forward_fixture_sample.md`](artifacts/walk_forward_fixture_sample.md)
for a small fixture-scale comparison (observation only; not contest decision value).

### Production-pipeline backtest (issue #280)

`nfl_oracle.replay.production_backtest` replays the real production path
(`fit_model` over `attach_enrichment`/`enrich_historical_rows`, then `predict`
and the production `optimize`) walk-forward over finalized Corpus G games and
reports the zero-boost capture ratio (our realized score / hindsight-best score
over the same candidate pool and slots). Every row the model or the prior bank
sees must be final strictly before the slate cutoff; `LeakageError` fails the
run otherwise. Training uses the wall clock with a data cutoff, because Corpus G
and nflverse capture clocks are retrospective; context is
`retrospective_reconstructed`, never prospective proof.

```sh
# needs local data/raw/corpus_g plus a saved nflverse ContextSnapshot JSON
make -C nfl-oracle production-backtest CONTEXT_SNAPSHOT=/path/to/context.json \
  BACKTEST_ARGS="--grouping game --out /tmp/production_backtest.json"
```

`--grouping game` matches the naive per-game baseline in
`nfl_oracle.replay.backtest`; `--grouping day` groups games by US/Eastern date.
Current results live in `STATUS.md`.

## Local commands

```sh
make test
make lint
make typecheck
make research-smoke          # offline TestClient research suite subset
make research-smoke SMOKE_ARGS=--json
```

`make research-smoke` runs `scripts/research_client_smoke.py` against
`tests/fixtures/offline_research` via FastAPI TestClient (no network). It asserts
schema/catalog/coverage/schedule/identity routes, shadow preview + rank-orderings,
and **hard-deny** entry gates (`package_submit_hard_deny` + unverified provider
contract). Strip live DB/redis env like `make test`. Observation only: never
enables contest entry.


From monorepo root:

```sh
make test-app APP=nfl-oracle
make check-applications
make check-boundaries
```



## Data / strategy / feature scaffolds (observation only)

- `nfl_oracle.data`: catalog / coverage / paths helpers
- `nfl_oracle.strategy`: pre-lock clock gates, five-card structural checks, shadow snapshots
- `nfl_oracle.features`: FeatureSpec registry (`nfl_oracle.features.schema`)
- `make strategy-schema` / `uv run --package nfl-oracle nfl-strategy-schema --schema-only`
- Research HTTP scaffold: `nfl_oracle.service.create_app` / `nfl-research-serve`
  (`make research-serve`; schemas incl. scoring, catalog, coverage + schedule
  summary/census, identity density, shadow preview + rank-orderings, entry
  gates, live-ok features, provider rules-offline, status; contest entry always false)
- Strategy helpers: 120 five-card orderings + readiness→posture mapping
- Production container: `Dockerfile.production` builds one NFL image for the
  read-only API and the write-capable worker. `railway.toml` only selects the
  Docker build; it does not create services or change Railway state.

## Production container runbook

Build from the monorepo root with `docker build -f
nfl-oracle/Dockerfile.production -t nfl-oracle:production .`. The image has
the Playwright Chromium runtime needed for the worker's derived-session refresh,
but it contains no provider session, credentials, or mounted-volume data. It
bakes only the slim public schedule CSV and its attribution README under
`/opt/nfl-oracle/bootstrap/schedule/`, outside the worker data volume. Worker,
train, and week-close starts copy that CSV into an empty volume without
overwriting an existing volume schedule.

Run the API service with:

```sh
nfl-pipeline serve --host 0.0.0.0 --port "${PORT:-8000}"
```

The API process uses `NFL_DATABASE_URL` in a PostgreSQL read-only session and
does not run migrations. Its health endpoint is `/health`. Run the worker as a
separate service with `nfl-pipeline worker`; only that role receives the
write-capable database credentials and provider session environment. Run
`nfl-pipeline migrate` as an explicit one-shot release step before either
service starts. A worker restart is bounded by the worker command's retry and
backoff policy, and failure must leave the prior frozen recommendation intact.

Once a slate has frozen successfully, the worker treats that published lineup
as terminal and does not re-freeze the same day on later poll cycles. A
deliberate operator re-freeze still exists via
`nfl-pipeline worker --allow-refreeze`; ordinary scheduled runs should never
replace an already-published lineup.

Deadline alerting is GitHub Actions-based, not Railway-hosted:
`.github/workflows/nfl-t40-watchdog.yml` polls every 15 minutes inside NFL
kickoff windows (UTC crons in the workflow), combines the
public nflverse schedule's kickoff time with `RecommendationStore` freeze/run
state, and opens or updates one `nfl-ops-guard` issue if no freeze exists by
the post-T-40 grace deadline. It needs only `NFL_DATABASE_URL` and
`NFL_PG_SSL_ROOT_CERT`; no Real Sports session is required.

The repeatable local image check is `make -C nfl-oracle
docker-production-smoke`. It builds the image and invokes `nfl-pipeline
--help` without a database or secret. No command in this runbook submits a
contest entry.

The PostgreSQL storage check is `make -C nfl-oracle postgres-store-smoke`. It
starts a temporary local `postgres:16-alpine` container on a random host port,
runs the explicit migration, verifies the append-only trigger, exports and
restores freezes, run records, and artifacts, then removes the temporary
container. It does not connect to Railway or any other database.

## Codespace daily ops (planned)

Codespaces is the long-term home for every app's daily processes (NFL is the
first concrete slice). The Codespace Railway CLI uses the account/workspace
credential `RAILWAY_API_TOKEN`; the scoped `RAILWAY_TOKEN` is reserved for
explicit GitHub Actions repair paths. Full checklist lives in `STATUS.md`.
Shadow only: Corpus G coverage refresh → label/baseline recompute → status
artifact; no contest entry; no recreate-blind Codespace; device secrets are
`NFL_DEVICE_UUID` / `NFL_DEVICE_NAME` only (never git).

# nfl-oracle

Real Sports NFL research application. Current track: Corpus G (historical
games/box/play archive with Real `value` labels) and honest coverage audits.

Slice 1 scope is read-only ingest + redacted persistence. Contest submission,
live entry, and Railway production secrets are explicitly out of scope here.

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
fallbacks). It does **not** read `NFL_REALSPORTS_DEVICE_UUID` /
`NFL_REALSPORTS_DEVICE_NAME`. Those legacy names may still exist as harmless
placeholders on Railway project `nfl-oracle-staging` / service `nfl-oracle`;
the additive correct names are what the package uses.

Default local storage path: `nfl-oracle/scraper/storage_state.json`.
Never commit `scraper/`, cookies, tokens, or payloads containing `userId`.

Seed from `REALSPORTS_STORAGE_STATE_B64GZ`:

```sh
uv run --package nfl-oracle python nfl-oracle/scripts/seed_storage_state.py
```

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
```

## Local commands

```sh
make test
make lint
make typecheck
```

From monorepo root:

```sh
make test-app APP=nfl-oracle
make check-applications
make check-boundaries
```



## Data / strategy / feature scaffolds (observation only)

- `nfl_oracle.data` — catalog / coverage / paths helpers
- `nfl_oracle.strategy` — pre-lock clock gates, five-card structural checks, shadow snapshots
- `nfl_oracle.features` — FeatureSpec registry (`nfl_oracle.features.schema`)
- `make strategy-schema` / `uv run --package nfl-oracle nfl-strategy-schema --schema-only`
- Research HTTP scaffold: `nfl_oracle.service.create_app` (schemas + catalog; no entry)

## Codespace daily ops (planned)

**HOLD** until Codespaces `RAILWAY_TOKEN` is confirmed. Org-wide default:
Codespaces is the long-term home for every app's daily processes (NFL is the
first concrete slice). Full checklist lives in `STATUS.md`. Shadow only: Corpus G
coverage refresh → label/baseline recompute → status artifact; no contest entry;
no recreate-blind Codespace; device secrets are `NFL_DEVICE_UUID` /
`NFL_DEVICE_NAME` only (never git).

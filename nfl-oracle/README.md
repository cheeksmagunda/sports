# nfl-oracle

Real Sports NFL research application. Current track: Corpus G (historical
games/box/play archive with Real `value` labels) and honest coverage audits.

Slice 1 scope is read-only ingest + redacted persistence. Contest submission,
live entry, and Railway production secrets are explicitly out of scope here.

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

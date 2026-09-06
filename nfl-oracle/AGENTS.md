# NFL Oracle agent instructions

Read the repository root `AGENTS.md` first. This file adds NFL-only rules and
does not weaken the portfolio contract.

## Purpose and ownership

NFL Oracle is an independent application for Real Sports NFL research. Near-term
scope is read-only Corpus G ingest (games, boxes, plays, player-game
performances), redacted persistence with provenance, coverage tracking, and
later walk-forward five-card baselines.

NFL owns its calendar, identity map, feature schema, model policy, contest
scoring, payout curve, provider adapters, and operational gates. Do not import
`wnba_oracle` domain packages (`picker`, `features`, `modeling`, `predict`, or
WNBA schemas). Shared work belongs in `oracle-core` only when provider-neutral.

## Exact local commands

From the monorepo root:

```sh
make setup
make check-applications
make check-boundaries
make test-app APP=nfl-oracle
```

From this directory:

```sh
make test
make lint
make typecheck
```

Optional secret injection for live Real Sports calls:

```sh
scripts/with-secrets wnba-oracle -- uv run --package nfl-oracle nfl-corpus-g-backfill --season 2002 --game-ids 126323
```

The WNBA project name is used only because the operator-seeded Real Sports
session currently lives in that SOPS file. NFL does not import WNBA code.

## Verification bar

- Focused unit tests, then `make test` from this directory.
- Live ingest is read-only: never enter contests or mutate provider state.
- Never commit `scraper/`, cookies, tokens, `userId`, or storage_state material.
- Boundary checks must stay green after packaging changes.

## Domain invariants (Corpus G)

- Host: `https://web.realapp.com`
- Sport path segment: `nfl`
- Endpoints: `/games/{id}/sport/nfl/stats`, `/players`, `/feed?version=2&view=all&viewFrame=default`
- Persist redacted JSON with sha256 + provenance; resume by season cursor
- Primary Real label field: `playerBoxScores[].value`
- Corpus C (contests) and five-man policy are out of scope for the first scaffold

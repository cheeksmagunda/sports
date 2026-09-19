# nhl-oracle

NHL Oracle application scaffold.

Current scope is a pre-provider-access scaffold exercised only against
synthetic fixtures: package wiring, boundary-safe layout, verification
targets, a candidate contest contract and audit gates (`contract/`), a
redacted payload provenance store (`ingest/`), an identity map and collision
reconciler (`identity/`), and a freeze-cycle job skeleton (`scheduler/`). No
live NHL provider, model, optimizer, hosted API, frontend, or deployment
exists yet; see `STATUS.md` for current detail.

## Connection surfaces

Use root `../ENTRY_POINTS.md` for the portfolio-wide Codespace, agent, auth,
and cloud project rules. For NHL work, open or rejoin the repo's GitHub
Codespace, read root `../AGENTS.md`, this app's `AGENTS.md`, this `README.md`,
and `STATUS.md`, then run from the monorepo root:

```sh
make test-app APP=nhl-oracle
scripts/auth-check nhl-oracle --offline
```

NHL has no Railway production project yet. Do not create Railway services,
provider credentials, contest entry paths, or per-agent PATs unless a scoped
issue explicitly authorizes that work. Cloud projects must include the root
snapshot bundle plus `nhl-oracle/AGENTS.md`, `nhl-oracle/README.md`, and
`nhl-oracle/STATUS.md`, then verify against live `main` before material work.

## Commands

From this directory:

```sh
make test
make lint
make typecheck
```

From the repository root:

```sh
make test-app APP=nhl-oracle
make check-applications
make check-boundaries
```

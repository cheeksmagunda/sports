# nba-oracle

NBA Oracle application scaffold.

Current scope is infrastructure only: package wiring, boundary-safe layout, and
verification targets. Domain behavior (providers, schemas, models, contests,
and operations) is intentionally not implemented yet.

## Connection surfaces

Use root `../ENTRY_POINTS.md` for the portfolio-wide Codespace, agent, auth,
and cloud project rules. For NBA work, open or rejoin the repo's GitHub
Codespace, read root `../AGENTS.md`, this app's `AGENTS.md`, this `README.md`,
and `STATUS.md`, then run from the monorepo root:

```sh
make test-app APP=nba-oracle
scripts/auth-check nba-oracle --offline
```

NBA has no Railway production project yet. Do not create Railway services,
provider credentials, contest entry paths, or per-agent PATs unless a scoped
issue explicitly authorizes that work. Cloud projects must include the root
snapshot bundle plus `nba-oracle/AGENTS.md`, `nba-oracle/README.md`, and
`nba-oracle/STATUS.md`, then verify against live `main` before material work.

## Commands

From this directory:

```sh
make test
make lint
make typecheck
```

From the repository root:

```sh
make test-app APP=nba-oracle
make check-applications
make check-boundaries
```

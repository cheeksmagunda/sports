# NHL Oracle agent instructions

Read the repository root `AGENTS.md` first. This file adds NHL-only rules and
does not weaken the portfolio contract.

## Purpose and ownership

NHL Oracle is an independent NHL application scaffold. NHL owns its calendar,
identity map, feature schema, model policy, scoring rules, provider adapters,
and operational gates. Do not import domain code from `wnba_oracle`,
`nfl_oracle`, or `nba_oracle`.

Shared work belongs in `oracle-core` only when the interface is provider-neutral
and proven by at least two sports with the same stable contract.

## Exact local commands

From the monorepo root:

```sh
make setup
make check-applications
make check-boundaries
make test-app APP=nhl-oracle
```

From this directory:

```sh
make test
make lint
make typecheck
```

## Verification bar

- Start with focused tests and run `make test`.
- Keep live-provider behavior out of this scaffold until explicitly added.
- Never commit secrets, browser sessions, or token material.

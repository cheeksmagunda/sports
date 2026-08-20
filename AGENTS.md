# Sports Oracle Portfolio Instructions

This private monorepo contains independent league applications and the
provider-neutral technical platform they share. These instructions are the
canonical portfolio rules. A child `AGENTS.md` adds application rules and exact
commands, but cannot weaken this contract.

## Start every task

1. Identify the target application or shared package and the requested
   deliverable. Read this file, then the nearest child `AGENTS.md`, `README.md`,
   and `STATUS.md` before acting.
2. Inspect the working tree and preserve concurrent, unrelated, and uncommitted
   changes. Keep work inside the requested boundary.
3. Separate verified facts from inference. Prefer code, tests, schemas, and live
   authoritative sources over mutable prose. Recheck mutable production facts
   before relying on them.
4. Prefer reversible, scoped actions. Stop for missing authority, destructive or
   irreversible work, or a choice that materially changes the requested scope.

## Portfolio boundaries

- Dependency direction is `league application -> oracle-core`.
- `oracle-core` must not import a league application. League applications must
  not import one another.
- Shared code is domain-free technical infrastructure: configuration,
  redaction, logging, HTTP transport, persistence primitives, job execution,
  service scaffolding, artifact handling, and test helpers.
- Models, features, strategies, scoring, league schemas, calendars, provider
  implementations, provider payloads, and domain endpoints stay in the owning
  application unless a later, explicit portfolio decision promotes a proven
  abstraction.
- The current `oracle-core` extraction is approved platform work. After it,
  prefer keeping a capability local until production evidence and tests show a
  stable provider-neutral interface. This policy does not prohibit future
  sports-level abstractions.
- Frontend and backend ownership are separate. Do not edit frontend source,
  dependencies, tests, styling, or build configuration during backend-only
  work. Preserve a concurrent frontend contributor's changes exactly.

## Engineering and verification

- Read before editing and preserve public behavior unless the task explicitly
  changes it.
- Prefer typed boundaries, explicit dependencies, deterministic behavior,
  bounded retries and timeouts, idempotent operations, atomic writes, and
  structured logs with redaction.
- Keep migrations backward compatible when practical. Production changes need
  a verification step, a rollback path, and a retained previous deployment.
- Tests must cover behavior and failure paths. Run the documented focused
  checks while iterating, then the child project's required test, lint, type,
  contract, package, boundary, and container checks in proportion to risk.
- Never report a check as passing unless it completed successfully against the
  relevant artifact or system. State material checks that could not run.
- Do not commit, push, deploy, mutate production data, alter schedules, create
  credentials, archive repositories, or perform destructive work unless the
  task authorizes that action.
- Use standard punctuation. Do not use Unicode U+2014 in responses or files.

## Portable operations and secrets

- Required operational interfaces are ordinary files, process environment
  variables, shell commands, documented CLIs, and HTTPS APIs.
- MCP servers, desktop automation, browser control, and product-specific
  connectors are optional accelerators. No required workflow may depend on one
  as its only implementation.
- Applications and scripts read configuration from the process environment.
  Do not implicitly load `.env`, `.envrc`, agent settings, or vendor-specific
  credential files.
- Native `gh` and Railway CLI sessions are the canonical authentication for
  those CLIs. Do not copy their stored credentials into repository files or
  duplicate them as local tokens merely to run normal commands. HTTP
  automation receives only the scoped environment credential it requires.
- SOPS and age are an optional at-rest helper for environment-backed values
  that an operator chooses to persist locally. When used, root-common values
  live in `.secrets/common.sops.env` and application values live in
  `<project>/.secrets/local.sops.env`. Both directories use mode `0700`;
  encrypted files use mode `0600` and remain ignored. The age private identity
  stays outside the repository at mode `0600`.
- Commands normally run directly with the existing process environment. When
  optional encrypted files are needed, invoke
  `scripts/with-secrets <project> -- <command>`. An explicitly exported value
  wins over application values, which win over root-common values.
- Use `scripts/auth-check <project> --offline` for concise current-process and
  local capability checks, then `--live` for value-free validation. It does
  not decrypt optional files unless the operator explicitly wraps it with
  `with-secrets`. These commands must not print tokens, passwords, connection
  URLs, response bodies, or other secret values.
- Never pass secrets in command arguments or logs. For a provider that requires
  query authentication, construct the request inside the process and redact
  the URL and errors.
- Frontend login passwords remain exclusively in iCloud Passwords and enter the
  browser through Autofill or user interaction. Never copy them into SOPS,
  environment files, agent settings, scripts, or chat.
- Backend provider credentials and derived browser sessions are application
  secrets. Derived session files require mode `0600`, atomic writes, redaction,
  and the same handling as credentials.

## Documentation and state

- Root documentation owns portfolio purpose, boundaries, and technical
  conventions. Child documentation owns domain behavior and operations.
- Mutable deployments, repository commits, service identifiers, schedules,
  artifact identifiers, incidents, measurements, and production observations
  belong in the child `STATUS.md`.
- Decision rationale belongs in tests, code comments, or commits. Do not create
  competing markdown ledgers.
- Tool-specific instruction shims import canonical instructions and contain no
  independent rules. Root `CLAUDE.md` must contain only `@AGENTS.md`.

# Sports Oracle Portfolio Instructions

You are a brilliant and hard working creative strategy and data sports
analytics product developer for IᎤænnغS, the operator. It is really great
to meet you.

He is working on Sports Oracle, a Python monorepo at
github.com/cheeksmagunda/sports. It contains oracle-core (shared technical
platform) and independent sport applications. Smart, action oriented
programming and natural language outcomes for IᎤænnغS are the priority.

We prioritize state awareness and file synchronization management. The
operator works across many surfaces, so project state is key.

This monorepo contains independent sport applications and the
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
5. Before material work, find or create one GitHub issue with the objective and
   acceptance check. Link the branch, every commit, and the PR to that issue.
    The acting agent handles this bookkeeping. Every work item requires an issue;
    follow `CONTRIBUTING.md` for the repository contribution process.

## Portfolio boundaries

- Dependency direction is `sport application -> oracle-core`.
- `oracle-core` must not import a sport application. Sport applications must
  not import one another.
- Every sport application owns its child `AGENTS.md`, `README.md`, `STATUS.md`,
  optional `skills/`, connector configuration, and permission-scoped runtime
  credentials. Those files and capabilities apply only within that application
  unless explicitly promoted through a portfolio decision.
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
- GitHub login, Copilot, Actions, and Codespaces secrets live in the repo's
  Codespace for sports work. Do not mint per-agent PATs for Claude, Codex,
  Copilot, or Grok.
- Claude, Codex, and Copilot are clients for the Codespace, live checkout, or
  live GitHub repository. They are not separate GitHub credential homes.
- Grok Bot is the only Cursor-based surface. Use Cursor cloud agents on this
  repo or an operator-authorized one-session `gh` login only. Do not copy
  Codespaces credentials into chat, Cursor, or other agents.
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
- Current deployments, active source commits, service identifiers, schedules,
  artifact identifiers, incidents, and production risks belong in the child
  `STATUS.md`. Development progress and history belong in GitHub Issues and PRs.
- Decision rationale belongs in issues, PRs, tests, code comments, or commits.
  Do not create competing markdown ledgers.
- `AGENTS.md` is the only agent-instruction format in this repository. Each
  `CLAUDE.md` is a plain symlink to its sibling `AGENTS.md`, present only
  because Claude Code does not read `AGENTS.md` natively. Do not add any
  other model-specific instruction file or a shim that carries separate
  content.

## Context synchronization

The single source of truth is the `main` branch of `cheeksmagunda/sports`
on GitHub. The GitHub Codespace built from this repository is the canonical
development environment. The operator's laptop checkout stays synchronized
with git. Nothing else is authoritative.

### Access points and sync guarantees

**Live entry points** (read repository directly on every task):
- GitHub Codespaces in a browser, local editor, or mobile-capable GitHub view
- GitHub Copilot CLI, app, GitHub UI, or mobile when attached to this repo or
  Codespace
- Claude Code CLI, Claude app, or Claude web/mobile when attached to this repo
  through a live checkout, Codespace, or GitHub connector
- Codex CLI, app, or web/mobile when attached to this repo through a live
  checkout, Codespace, or GitHub connector
- Grok app, web, mobile, or grokbot when attached to this repo through a live
  checkout, Codespace, or GitHub connector
- GitHub Desktop and other local editors opened on the synchronized checkout

Only call work portfolio-current after the relevant commit is on live `main`.
A dirty or unpushed Codespace is local state, not portfolio state.

**Static-copy entry points** (may be stale; fetch live before acting):
- Claude, Codex, Copilot, and Grok cloud projects or chats that use uploaded
  files, pasted context, exported session files, or knowledge bases instead of
  reading the repository directly
- Local agent session files or mobile chats that were prepared from a prior
  snapshot

### Keeping static snapshots current

Claude, Codex, Copilot, and Grok cloud projects may contain uploaded static
copies of the root instructions and application documents. The canonical
snapshot bundle is root `AGENTS.md`, root `README.md`, root `Makefile`, root
`pyproject.toml`, `.devcontainer/`, `.github/workflows/`, and each
application's `AGENTS.md`, `README.md`, and `STATUS.md`. The root of this
repository has no `STATUS.md`; mutable state belongs to application
`STATUS.md` files. Static copies drift. Before acting on any of them:

1. Fetch the live version from the repository through the GitHub connector
2. Treat the live file as authoritative
3. If a snapshot and the live repository disagree, note the discrepancy
   and follow the repository
4. The operator re-uploads snapshots to all configured Claude, Codex, Copilot,
   and Grok projects when the context freshness workflow flags a change

Sync-critical files: every `AGENTS.md` and `README.md`, every application
`STATUS.md`, plus root `Makefile`, `pyproject.toml`, `.devcontainer/`, and
`.github/workflows/`. When one of these changes on `main`, every agent must
re-read it before related work, and the operator refreshes the uploaded
snapshots. A scheduled workflow opens a tracking issue when these files change
so re-uploads are not forgotten.

### Repository structure for all entry points

All entry points access the same monorepo structure:

- **oracle-core** (`packages/oracle-core/`) — domain-free platform
  shared by all applications
- **wnba-oracle** (`wnba-oracle/`) — WNBA application, owns models,
  features, strategy, scoring, calendar, contests, and provider adapters
- **nfl-oracle** (`nfl-oracle/`) — NFL application, owns models,
  features, strategy, scoring, calendar, contests, and provider adapters
- **nba-oracle** (`nba-oracle/`) — NBA application, owns models,
  features, strategy, scoring, calendar, contests, and provider adapters
- **nhl-oracle** (`nhl-oracle/`) — NHL application, owns models,
  features, strategy, scoring, calendar, contests, and provider adapters
- **Shared commands** — all entry points run the same `make` targets
  from root or app directory

Command compatibility across entry points:

```sh
# All entry points support these from /workspaces/sports root:
make setup                      # Install locked dependencies
make test                       # Run offline tests
make test-core                  # Core-only tests
make test-app APP=wnba-oracle   # WNBA-only tests
make test-app APP=nfl-oracle    # NFL-only tests
make test-app APP=nba-oracle    # NBA-only tests
make test-app APP=nhl-oracle    # NHL-only tests
make lint                       # Ruff check + format
make typecheck                  # mypy across apps
make check-boundaries           # Verify dependency direction
make build                      # Build application images

# App-specific commands from app directory:
cd nfl-oracle && make test      # Run nfl-oracle tests only
cd wnba-oracle && make test     # Run wnba-oracle tests only
cd nba-oracle && make test      # Run nba-oracle tests only
cd nhl-oracle && make test      # Run nhl-oracle tests only
```

Never act on remembered or cached copies of sync-critical files when a
live copy is reachable.

## Pull request autonomy

- The operator never has to approve or merge a pull request through manual
  action. When a PR's required checks are green and the change is within the
  scope the operator authorized, the acting agent merges it. Every access
  point (Copilot CLI, Claude Code, Codex, the Claude GitHub App, and the
  Copilot coding agent) follows this rule identically.
- Merge with squash to keep `main` linear, then delete the branch.
- This autonomy covers only routine, reversible work. Destructive actions,
  production data mutation, schedule changes, and scope-expanding changes
  still stop for explicit operator authorization, per Engineering and
  verification.
- Agents must not leave stale PRs open. If a PR the agent owns cannot merge
  (failing checks, conflicts, review feedback), the agent fixes it, asks
  for help, or closes it with a reason.

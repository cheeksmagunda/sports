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
4. Prefer reversible, scoped actions. Stop only when authority is genuinely
   missing, the write path is broken, a required secret cannot be obtained
   without minting a new credential, or a hard freeze-window serving lock is
   active. Do not re-ask for per-step confirmation inside an already
   authorized campaign (see Operator authorization and agent authority).
5. Before material work, find or create one GitHub issue with the objective and
   acceptance check. Link the branch, every commit, and the PR to that issue.
    The acting agent handles this bookkeeping. Every work item requires an issue;
    follow `CONTRIBUTING.md` for the repository contribution process.
6. Before material work, declare the acting environment and prove the write
   path. Run `make write-path-check` from the repository root. It reports the
   host, checkout, remote, and branch. Inside the Codespace it confirms a
   direct dry-run push to `origin`; from the Mac checkout it confirms an
   authenticated Codespace push route is available through
   `scripts/codespace-push` instead of a direct local push. If neither route
   is available, stop and report the block on the issue. Do not mint a
   per-agent credential and do not keep building behind a credential that
   cannot land the work.
7. Check the canonical Codespace's state (`gh codespace list`) and wake it if
   `Shutdown` (`gh codespace ssh -c <name> -- true` resumes it; postStart then
   runs the health-check and prune on its own). Do this at the start of an
   active work session. There is no scheduled sweep; GitHub's own idle
   timeout and 30-day retention handle Codespaces between sessions.

## End every task

Documentation is not a follow-up step; a change is not done until its
documentation is, and that happens before the PR merges, not after.

1. Update every document the change actually affects before opening or
   updating the PR: the child `STATUS.md` for any current-state fact
   (deployment, schedule, credential, incident, production risk), the child
   `README.md` for any stable-shape change, root `AGENTS.md` when a
   portfolio-wide boundary or credential contract changed. A PR that changes
   behavior without updating the doc that describes it is incomplete, not
   merely undocumented.
2. State each fact exactly once, at the level that owns it. If root
   `AGENTS.md`, `README.md`, or `ENTRY_POINTS.md` already documents
   something, a child file references it, never restates it (see Portable
   operations and secrets and Context synchronization below). Two copies of
   one fact are two chances for it to drift out of sync with each other;
   treat that as a bug to fix, not a style choice, whenever it turns up.
3. Verify a documentation claim against live state before writing it, the
   same discipline as verifying code against tests: check the actual
   Railway/GitHub/API status, not a deployment or build field as a stand-in
   for the application's own recorded outcome, and not a prior session's
   memory of either. Write "unverified" rather than a plausible-sounding
   guess.
4. Regenerate `FILES.md` (`scripts/generate_file_manifest.py`) whenever the
   tracked tree changed, and re-run the touched application's verification
   bar against the state the PR will actually merge, not the state it was
   drafted against.
5. Prefer changes that keep DevOps posture and visibility consistent across
   every application, not just the one directly touched: a credential,
   auth, or push-path change (issue-first tracking, `write-path-check`,
   git/Railway/Real Sports auth, Codespace as the default execution
   environment) is portfolio-wide by nature, so its documentation update is
   too, even when the code change was scoped to one app.

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
- Prefer schema.org types and properties at root / `oracle-core` and other
  shared portfolio contracts for entity linking and JSON-LD interchange
  (`Person`, `SportsTeam`, `SportsOrganization`, `SportsEvent`, `Place`,
  `Role`/`OrganizationRole`, `identifier`/`PropertyValue`, `sameAs`,
  `Observation`, `QuantitativeValue`, `ItemList`). Use IPTC Sport Schema only
  where schema.org is weak for sport-specific participation or statistics.
  Use PROV-O when claims need source/time/process provenance. Never assert
  `sameAs` from a fuzzy name+team match. Sport-specific scoring, contest
  value algebra, and provider payload parsing stay in the owning app.
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
- Commit, push, deploy, mutate production data, alter schedules, or perform
  other production actions when the linked issue or in-session operator
  authorization covers them (see Operator authorization and agent authority).
  Still never mint new credentials, archive repositories, script a Real Sports
  login, or print secret values.
- Use standard punctuation. Do not use Unicode U+2014 in responses or files.

## Operator authorization and agent authority

This section is binding for every client that reads these instructions
(Codespace shells, Cursor / Grok Bot, Claude Code, Codex, Copilot, and cloud
agents attached to this repository).

- An open GitHub issue that lists production actions (Railway deploy or
  restart, model SHA or env knob flip, schema migration, required-check
  change, active_model promotion) is standing authorization for those
  actions. Execute them from the Codespace via the documented helpers
  (`scripts/codespace-push`, `scripts/codespace-railway-env`), with a stated
  rollback on the issue or in STATUS, without asking for a fresh "go" on each
  step.
- In-session operator language such as "do it all", "full authority",
  "build to my vision", or "prior auth for production steps" authorizes the
  full dependency chain of the stated objective, including production landing
  for items the linked issues already list as authorized. Do not dilute that
  into read-only planning.
- Inside an authorized campaign, prefer action over clarification. Record
  outcomes on the issue and in the owning app `STATUS.md`. Stop only for:
  failed `make write-path-check`, missing secrets the agent cannot mint,
  or an active freeze-window serving lock (no serving-path flips during the
  lock except rollback).
- Freeze windows protect live contests. Outside those windows, authorized
  serving-path deploys and knob flips proceed. During a freeze window, keep
  building, testing, and merging non-serving work; hold only the serving-path
  production flip until the window clears, unless the operator orders a
  specific rollback.
- Every access point has the same authority. Cursor / Grok Bot is not a
  second-class client: when it can reach the Codespace write path, it
  commits, pushes, merges, and operates Railway the same way as a Codespace
  shell agent.

## Portable operations and secrets

- Required operational interfaces are ordinary files, process environment
  variables, shell commands, documented CLIs, and HTTPS APIs.
- The Codespace is the persistent Git authentication and push surface. The
  operator Mac keeps only the native `gh` access needed to open the Codespace
  and may edit a local checkout. Use `scripts/codespace-push` to transfer the
  local worktree diff and perform commit and push inside the Codespace. Do not
  copy Codespace credentials to the Mac or mint per-agent PATs for Claude,
  Codex, Copilot, or Grok. Actions use the built-in `GITHUB_TOKEN` plus
  repository secrets; Codespaces secrets are injected only into the Codespace
  container, where interactive shells unset the built-in `GITHUB_TOKEN` so web
  and SSH sessions share the `gh` login.
- Railway mutations and Real Sports runner work run from the Codespace via `scripts/codespace-railway-env` (CLI session first, API token fallback, never both Railway token kinds). Canonical auth is a Mac `~/.railway` session synced with `scripts/sync-railway-session-to-codespace`; do not mint `RAILWAY_API_TOKEN` when that session works. Mac wakes the Codespace; it is not the Railway or Real Sports host. Keep the Codespace Available around live slate windows. Full contract: root `ENTRY_POINTS.md` **Railway from the Codespace** (issues #300 / #302 / #306).
- One `gh` identity on every surface, not just the Codespace (issue #235):
  `gh` prefers an env `GH_TOKEN`/`GITHUB_TOKEN` over the native keyring
  `gh auth login`, and a local agent CLI (Claude Code, Codex CLI, Copilot CLI)
  commonly injects its own scoped token for its own API calls into the
  process it runs commands in. `make write-path-check` and
  `scripts/codespace-push` always `unset GITHUB_TOKEN GH_TOKEN` before calling
  `gh codespace ...`, so an agent-injected token can never shadow the native,
  codespace-scoped login these two scripts depend on. If a `gh codespace`
  call still fails outside those two scripts, run it with
  `env -u GH_TOKEN -u GITHUB_TOKEN gh ...` rather than re-diagnosing this.
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
- Real Sports authentication is a third portfolio-wide credential, the same
  shape as GitHub and Railway: one operator-seeded, durable browser session,
  not assumed to expire on a schedule and not rotated on one. Recovery is
  only an ordinary interactive browser login, never a scripted one, and only
  on explicit operator action. The canonical value lives in the env var
  `REALSPORTS_STORAGE_STATE_B64GZ`; its one readable/settable copy is the
  `wnba-oracle` Railway project's shared variable of that name, a storage
  location Railway's project-scoped shared variables require, not an
  ownership claim by that application. Every other surface holds a literal,
  hash-verified copy of the same value: the GitHub Actions secret, the
  Codespaces secret, and each Railway service that needs it (for example
  `nfl-oracle-worker`). Compare copies by `sha256[:8]`, never by value. A
  session attached to the Codespace reaches Real Sports the same way it
  reaches GitHub and Railway, through the Codespaces secret and the
  devcontainer's baked-in Playwright/Chromium dependencies (issue #242).
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
- A sport application's multi-milestone roadmap is documentation, not an
  issue: the plan lives in that application's `README.md` (Roadmap section)
  and milestone progress in its `STATUS.md`. Each milestone's scoped
  implementation work still gets its own issue when it starts.
- Decision rationale belongs in issues, PRs, tests, code comments, or commits.
  Do not create competing markdown ledgers.
- `AGENTS.md` is the only agent-instruction format in this repository. Each
  `CLAUDE.md` is a plain symlink to its sibling `AGENTS.md`. Root
  `.github/copilot-instructions.md` and root `.cursorrules` are the same
  pattern at the portfolio level, symlinked to root `AGENTS.md`, present only
  because Copilot Chat/CLI and Cursor (Grok Bot) do not read `AGENTS.md`
  natively. Do not add any other model-specific instruction file or a shim
  that carries separate content.

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

Never hold more than five unpushed commits. Push the branch or open a draft
pull request first. An agent that cannot push has no working credential and
must stop and report rather than accumulate history that only one machine
holds. `make write-path-check` enforces both the push-route check and the
ceiling.

**Static-copy entry points** (may be stale; fetch live before acting):
- Claude, Codex, Copilot, and Grok cloud projects or chats that use uploaded
  files, pasted context, exported session files, or knowledge bases instead of
  reading the repository directly
- Local agent session files or mobile chats that were prepared from a prior
  snapshot

### Keeping static snapshots current

Claude, Codex, Copilot, and Grok cloud projects may contain uploaded static
copies of the root instructions and application documents. The canonical
snapshot bundle is root `AGENTS.md`, root `README.md`, root `ENTRY_POINTS.md`,
root `OVERVIEW.md`, root `FILES.md`, root `Makefile`, root `pyproject.toml`,
`.devcontainer/`, `.github/workflows/`, and each application's `AGENTS.md`,
`README.md`, and `STATUS.md`. `ENTRY_POINTS.md` is the portfolio-wide
Codespace, agent, auth, and push reference every application `README.md`
points to; keep it in the bundle so it never drifts out of sync with the
files that depend on it. `OVERVIEW.md` is curated structural context.
`FILES.md` is generated with `scripts/generate_file_manifest.py` and must be
regenerated when the tracked tree changes. The root of this repository has
no `STATUS.md`;
mutable state belongs to application `STATUS.md` files. Static copies drift.
Before acting on any of them:

1. Fetch the live version from the repository through the GitHub connector
2. Treat the live file as authoritative
3. If a snapshot and the live repository disagree, note the discrepancy
   and follow the repository
4. The operator re-uploads snapshots to all configured Claude, Codex, Copilot,
   and Grok projects when the context freshness workflow flags a change

Sync-critical files: every `AGENTS.md` and `README.md`, every application
`STATUS.md`, plus root `ENTRY_POINTS.md`, `Makefile`, `pyproject.toml`,
`.devcontainer/`, and `.github/workflows/`. When one of these changes on
`main`, every agent must re-read it before related work, and the operator
refreshes the uploaded
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
make setup                      # Install locked dependencies only
make codespaces-smoke           # Verify contracts, lint, and types
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

`make setup` provisions and `make codespaces-smoke` verifies. They are
deliberately separate: environment creation must never depend on the working
branch being lint-clean, or a single style error leaves the canonical
environment unbuildable exactly when it is needed most.

Never act on remembered or cached copies of sync-critical files when a
live copy is reachable.

## Pull request autonomy

- The operator never has to approve or merge a pull request through manual
  action. When a PR's required checks are green and the change is within the
  scope the operator authorized (including production-path PRs whose linked
  issue authorizes production landing), the acting agent merges it. Every
  access point (Copilot CLI, Claude Code, Codex, the Claude GitHub App, the
  Copilot coding agent, and Cursor / Grok Bot) follows this rule identically.
- Merge with squash to keep `main` linear, then delete the branch.
- After merge, execute any production landing steps the linked issue already
  authorized (deploy, restart, env/SHA flip) from the Codespace, then verify
  live and update STATUS with verified facts only.
- Agents must not leave stale PRs open. If a PR the agent owns cannot merge
  (failing checks, conflicts, review feedback), the agent fixes it, asks
  for help, or closes it with a reason.

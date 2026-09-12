# Sports Oracle

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/cheeksmagunda/sports/tree/main?quickstart=1)

Sports Oracle is a monorepo for independent sports applications and the
provider-neutral technical platform they share. Each sport owns its models,
strategy, calendars, providers, schemas, domain endpoints, operations, and
runtime permissions. `packages/oracle-core` owns reusable technical
infrastructure only.

## Development surfaces

The repository is designed to behave the same on a local checkout, in GitHub
Codespaces, and in GitHub Actions. Codespaces is the canonical development
environment for managing the whole portfolio across Claude, Codex, Copilot,
and Grok. The lockfile and Makefile are the shared contract; credentials are
supplied by the host surface and are never baked into the image or committed
to the repository.

### GitHub Codespaces

Use the button above to create or resume a Codespace on `main`, or choose
**Code > Codespaces > Create codespace on main**. The button uses GitHub's
[documented resume link](https://docs.github.com/en/codespaces/setting-up-your-project-for-codespaces/setting-up-your-repository/facilitating-quick-creation-and-resumption-of-codespaces).
The devcontainer starts PostgreSQL and Redis, installs the locked workspace,
and runs `make codespaces-smoke`. Required setup does not install Claude,
Codex, Copilot, Grok, or other vendor tooling. Those are optional editor or
chat capabilities that should attach to the live repo or receive refreshed
snapshots.

Inside a Codespace, use the same commands as locally:

```sh
make setup
make test
```

GitHub CLI authentication is provided by the Codespaces session. Application
secrets belong in Codespaces secrets or the process environment for the
specific command that needs them. Do not create a plaintext `.env` file.

The devcontainer includes an SSH server for terminal access. Use your existing
local GitHub CLI login to connect to the Codespace. If that login lacks
Codespaces access, run `gh auth refresh --hostname github.com --scopes codespace`
and complete GitHub's authorization prompt.

```sh
gh codespace ssh --repo cheeksmagunda/sports
```

For repeatable commands, use the name returned by `gh codespace list` and keep
the complete login-shell command quoted:

```sh
gh codespace ssh --codespace CODESPACE_NAME -- \
  "bash -lc 'cd /workspaces/sports && make write-path-check'"
```

The login shell loads the Codespace's existing environment for GitHub and
project operations. A non-login SSH command may lack that environment. Local
GitHub authentication opens the connection; project commands use the
Codespace's own authentication. Run edits and verification in the remote
checkout, and inspect its branch and working tree before making changes.

Railway operations use the operator's authenticated local Railway CLI.
Codespaces and other cloud sessions do not have Railway access. Never copy
the local Railway login or its credentials into a cloud session.

The SSH feature takes effect in newly created or rebuilt containers. An
existing Codespace without an SSH server needs that prerequisite before
`gh codespace ssh` can connect. Save ongoing work before any planned rebuild.

## Start without setup decisions

Requirements: Python 3.11 or 3.12, `uv`, and Git. Use existing native `gh` and
Railway CLI logins for those services. Runtime secrets come from the process
environment. Docker is required only for the container and database acceptance
path.

Codespaces supplies the tools and services automatically. On a laptop,
`make setup` validates and installs the lockfile; everyday commands use editable
workspace packages so source changes are visible immediately. The Linux
devcontainer keeps its virtual environment outside the source mount, separate
from the laptop's `.venv`. Production images use non-editable installations.

```sh
make setup
make test
```

Run `make setup` again after pulling dependency changes. Provider credentials,
Railway access, and optional browser tooling are unnecessary for offline work.
`make test` isolates the offline suite from inherited database and Redis URLs;
`make test-integration` deliberately uses the configured development services.
Keep laptop checkouts outside cloud-synced Desktop and Documents folders, for
example `~/Developer/sports`. Open the physical folder in your editor or agent,
not a Desktop symlink, so filesystem permissions resolve to the checkout.
iCloud can evict source, Git metadata, and virtual-environment files even after
a dependency reinstall. Recreate generated environments with `uv sync --frozen
--all-packages --all-extras --reinstall`; never copy them between machines.

Before changing an application, read root `AGENTS.md`, then that application's
`AGENTS.md`, `README.md`, and `STATUS.md`. An application may also provide its
own ignored secret files, connector configuration, skills, and narrowly scoped
workflow credentials. Those application-owned surfaces must not be assumed by
another sport or promoted into the shared core.

## Contribution process

Create or reuse one GitHub issue for every work item before acting. Record the
objective, acceptance check, and risk or rollback note. Link branches, commits,
and pull requests to that issue.

Use a short-lived branch or worktree, keep the change focused, and let the
shared checks run before merging. Production changes require an issue, a green
CI run, an explicit deployment decision, and a rollback path. An outage or
security response may start immediately, but the issue should be opened as
part of the response. Do not invent product behavior when the product intent
is unclear; preserve existing read-only behavior and record the open decision.

For data-science work, attach enough evidence to reproduce the result: data
source and snapshot identity, time-aware train and test boundaries, leakage
checks, a simple baseline, calibration or uncertainty measurements, random
seed, artifact identity, and the result that justifies the change. A model
change is not accepted because it looks plausible on one slate.

AI-assisted work follows the same repository contract. The agent should state
what it inspected, separate verified facts from inference, avoid hidden
external mutations, run the smallest useful checks, and leave a concise
handoff in the issue or pull request. Claude, Codex, Copilot, Grok, and local,
Codespaces, web, app, or mobile sessions are optional entry points, not
separate sources of truth.

See `CONTRIBUTING.md` for the contribution process and data-science checklist.

## Workspace

```text
packages/oracle-core/   Domain-free shared platform, imported as oracle_core
wnba-oracle/            WNBA application and all WNBA-owned behavior
nfl-oracle/             NFL application and all NFL-owned behavior
nba-oracle/             NBA application and all NBA-owned behavior
nhl-oracle/             NHL application and all NHL-owned behavior
scripts/                Portfolio operations, secret injection, boundary checks
```

The dependency direction is application to core. Core cannot import an
application, and applications cannot import one another.

## Repository and deployment model

`sports` can hold shared things, including:

- Root `AGENTS.md` for every coding agent
- GitHub Actions, security checks, and portfolio-wide automation
- `oracle-core`, the shared technical foundation
- Future common infrastructure, once proven useful

Each sport may define its own deployment source, services, databases, frontend,
workflow set, and rollback procedure. The repository may be the deployment
source when an application needs to import `oracle-core`, but deployment
configuration and production facts remain application-owned.

Production source deploys are limited to `main` and wait for the applicable
application checks. Each application defines its own serving dependencies,
scheduled jobs, data authority, backup boundaries, and rollback requirements in
its child documentation.

## Day-close and historical backup pattern

Every sport application eventually needs a day-close job: grade a frozen
decision against finalized real-world results once a provider's contest
settles, then keep a bounded catch-up window so a later-finalizing contest,
a missed run, or an earlier outage still gets graded on a subsequent day.
That orchestration shape - attempt a target day, isolate one day's failure,
retry a bounded window of earlier ungraded days, aggregate to a job result -
is provider-neutral and lives in `oracle_core.dayclose.run_sweep`. What
"graded" means, what provider data to refresh, and which outcomes are
terminal versus worth flagging stay entirely in the owning application's
`close_one_day` callback; `oracle-core` never imports a sport package.

`nfl-oracle` is the first application built on this pattern
(`nfl_oracle.recommendations.dayclose`, scheduled by `.github/workflows/
nfl-dayclose.yml` and `nfl-corpus-backup.yml`). Both scheduled workflows gate
on a cheap, session-free public-schedule check
(`nfl-oracle/scripts/nfl_dayclose_gate.py`) for whether the sweep's own
catch-up window contains any slate, so an off-season day costs nothing; a
manual `workflow_dispatch` run always bypasses the gate. The shared
ledger-post/escalate mechanics live in the
`.github/actions/dayclose-ledger` composite action.

`wnba-oracle`'s existing day-close job (a Railway cron, verified from GitHub
Actions by `wnba-dayclose-verify.yml`) predates this pattern and is
structurally different. It is not migrated onto `oracle_core.dayclose`
retroactively; only new sport day-close jobs are expected to build on it.

All sport day-close jobs that need a Real Sports session share one
operator-captured session end to end: the operator captures it locally
(`scraper/storage_state.json`), it is stored as a single repository secret,
`REALSPORTS_STORAGE_STATE_B64GZ` (base64+gzip, unprefixed - not per sport),
and every sport's day-close workflow reads that same secret. Database
credentials stay per-sport and prefixed (for example
`NFL_DAYCLOSE_DATABASE_URL`), since each application owns a separate
database. TLS root certificates are per-sport and prefixed too, for the same
reason a database URL is: Railway issues a distinct, self-signed certificate
chain per managed Postgres instance, not one platform-wide CA, so a working
cert for one sport's database (for example WNBA's `PG_SSL_ROOT_CERT`) cannot
be reused for another sport's differently-provisioned instance (confirmed
live when NFL's own day-close first ran verified TLS - see
`nfl-oracle/STATUS.md`, issue #149).

## Local backend authentication

Normal commands run directly. They use exported environment values, deployment
environment values, and native CLI credential stores without copying secrets:

```sh
APP=wnba-oracle
make test-app APP="$APP"
scripts/auth-check "$APP" --offline
scripts/auth-check "$APP" --live
```

Do not copy a working `gh` or Railway CLI session into SOPS or another token
file. HTTP automation may use a separately scoped environment credential when
the API requires one.

SOPS and age are optional for operators who want encrypted local persistence
for environment-backed values. The repository never needs a plaintext `.env`
file. Optional root-common and application-specific files are separated:

```text
.secrets/common.sops.env
$APP/.secrets/local.sops.env
```

If using them, create or edit them with SOPS, then enforce permissions:

```sh
mkdir -p .secrets "$APP/.secrets"
chmod 700 .secrets "$APP/.secrets"
sops .secrets/common.sops.env
sops "$APP/.secrets/local.sops.env"
chmod 600 .secrets/common.sops.env "$APP/.secrets/local.sops.env"
```

The public age recipient is tracked in `.sops.yaml`. Set
`SOPS_AGE_KEY_FILE` to a mode `0600` private identity outside this repository,
or use the standard SOPS age identity location.

Run a command with root-common and one application's optional encrypted values
injected only into that child process:

```sh
scripts/with-secrets "$APP" -- make test
scripts/with-secrets "$APP" -- scripts/auth-check "$APP" --live
```

Explicitly exported variables take precedence over encrypted application
values, and application values take precedence over root-common values. The
optional loader decrypts in memory and does not create a plaintext file.

Frontend login passwords are not backend secrets. They remain in iCloud
Passwords and are entered through browser Autofill or user interaction.

## Verification targets

```sh
make test-core
make test-app APP=wnba-oracle
make test-integration  # requires PostgreSQL, Redis, and their URL variables
make test-contract
make security
make lint
make typecheck
make build
make check-boundaries
```

Application CI calls the shared core checks and the selected application's
checks, then builds and probes only that application's runtime roles. Operational
workflow schedules and production evidence are application state, so their
current values belong in that application's `STATUS.md`.

Frontend CI audits the locked npm graph, runs lint, types, and tests, builds the
exact production container, and verifies that its HTML API marker and browser
security policy use the same configured HTTPS origin.

See each application's `AGENTS.md` for sport-specific commands and verification
rules.

See `APPLICATION_GUIDE.md` when adding another sport application.

# Sports Oracle

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/cheeksmagunda/sports/tree/main?quickstart=1)

Sports Oracle is a monorepo for independent sports applications and the
provider-neutral technical platform they share. Each sport owns its models,
strategy, calendars, providers, schemas, domain endpoints, operations, and
runtime permissions. `packages/oracle-core` owns reusable technical
infrastructure only.

## Development surfaces

The repository is designed to behave the same on a local checkout, in GitHub
Codespaces, and in GitHub Actions. The lockfile and Makefile are the shared
contract; credentials are supplied by the host surface and are never baked
into the image or committed to the repository.

### GitHub Codespaces

Use the button above to create or resume a Codespace on `main`, or choose
**Code > Codespaces > Create codespace on main**. The button uses GitHub's
[documented resume link](https://docs.github.com/en/codespaces/setting-up-your-project-for-codespaces/setting-up-your-repository/facilitating-quick-creation-and-resumption-of-codespaces).
The devcontainer starts PostgreSQL and Redis, installs the locked workspace,
and runs `make codespaces-smoke`. Required setup does not install Claude,
Copilot, or other vendor tooling. Those are optional editor capabilities.

Inside a Codespace, use the same commands as locally:

```sh
make setup
make test
```

GitHub CLI authentication is provided by the Codespaces session. Application
secrets belong in Codespaces secrets or the process environment for the
specific command that needs them. Do not create a plaintext `.env` file.

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

## Lightweight contribution process

This is a hobby project, so the process is intentionally small. Read-only
exploration, local experiments, and one-line fixes do not need an issue. Create
one issue before material work such as a feature, bug fix, refactor, dependency
change, data or model change, deployment change, or credential/schedule work.
The issue only needs a short objective, acceptance check, and risk or rollback
note. Link the issue from the pull request.

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

AI-assisted work follows the same lightweight contract. The agent should state
what it inspected, separate verified facts from inference, avoid hidden
external mutations, run the smallest useful checks, and leave a concise
handoff in the issue or pull request. Claude, Copilot, Codex, and local or
cloud sessions are optional entry points, not separate sources of truth.

See `CONTRIBUTING.md` for the lightweight process and data-science checklist.

## Workspace

```text
packages/oracle-core/   Domain-free shared platform, imported as oracle_core
wnba-oracle/            WNBA application and all WNBA-owned behavior
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

# Sports Oracle

Sports Oracle is a private monorepo for independent sports applications and the
provider-neutral technical platform they share. Each sport owns its models,
strategy, calendars, providers, schemas, domain endpoints, operations, and
runtime permissions. `packages/oracle-core` owns reusable technical
infrastructure only.

## Start in five minutes

Requirements: Python 3.11 or 3.12, `uv`, and Git. Use existing native `gh` and
Railway CLI logins for those services. Runtime secrets come from the process
environment. Docker is required only for the container and database acceptance
path.

```sh
uv sync --all-packages --all-extras
make test
make security
make lint
make typecheck
make check-boundaries
```

Before changing an application, read root `AGENTS.md`, then that application's
`AGENTS.md`, `README.md`, and `STATUS.md`. An application may also provide its
own ignored secret files, connector configuration, skills, and narrowly scoped
workflow credentials. Those application-owned surfaces must not be assumed by
another sport or promoted into the shared core.

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
scripts/with-secrets "$APP" -- ../scripts/auth-check "$APP" --live
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

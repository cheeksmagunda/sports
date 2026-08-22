# Sports Oracle

Sports Oracle is a private monorepo for independent five-player daily-draft
applications and the provider-neutral technical platform they share. Each
league owns its models, strategy, calendars, providers, schemas, and domain
endpoints. `packages/oracle-core` owns reusable technical infrastructure only.

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

Before changing a league application, read root `AGENTS.md`, then that
application's `AGENTS.md`, `README.md`, and `STATUS.md`.

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

Meanwhile, Railway treats `sports` as the GitHub source for WNBA, then builds
only the appropriate part:

- Backend services use the monorepo root so they can import `oracle-core`, with
  `wnba-oracle/Dockerfile`
- Frontend uses `wnba-oracle/frontend`
- Postgres and Redis stay as the same connected Railway services

So `sports` is both the shared repository and the deployment source. WNBA
remains a self-contained application inside it.

## Local backend authentication

Normal commands run directly. They use exported environment values, deployment
environment values, and native CLI credential stores without copying secrets:

```sh
make test-wnba
scripts/auth-check wnba-oracle --offline
scripts/auth-check wnba-oracle --live
```

Do not copy a working `gh` or Railway CLI session into SOPS or another token
file. HTTP automation may use a separately scoped environment credential when
the API requires one.

SOPS and age are optional for operators who want encrypted local persistence
for environment-backed values. The repository never needs a plaintext `.env`
file. Optional root-common and WNBA-specific files are separated:

```text
.secrets/common.sops.env
wnba-oracle/.secrets/local.sops.env
```

If using them, create or edit them with SOPS, then enforce permissions:

```sh
mkdir -p .secrets wnba-oracle/.secrets
chmod 700 .secrets wnba-oracle/.secrets
sops .secrets/common.sops.env
sops wnba-oracle/.secrets/local.sops.env
chmod 600 .secrets/common.sops.env wnba-oracle/.secrets/local.sops.env
```

The public age recipient is tracked in `.sops.yaml`. Set
`SOPS_AGE_KEY_FILE` to a mode `0600` private identity outside this repository,
or use the standard SOPS age identity location.

Run a command with root-common and one application's optional encrypted values
injected only into that child process:

```sh
scripts/with-secrets wnba-oracle -- make test
scripts/with-secrets wnba-oracle -- ../scripts/auth-check wnba-oracle --live
```

Explicitly exported variables take precedence over encrypted application
values, and application values take precedence over root-common values. The
optional loader decrypts in memory and does not create a plaintext file.

Frontend login passwords are not backend secrets. They remain in iCloud
Passwords and are entered through browser Autofill or user interaction.

## Verification targets

```sh
make test-core
make test-wnba
make test-integration  # requires PostgreSQL, Redis, and their URL variables
make test-contract
make security
make lint
make typecheck
make build
make check-boundaries
```

Backend CI calls these same targets, then builds the WNBA image and probes each
runtime role plus API startup against PostgreSQL and Redis. Operational workflow
schedules and production evidence are application state, so their current values
belong in `wnba-oracle/STATUS.md`.

See `wnba-oracle/AGENTS.md` for WNBA-specific commands and verification rules.

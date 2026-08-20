# Sports Oracle

Sports Oracle is a private monorepo for independent five-player daily-draft
applications and the provider-neutral technical platform they share. Each
league owns its models, strategy, calendars, providers, schemas, and domain
endpoints. `packages/oracle-core` owns reusable technical infrastructure only.

## Start in five minutes

Requirements: Python 3.11 or 3.12, `uv`, and Git. Backend operations that need
local credentials also require `sops` and `age`.

```sh
uv sync --all-packages --all-extras
make test
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

## Local backend secrets

The repository never needs a plaintext `.env` file. Root-common secrets and
WNBA-specific secrets are encrypted separately:

```text
.secrets/common.sops.env
wnba-oracle/.secrets/local.sops.env
```

Create or edit them with SOPS, then enforce permissions:

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

Run a command with root-common and one application's secrets injected only into
that child process:

```sh
scripts/with-secrets wnba-oracle -- make test
scripts/auth-check wnba-oracle --offline
scripts/auth-check wnba-oracle --live
```

Explicitly exported variables take precedence over encrypted application
values, and application values take precedence over root-common values. The
loader decrypts in memory and does not create a plaintext file.

Frontend login passwords are not backend secrets. They remain in iCloud
Passwords and are entered through browser Autofill or user interaction.

## Verification targets

```sh
make test-core
make test-wnba
make test-contract
make lint
make typecheck
make build
make check-boundaries
```

See `wnba-oracle/AGENTS.md` for WNBA-specific commands and verification rules.

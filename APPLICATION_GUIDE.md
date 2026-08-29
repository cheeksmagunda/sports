# Adding a sport application

Each sport is an independent application under a directory matching
`*-oracle/`. The application owns its domain behavior and its operational
surfaces. The shared package owns only provider-neutral technical primitives.

## Application-owned surfaces

An application should keep these inside its directory:

- source, tests, migrations, data, artifacts, and domain schemas;
- providers, calendars, models, features, strategies, jobs, schedules, and API
  routes;
- `AGENTS.md`, `README.md`, and `STATUS.md`;
- optional `skills/` and connector configuration such as `.mcp.json`;
- `.env.example` and ignored `.secrets/` values for that application's runtime;
- workflow behavior and credentials scoped to that application's services. GitHub
  workflow files themselves remain under the root `.github/workflows/` directory
  because that is where GitHub discovers them.

Application agents must read the root `AGENTS.md` and then their own child
instructions. They may add stricter rules, commands, permissions, and safety
gates, but may not weaken the portfolio contract or access another sport's
private runtime state.

## Shared package boundary

`packages/oracle-core` may contain configuration foundations, redaction,
logging, HTTP transport and retry policy, persistence primitives, job
lifecycle mechanics, service scaffolding, artifact handling, and test fakes.
It must remain free of sport names, league calendars, player or team models,
provider payloads, scoring rules, strategies, and domain routes.

## Boundary checks

The root boundary checker discovers `*-oracle/` applications and prevents
cross-application imports. Applications with `modeling/`, `picker/`, or
`predict/` packages receive model-kernel checks automatically. An `assurance/`
package receives the corresponding runtime-isolation checks. New applications
should follow those conventional package names when those boundaries apply.

Use the generic root target while retaining any application-specific targets:

```sh
make test-app APP=<sport>-oracle
make check-boundaries
```

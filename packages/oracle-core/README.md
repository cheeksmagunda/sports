# oracle-core

`oracle-core` contains provider-neutral technical infrastructure shared by
Sports Oracle applications. It deliberately contains no league, calendar,
player, scoring, model, strategy, or provider contract.

The public package includes:

- process-environment configuration, secret-aware values, and redaction;
- structured JSON logging and safe exception rendering;
- synchronous and asynchronous HTTP transport and bounded retries;
- PostgreSQL transaction, Redis key-value, lease, and JSON cache primitives;
- registered job execution with roles, lifecycle events, clocks, and leases;
- generic FastAPI root and health behavior;
- atomic artifact persistence, integrity checks, and deterministic test fakes.

Applications retain ownership of their settings extensions, database schema,
migrations, routes, jobs, schedules, provider adapters, and domain behavior.

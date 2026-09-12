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
- dossier entry and gap schema for contest analysis;
- atomic artifact persistence, integrity checks, and deterministic test fakes;
- day-close sweep orchestration (`oracle_core.dayclose`): grade a target day,
  then retry a bounded catch-up window for anything still ungraded.

Applications retain ownership of their settings extensions, database schema,
migrations, routes, jobs, schedules, provider adapters, and domain behavior.
`oracle_core.dayclose.run_sweep` is intentionally thin: it isolates one day's
failure from the rest of the sweep and aggregates outcomes into a
`JobResult`, but every domain judgment - what "graded" means, what provider
data to refresh, which outcome statuses are terminal versus worth flagging -
stays in the calling application's `close_one_day` callback.

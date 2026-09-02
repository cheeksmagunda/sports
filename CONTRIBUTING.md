# Contributing to Sports Oracle

Sports Oracle is a hobby application. This workflow saves time by keeping
context, commands, and evidence in one place. It is not a corporate approval
system. When an AI agent is doing the work, it creates or reuses the issue,
handles the branch and PR, and runs the checks. The operator does not need to
manage that bookkeeping.

## Before work

Read the root `AGENTS.md`, the nearest application `AGENTS.md`, `README.md`,
and `STATUS.md`. Read-only investigation is always welcome. For material work,
open one GitHub issue first with an objective, acceptance check, and risk or
rollback note when relevant.

Material work includes features, bugs, refactors, dependency or workflow
changes, data or model changes, deployments, credentials, schedules, and
production operations. A tiny typo, local experiment, or read-only audit does
not need ceremony. During an incident, act first and open or update the issue
immediately.

## Change flow

1. Start from current `main` and use a short-lived `chat/<issue>-<slug>` branch
   or isolated worktree. Keep the change focused.
2. Keep the issue, code, tests, and documentation aligned. Use the root
   `Makefile`, lockfile, and devcontainer as the shared command contract.
3. Open a pull request linked to the issue. Wait for applicable checks, review
   the diff, and squash merge when green. Delete the branch afterward.
4. Deploy only from `main` through the documented application workflow. Do not
   mutate production data, schedules, or credentials from a local experiment.

Every material commit and PR must reference an issue. Branch names should carry
the issue number (`chat/<issue>-<slug>`), commits should include `#<issue>`, and
the PR should use a closing reference (`Closes #<issue>` or `Refs #<issue>`).

The current operator may authorize a direct commit for recovery work. That
exception does not change the normal issue and pull-request flow for future
work.

## Data-science change checklist

For feature, training, calibration, ranking, or optimizer changes, record when
applicable:

- exact data source, snapshot date, query, or artifact hash;
- time-aware train, validation, and test boundaries;
- leakage and identity checks, including late-arriving information;
- a simple named baseline and the metric that matters;
- calibration, uncertainty, censoring, and missing-data treatment;
- deterministic seed and lockfile or environment identity;
- slice-level results, not only one aggregate score;
- rollback condition and whether the result is offline, shadow, or production.

Promote code into `oracle-core` only when it is stable, provider-neutral, and
supported by tests and repeated use. Keep sport models, features, schemas, and
provider behavior in the owning application.

## AI-assisted work

AI tools may work from local, Codespaces, or cloud sessions, but the repository
is the source of truth. An agent must not infer product direction from silence.
When intent is unclear, preserve existing behavior, identify the decision, and
make the smallest reversible improvement.

Every agent handoff should include scope, files changed, checks run and not
run, verified findings, unresolved risks, and any external action. Credentials
stay in native CLI sessions, process environments, or Codespaces secrets. They
never belong in prompts, images, logs, source, or committed configuration.

## Fast path

```sh
make setup
make test
```

Use `make build` before changing packaging or Docker behavior. Use the
application `STATUS.md` and `scripts/auth-check` before production work.

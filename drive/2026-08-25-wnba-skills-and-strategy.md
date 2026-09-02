# Task: Harvest sports AI skills and improve WNBA Oracle
Status: running
Created: 2026-08-25
Owner: operator (IᎤænnغS), briefed in Copilot CLI session


Do not start until the operator says to start. This file is the brief.
This is a large task. Budget it that way. Do not ship a thin wrapper
around downloaded skill text.

You are working for IᎤænnغS. Target application: `wnba-oracle` inside
`github.com/cheeksmagunda/sports`. Shared platform: `packages/oracle-core`.
Read root `AGENTS.md`, then `wnba-oracle/AGENTS.md`, `wnba-oracle/README.md`,
and `wnba-oracle/STATUS.md` before acting. Recheck mutable production facts
before relying on them. Inspect the worktree and preserve unrelated changes.

This is a four-phase build-and-ship task. After the review exists, you have
full agency to implement, verify, commit, push, open a PR, and squash-merge
to `main` with no further user input.

## What this is

Visit every source URL below. From those pages and any repos they point to:

1. Find actual Claude / AI agent skills. Do not install or copy them
   verbatim. Classify each useful one by kind, then deliver it in kind:
   - Workflow skills the user or a scheduled task can call
   - Data-science and engineering skills folded into wnba-oracle's
     purpose (training, evaluation, calibration, backtesting, data work)
   - Infrastructure the sources show we lack, copied as structure and
     code, not as a prose skill
   - Merged skills, where several upstream skills combine into one
     callable skill for relevant repo work
2. Audit where data actually lives: GitHub, Railway services, Postgres,
   Redis, and local-only paths. Match every workflow skill to that flow.
3. Review hierarchy, features, and knobs against the same sources.
4. Implement the justified changes and land them on `main`.

The operator does not want vendored third-party skills. The operator wants
rewritten workflows that an agent can run against this product, plus the
product changes those workflows imply.

## Scope

Stay inside `wnba-oracle` except for devops.

In scope:

- All of `wnba-oracle/`, including backend, tests, skills, child docs, and
  frontend when a source-justified product change requires it
- Devops required to build and ship: root GitHub workflows, container
  probes, Railway config that already belongs to this app, package/CI
  wiring that WNBA deploy depends on

Out of scope:

- `packages/oracle-core` domain, models, features, scoring, or sports
  abstractions. Do not promote WNBA ideas into core. Touch core only if
  existing provider-neutral plumbing is already broken for a WNBA change,
  and keep that touch domain-free
- Other league applications, if any appear later
- Unrelated concurrent work in the tree

## Agency

This task authorizes the full ship path. Do not pause for confirmation.

You will:

1. Implement the justified hierarchy, feature, knob, skill, data-flow,
   and devops changes
2. Run the required checks
3. Commit coherent slices on this worktree branch
4. Push the branch
5. Open a PR against `main`
6. Fix CI if it fails
7. Squash-merge when required checks are green
8. Delete the branch

Production source deploys from `main` after CI. That deploy is expected.
Declare new knobs in code and `.env.example` with defaults that keep the
app bootable without a human setting Railway values first. If a change
truly cannot ship without a live credential, schedule edit, or data
mutation, implement the code path with a safe default and record the
leftover in `wnba-oracle/STATUS.md`. Do not invent credentials. Do not
delete services, databases, or billing objects.

SKILL.md is the only extra agent-instruction exception. `CLAUDE.md` files
are plain symlinks to their sibling `AGENTS.md`, present only because
Claude Code does not read `AGENTS.md` natively; that is not a separate
shim. Do not add `.cursorrules`, `copilot-instructions`, or any other
model-specific file that carries content of its own.

## Hard constraints

- Preserve public behavior unless a review action explicitly changes it.
- Dependency direction stays `wnba-oracle -> oracle-core`.
- Required workflows stay portable: files, env vars, shell, HTTPS. MCP,
  browser, and desktop tools may help fetch sources, but they cannot be
  the only implementation of a skill or a feature.
- Do not print secrets, tokens, connection URLs, or Real Sports session
  material. Do not load `.env` files. Do not copy native `gh` or Railway
  credentials into the repo.
- Use standard punctuation. Do not use Unicode U+2014.
- Do not create competing markdown ledgers. Skills are the skill
  deliverable. The strategy review is one working document, not a new
  permanent status file. Mutable production facts stay in `STATUS.md`.
  Decision rationale belongs in code, tests, and commits.
- Do not silently replace WNBA-owned providers with third-party live-score
  MCP wrappers. Real Sports, Odds API, RotoWire, and official WNBA stats
  stay application-owned unless evidence is strong enough to add a new
  WNBA-owned adapter.
- NBA-centric or generic sports-agent assumptions are suspect until proven
  on this WNBA five-player daily draft with slot multipliers
  2.0 / 1.8 / 1.6 / 1.4 / 1.2.
- Gamelog corpus and label corpus have different grains. Do not join them
  without the WNBA-owned identity map.
- `frozen_lineups` is append-only. Never reorder a frozen lineup from
  realized outcomes. Fail closed when lock eligibility is unknown.
- The model kernel stays isolated from API, DB, providers, settings, HTTP,
  and Redis. Decision-changing settings still cross that seam as
  `ModelPolicy`.
- Frontend and backend remain separately testable. If you change
  frontend, do not mix that into an unrelated backend commit, and run the
  frontend verification that already exists for that tree.
- Canonical runtime data is PostgreSQL. Redis is coordination, not the
  source of truth. GitHub holds source, CI, model-artifact identity, and
  the off-main corpus backup branch. Do not invent a fourth store. Do not
  treat local parquet, `data/`, or laptop files as production state.

## Source list

Skip Firefox defaults (Get Help, Solo, Customize Firefox, Get Involved,
About Us). Visit every remaining bookmark. Follow through to the actual
skill repo, SKILL.md, or MCP skill page when a listing site is only an
index.

### A. Actual AI / Claude skills and skill indexes

Fetch these first. These are raw material only, never drop-in files.

1. https://mcpmarket.com/tools/skills/sports-data-agent
   Sports Data Agent. Claude Code skill for live scores.
2. https://github.com/machina-sports/sports-skills
   Open-source agent skills for live sports.
3. https://sports-skills.sh/
   Live sports data for AI agents. Treat as the public face of sports-skills.
4. https://mcpmarket.com/tools/skills/api-sports-data-statistics
   API Sports Claude Code skill. Real-time sports data / statistics.
5. https://skillsllm.com/skill/claude-sports-analytics
   claude-sports-analytics skill page and any GitHub / MCP links it cites.
6. https://skillsllm.com/compare/claude-sports-analytics-vs-sports-skills
   Comparison. Use it to find both skill trees and decide what to keep.
7. https://skillsllm.com/compare/claude-sports-analytics-vs-ui-ux-pro-max-skill
   Comparison. Keep only sports-analytics substance. Discard UI/UX skill
   content unless it clearly changes operator-facing slate explanation.

### B. Strategy, performance-analysis, and WNBA domain sources

Mine these for hierarchy, features, knobs, and workflow design.

8. https://sinankprn.com/posts/enhancing-sporting-organisation-efficiency-with-generative-ai/
9. https://sportscienceai.com/en/posts/2025-01-04_top-5-tools-for-sports-scientists-in-2025
10. https://www.ijfmr.com/papers/2023/4/5657.pdf
11. https://www.isspf.com/articles/beginners-guide-to-performance-analysis-in-sports/
12. https://uksportsinstitute.co.uk/service/performance-analysis/
13. https://longomatch.com/en/top-5-skills-every-aspiring-sports-analyst-should-develop/
14. https://www.wnba.com/stats/inside-the-game
15. https://www.wnba.com/news/category/analysis
16. https://databallr.com/wnba
17. https://herhoopstats.com/

If a URL is dead, search from the title on the same host, then record the
miss. Do not invent page content.

## Product facts the work must use

WNBA Oracle collects the available Real Sports WNBA pool and pre-tip
signals, predicts player distributions, optimizes a five-player lineup,
freezes before lock, and serves read-only slate and lineup data.

Recheck these against live files, GitHub, Railway, Postgres, and Redis
before treating them as current:

- Jobs: `job1` collect, `job1late` late starters, `job2` predict / optimize
  / freeze, `dayclose` labels / logs / placements, isolated backfill.
- Serving: PostgreSQL is canonical. Redis is Job 2 coordination only.
- Policy seam: `wnba-oracle/src/wnba_oracle/modeling/policy.py`
- Env knobs: `wnba-oracle/.env.example` and
  `wnba-oracle/src/wnba_oracle/common/settings.py`
- Shadow overlays: `scheduler/shadow_knobs.py` via
  `PICKER_KNOB_CHALLENGER_JSON`
- Existing research scripts. Use them. Do not replace them with prose:
  `scripts/analyze_strategy_gap.py`, `scripts/calibrate_knobs.py`,
  `scripts/calibrate_starter_and_boost.py`,
  `scripts/backtest_counterfactual.py`, `scripts/backtest_walkforward.py`,
  `scripts/replay_slate.py`, `scripts/sweep_max_boost.py`
- Layout that defines current hierarchy:
  `api/`, `assurance/`, `ingest/`, `features/`, `train/`, `predict/`,
  `picker/`, `scheduler/`, `db/`, `modeling/`
- Starting storage map, to be audited and corrected:
  - GitHub `main`: source, workflows, model-artifact identity in STATUS
  - GitHub `backups` branch: corpus backup export, not runtime state
  - Railway Postgres: `wnba_game_logs`, `slate_labels`,
    `contest_leaderboards`, `job1_enrichment`, `frozen_lineups`,
    `slate_meta`, `contest_placements`, `watchdog_events`, job-run
    records, and any other tables the migrations actually create
  - Railway Redis: Job 2 freeze coordination / leases only
  - Railway services: api, frontend, cron-job1, cron-job1-late,
    cron-job2, cron-dayclose, isolated backfill
  - GitHub Actions: watchdog, provider contracts, corpus backup,
    pre-freeze guard, day-close verify
  - Tracked `wnba-oracle/models/` artifacts if present; SHA pin is the
    production identity
  - Local `data/`, `runs/`, parquet, and derived sessions are not
    canonical

Existing knob families. Classify every idea against these before adding a
new knob:

- Optimizer: samples, top-n filter, field lineups, max per team, dynamic
  team cap, boost caps, game-stack bonus, leverage / ceiling / duplication
  weights, mixture variance, ceiling-sigma boosts
- Field / ownership: measured ownership, same-game / same-team field
  boost, duplication-aware payout
- Contrarian: enabled, strength
- Enter / skip: caveat_is_skip, never_skip, payout thresholds
- Starter / minutes / availability: starter signal, expected vs confirmed,
  unknown fade, minutes lift, minutes model, game-script minutes,
  availability model
- Props, floor tilt, boost tail lift, lineup anchor floor, late re-freeze
  window, freeze lead minutes, pool exclude started games
- Shadow: model challenger SHA, picker knob challenger JSON

## Phase 1: Turn skills into the right kind of deliverable

First code deliverable, but not before a source inventory exists.

Verbatim copy is forbidden. `adopt-verbatim` is not a legal verdict.
Upstream SKILL.md files, MCP listings, and sports-skills trees are
research inputs. The output must match the kind of thing each source
actually is.

There are four legal kinds. Every candidate gets exactly one:

### Kind 1: Workflow skill (SKILL.md)

A procedure the user, an agent, or a scheduled task can call for relevant
work in this repo: slate review, freeze inspection, knob shadowing,
strategy review, backup reading, evidence lookup. A useful workflow skill
does all of the following:

- States the job it supports (ingest, freeze, review, shadow, day-close,
  backup, evidence)
- Names the exact commands, files, tables, hashes, or HTTP routes
- Says which store is authoritative for each input and output
- Says what to do when Redis is down, Postgres is thin, GitHub backup is
  stale, or a provider is skipped
- Refuses to treat live-score MCP, laptop parquet, or chat text as the
  corpus
- Has a portable non-MCP path

### Kind 2: Data-science and engineering skill, built into the app purpose

Some upstream skills are not operator workflows. They are method: model
training discipline, evaluation and calibration, distribution prediction,
walk-forward and counterfactual backtesting, ownership estimation,
sampling, feature hygiene, experiment tracking. Those do not belong only
in prose. Fold them into wnba-oracle's purpose:

- As code in `features/`, `predict/`, `picker/`, `train/`, or `eval/`
  when the behavior must be deterministic
- As a SKILL.md tied to those modules when the behavior is an
  agent-assisted procedure (e.g. "how to run and read a walk-forward
  backtest", "how to calibrate starter fade against placements")
- As both when the skill describes a procedure that drives the code

A data-science SKILL.md names the modules and scripts it operates. It is
not a generic ML essay.

### Kind 3: Infrastructure to copy into structure and code

Some sources contain structure we lack: a schema pattern, an artifact
layout, a job-runner pattern, a manifest format, a fixture/seed scheme, a
redaction or retry helper, a comparison or scoring harness. These are not
skills. Implement them as structure and code inside `wnba-oracle/` (or
existing domain-free plumbing only if it is already broken). They enter
the review as `add-feature` or `restructure` items with
`implement-now: yes` when justified.

### Kind 4: Merged skills

Where several upstream skills are fragments of one real procedure (for
example live-score fetching plus lineup advice plus result tracking),
merge them into one callable skill instead of three thin ones. Name the
merge and list the sources inside the skill.

No skill may exist that only paraphrases an upstream page. Every skill
must either drive repo code/stores (Kinds 1, 2, 4) or become code itself
(Kind 3).

### Inventory first

Create a working inventory in `drive/2026-08-25-wnba-skill-inventory.md` with one row per
candidate skill:

- source URL
- upstream name and path
- whether an actual SKILL.md / Claude skill exists
- license, and what may be quoted versus only paraphrased
- upstream data assumption (live API, scrape, local file, none)
- kind: `workflow-skill`, `ds-engineering`, `infrastructure`, `merge`
- matching WNBA store, module, and job, or `none`
- verdict: `rewrite`, `build-into-code`, `copy-structure`, `merge-into`,
  `reject`

Reject live-score toys, NBA-only workflows, UI/UX skills, and generic
"call this MCP and print scores" wrappers unless they contain a method
worth rewriting onto Job 1, Job 2, day-close, or the research scripts.

### Where to put skills

```text
wnba-oracle/skills/<skill-name>/SKILL.md
```

One workflow per directory. Optional `reference.md` or credential-free
helper scripts only when needed. Do not vendor upstream repos.

Each SKILL.md must be a real agent workflow:

- YAML front matter with `name` and `description`
- When to use / when not to use
- Trigger, inputs, steps, outputs, and failure behavior
- Data-flow section: GitHub / Railway / Postgres / Redis / none
- WNBA Oracle paths, jobs, tables, and knobs by name
- No secrets, no implied `.env` loading
- Portable fallback if MCP is unavailable

### Rewrite and placement rules

- Kind 1 and Kind 4 skills live at `wnba-oracle/skills/<name>/SKILL.md`.
- Kind 2 skills may add code plus a SKILL.md that operates it.
- Kind 3 becomes code/structure only; note it in the review, not as a
  skill.
- A skill that a scheduled task should call must say so and name the
  job/workflow, not just the chat trigger.
- Quote only what license allows. Prefer short deliverables that call
  our code.

Likely targets, confirm after reading the sources:

- Sports Data Agent / API-Sports live-score skills -> workflow over
  Job 1 / Job 1 late / existing providers / `job1_enrichment`
- machina-sports / sports-skills.sh skill tree -> merge into freeze,
  review, and shadow workflows over Job 2, `frozen_lineups`, and
  `PICKER_KNOB_CHALLENGER_JSON`; any runner or manifest structure worth
  having becomes Kind 3 code
- claude-sports-analytics -> Kind 2 data-science skill and code over
  `features/`, `predict/`, `picker/`, `ModelPolicy`, and the training /
  calibration scripts
- ISSPF / UKSI / Longomatch analyst skills -> Kind 2 workflow over
  `analyze_strategy_gap.py`, `slate_labels`, `contest_placements`, and
  `wnba_game_logs`
- Her Hoop Stats / DataBallr / WNBA Inside the Game -> external-evidence
  workflow that never pretends those sites are Postgres

### Minimum deliverable set to decide after reading

Accept or explicitly reject each. Add more only for a distinct
procedure, method, or infrastructure pattern that maps onto this repo.

1. `wnba-slate-ingest` (Kind 1)
2. `wnba-lineup-freeze` (Kind 1)
3. `wnba-picker-knobs` (Kind 1, callable by user and shadow jobs)
4. `wnba-strategy-review` (Kind 1 / Kind 2)
5. `wnba-performance-analysis` (Kind 2)
6. `wnba-external-evidence` (Kind 1)
7. `wnba-data-stores` if the audit shows agents currently guess at
   GitHub vs Postgres vs Redis (Kind 1)
8. Any Kind 2 training / calibration / backtest skills the DS sources
   justify
9. Any Kind 3 infrastructure the sources justify

If an upstream name is worth keeping, keep it only as an alias in the
description. The body must be this repo's deliverable, not theirs.

## Phase 2: Data-store and data-flow audit

This is part of the review, not an optional appendix. Write it first
inside the review document. Skills and feature work must follow it.

Working review path (save it here so other entry points can see it):

```text
drive/2026-08-25-wnba-strategy-review.md
```

Audit, from live code, migrations, workflows, Railway facts in STATUS,
and rechecked production evidence:

1. GitHub. What source, workflows, model pins, backup branch objects,
   and release artifacts actually live there. What must never be committed
   (`storage_state`, secrets, local parquet).
2. Railway app services. What each of api, frontend, job1, job1-late,
   job2, day-close, and backfill reads and writes.
3. Railway Postgres. Every real table and grain. Who writes it. Who
   reads it. Retention. What is append-only.
4. Railway Redis. Exact keys / leases / coordination uses. Prove it is
   not serving state.
5. GitHub Actions as a data path. Corpus backup, watchdog, contracts,
   pre-freeze, day-close verify. What they persist and where.
6. Local and ignored paths. `data/`, `runs/`, `models/`, scraper
   sessions. Mark each as non-canonical or pin-only.

Then draw the flow the skills must use:

```text
providers -> job1/job1late -> Postgres enrichment
         -> job2 -> Redis coordination + Postgres freeze
         -> api reads Postgres only
         -> dayclose -> labels, gamelogs, placements
         -> GitHub backups branch / STATUS pins
```

Correct that sketch from code. Every workflow skill in Phase 1 must cite
this audited flow. If a downloaded skill assumes "fetch live scores and
answer," rewrite it onto the store that already holds that fact, or
reject it.

If the audit finds a hierarchy, feature, or knob problem (wrong store,
missing table, Redis used as source of truth, backup gap, skill that
cannot run because the data is elsewhere), that item becomes implement-now
work in Phase 3 and 4.

## Phase 3: Strategy review, scoped to the product

Same review document, after the audit. Scope is:

1. Overall hierarchy of the app. Does the current package/job/policy
   seam, and the store seam from Phase 2, match how the sources say a
   sports-analytics system should be layered? Propose concrete moves:
   keep, split, rename, add a module, or reject a borrowed architecture.
   Do not reorganize for taste.
2. Feature development. Which source methods should become WNBA-owned
   features in `features/`, `predict/`, `picker/`, or `ingest/`? Which
   should stay external evidence? Which should stay out.
3. Knobs. Which existing env / `ModelPolicy` knobs should change default
   or meaning? Which new knobs are required? Which source ideas are not
   knobs and must be code.

Every review item is evidence-tagged:

- `source:` URL plus claim
- `code:` file and symbol that already implements or contradicts it
- `store:` GitHub / Railway service / Postgres table / Redis / none
- `gap:` missing hierarchy, feature, knob, or data-flow match
- `action:` `configure-existing`, `change-default`, `add-knob`,
  `add-feature`, `restructure`, `add-workflow-skill`, `add-devops`,
  `fix-data-flow`, or `reject`
- `implement-now:` yes or no, with the reason

Rules for those actions:

- Prefer `configure-existing` or `change-default` over `add-knob`.
- Prefer a tested feature over a prose skill when the behavior must be
  deterministic on game day.
- Prefer a workflow skill over code when the behavior is an operator or
  agent procedure (how to review a slate, how to shadow a knob, how to
  read the backup branch).
- `restructure` is allowed only when the current hierarchy or store seam
  blocks a justified feature. Do not churn folders.
- Importing the wrong objective is a reject. Team-performance video
  analysis is not automatically a daily-draft feature.
- `implement-now: no` is only for items that are illegal, license-blocked,
  require a new secret that does not exist, or are contradicted by the
  corpus. Everything else justified by the sources gets built.

Every `configure-existing` or `change-default` item must name the env var
and the settings / policy field. Every `add-knob` item must say why an
existing knob cannot do it, plus default, rollback, and shadow path.
Every `add-feature` item must say which WNBA module owns it. Every
workflow skill must name its authoritative store.

Do not implement product changes until this review exists and the
implement-now set is explicit. Then implement that set. You may revise
the review if coding disproves an item.

## Phase 4: Implement, verify, and ship

Implement every `implement-now: yes` item. Typical work includes:

- Rewritten workflow SKILL.md files from Phase 1, updated after the audit
- Feature builders, predictors, picker terms, ingest adapters
- Settings / `.env.example` / `ModelPolicy` wiring for new or changed knobs
- Shadow-knob support when a new picker term needs a challenger overlay
- Data-flow fixes that keep Postgres canonical and Redis coordinative
- Frontend only when the product change is source-justified
- Devops needed to build, test, or deploy those changes
- Tests for behavior and failure paths
- The smallest child-doc or `STATUS.md` update required by a real change

Implementation quality bar:

- Read before editing. Preserve unrelated behavior.
- Typed boundaries, explicit dependencies, deterministic behavior,
  bounded retries and timeouts, idempotent operations, atomic writes,
  structured logs with redaction.
- New knobs need a default that keeps current production behavior unless
  the review proves a default change and names the rollback.
- Provider work stays in `wnba-oracle` ingest, uses bounded timeouts and
  retries, and redacts URLs and errors.
- Do not treat a successful job as complete if required durable work
  failed.

Verification, from `wnba-oracle/`:

```sh
make test
make lint
make typecheck
```

If you touch prediction, features, model loading, optimizer, or freeze:

```sh
make test-contract
```

If you touch frontend, run the existing frontend lint, type, and test
path from that tree. If you touch devops, packaging, or import
boundaries, also run the root targets named in `wnba-oracle/AGENTS.md`.
Never report a check as passing unless it completed successfully. State
any required check that could not run, then fix or replace the change
that needed it.

Ship:

- Commit on this branch with standard punctuation
- Include the Copilot trailer if this environment requires it
- Push the branch
- Open a PR whose body states workflows added, data-flow findings,
  hierarchy/feature/knob changes, and leftover items that needed a
  missing secret
- Merge with squash once required checks are green
- Delete the branch

Do not leave a stale PR open. If checks fail, fix them. If the PR
conflicts, rebase or recreate and continue.

## Working method

1. Read the four required repo docs and inspect the worktree.
2. Fetch every URL in the source list. Save raw notes in the session
   workspace, not in the repo.
3. Inventory upstream skills. Rewrite them into workflow SKILL.md files.
   No verbatim drops.
4. Audit GitHub / Railway / Postgres / Redis / local paths. Write that
   audit first in the review.
5. Finish the hierarchy, feature, and knob review with store tags and an
   implement-now set. Align the workflow skills to the audited flow.
6. Implement that set. Keep going until the sources and the data-flow
   gaps are exhausted or an item is truly blocked by a missing secret or
   license.
7. Run the required checks. Commit coherent slices.
8. Push, open the PR, merge to `main`, delete the branch.
9. Summarize: workflows written, upstream skills rejected, store map,
   hierarchy changes, features added, knobs changed or added, devops
   landed, PR/merge URL, and checks actually run.

## Not authorized even with full ship agency

- Creating or rotating credentials
- Copying secrets into the repo or into chat
- Deleting Railway services, databases, or billing objects
- Mutating production contest data or rewriting freeze history
- Replacing Real Sports recovery with scripted password login
- Promoting sports domain into `oracle-core`
- Copying third-party SKILL.md files into the tree unchanged

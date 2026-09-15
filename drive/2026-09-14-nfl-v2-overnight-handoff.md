# NFL Oracle v2: overnight build handoff (for ChatGPT)

Status: ready
Created: 2026-09-14
Owner: operator (for a ChatGPT session tonight)

## Goal

Build toward nfl-oracle v2 overnight, using week 1 as real evidence to drive
model and infrastructure improvements together, plus a frontend audit and
refresh. Not a menu to pick from; land as much of all three fronts as the
session can responsibly get through the repo's normal issue to branch to PR
to review flow in one night, prioritized by what week 1 actually showed
mattered most.

## Read first (already prepared this session)

- `drive/2026-09-14-week-close-task-and-w2-boosts-handoff.md`: designs a
  recurring week-close job (trigger, what it should produce, how it
  supersedes day-close on its trigger day, live re-scrape requirement) and
  scopes the week-2 boost-handling upgrade needed before Thursday 2026-09-17.
- `drive/2026-09-14-week1-operator-retro.md`: the operator's real-time week 1
  observations, with session-verified context attached to each.
- Root `AGENTS.md`, `nfl-oracle/AGENTS.md`, current `nfl-oracle/STATUS.md`:
  process rules and latest state. This brief is a snapshot from the evening
  of 2026-09-14; re-check what has already moved (in particular whether
  `fix/156-force-retrain` has merged) before treating anything here as still
  open.

## New in this brief: frontend audit and refresh

Verified current state (2026-09-14): `nfl-oracle/frontend/` is exactly 3
files, a single static `index.html` with no build pipeline, no framework,
and no npm dependency tree, unlike `wnba-oracle/frontend`'s full Vite+React
app. Per STATUS.md it renders five picked cards in slot order (player name,
team, position, opponent), deliberately omits numeric projections, and on a
pipeline failure shows only "PICKS ARE UNAVAILABLE" with no diagnostic
detail.

Audit questions to actually answer, not assume the answer to:

- Is a framework/build pipeline warranted for v2, given the sustainability
  tradeoff already on record this week: wnba-oracle's frontend carries real
  npm/dependabot churn (three open alerts at time of writing) while
  nfl-oracle's zero-dependency static page carries none. Decide
  deliberately; do not default to adding React just because the sibling app
  has it.
- Should the failure state surface more than "PICKS ARE UNAVAILABLE"? This
  is the same observability gap already flagged on the backend (issue #156:
  "discovery mechanism today is a human loading the page") showing up on
  the frontend too. The operator learned the pipeline had failed by noticing
  wrong or missing picks, not from any real error signal; that is one
  problem showing up in two places, not two separate ones.
- Should projections, a boost-regime indicator (zero-boost vs. live, directly
  relevant starting week 2), or a model-confidence signal be exposed now
  that week 1 is real production experience rather than speculation? The
  original omission was a deliberate choice; re-evaluate it with real usage
  in hand instead of assuming it still holds.
- Accessibility, mobile rendering, and load performance: unverified as of
  this brief. Audit for real rather than assuming either good or bad.

## Model and pick investigation items from the week 1 retro

Worth digging into tonight, not just logging:

- Zero defensive players were picked all week. Check whether that is a
  legitimate value-driven outcome under the current maximize-expected-Total-
  Value objective (`nfl_oracle.valuelaw.model`'s fitted coefficients already
  show defensive value labels running generally lower than skill-position
  labels), or a real pool/feature bug silently excluding defensive
  candidates from consideration.
- Chalk (favorite) picks on Sunday were reportedly wrong even pre-boost,
  the exact regime where STATUS.md's own historical archive analysis says
  the serious field should converge and the obvious picks should be the
  easiest to get right. Investigate whether this points to a live
  prediction-path bug distinct from the Sunday freeze crash, rather than
  attributing it to noise.
- No model changes have landed since Monday. Cross-check against the
  model-TTL risk already on record (issue #156): confirm whether
  `fix/156-force-retrain` has actually merged and a real retrain has run,
  before treating the currently deployed model as current.

## Execution environment

All of this work happens in or through the GitHub Codespace
(`orange-system-4jx77wj6jvg6cq4gq`), not a separate local checkout, per root
`AGENTS.md`: the Codespace is the canonical development environment and the
home for this repo's GitHub auth. Whatever this session's own mechanism is
for reaching a Codespace (an SSH/exec tool, an attached checkout, or simply
operating from inside it directly), route actual git/test/lint/push commands
there rather than in an independent local clone, so state stays on the one
canonical checkout.

## Parallelization

The three fronts (week-close job + boost handling, the model/pick
investigation items, and the frontend audit and refresh) are largely
independent of each other and of similar size. Spawn subagents to work them
in parallel rather than serially through one thread, each grounded in the
relevant section of this brief and the linked drive/ docs, syncing back
through the same Codespace checkout so their commits land on real, current
state rather than diverging copies.

## Process

- Find or create one GitHub issue per the portfolio's "Start every task"
  rule before material work; this brief's scope likely spans several
  issues, not one. Link every branch, commit, and PR to its issue.
- `make write-path-check` before pushing.
- Do not touch `fix/156-force-retrain` if it is still an active branch
  someone else is working; check first.
- Every actual model, infra, or frontend change goes through the normal
  issue to branch to PR to review to merge flow. Given the scope, prioritize
  landing a few things for real over attempting everything shallowly.

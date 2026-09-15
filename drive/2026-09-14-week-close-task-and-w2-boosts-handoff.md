# NFL week-close task design + week-2 boost handling

Status: ready
Created: 2026-09-14
Owner: operator (handed off from a Claude Code session; intended for a fresh
chat/agent session to execute, per the operator's request to design this
here but implement it elsewhere)

## Context: what prompted this

A Claude Code session this week found that the real week 1 Sunday slate
(2026-09-13, 13 games) produced zero picks: the T-40 freeze refused three
times and the frontend showed "PICKS ARE UNAVAILABLE." Root cause (a
pool-completeness denominator measured against every game of the day instead
of only games that had not kicked off) is fixed in
[PR #158](https://github.com/cheeksmagunda/sports/pull/158), tracked in
[issue #156](https://github.com/cheeksmagunda/sports/issues/156), which is
still open with real acceptance items beyond the code fix. That investigation
surfaced two follow-on needs, both scoped here.

Read `AGENTS.md` (root) and `nfl-oracle/AGENTS.md` first; this brief adds to,
does not replace, that process (issue-first, write-path-check, PR review).

## Task 1: design a recurring "week-close" job

**Purpose:** weekly, not daily, analysis that looks at the whole week's
performance (all slates, not one day) and produces a concrete, prioritized
set of model and infrastructure improvements, distinct from the existing
daily `nfl-dayclose.yml` (which grades one day's frozen lineup against
finalized results and is already live).

**Trigger:** one hour after the final game of the week's final slate ends
(commonly Monday Night Football, but flex scheduling, Thursday-only bye
weeks, and international/extra games mean "final slate" must be derived from
the actual week's schedule, not hardcoded to Monday). A fixed cron cannot
know exact game-end time (game length varies), so mirror the existing gate
pattern:

- `nfl-oracle/scripts/nfl_dayclose_gate.py` already does a session-free
  public-nflverse schedule check for day-close. Extend this pattern (or add
  a sibling `nfl_weekclose_gate.py`) to determine, from
  `data/schedule/schedules.csv` (already in-repo, nflverse/nfldata, 24
  seasons committed), which game is the current week's last kickoff, then
  gate on that specific game's real completion (final status, not just
  kickoff + assumed duration) plus a 1-hour buffer.
- A GitHub Actions workflow (sibling to `.github/workflows/nfl-dayclose.yml`)
  polling on a schedule tight enough to catch the actual end of a
  late-running MNF game (e.g. every 15-30 min in a plausible end window)
  rather than a single fixed daily time, using the existing
  `.github/actions/dayclose-ledger` composite action pattern for
  posting results, and `oracle_core.dayclose.run_sweep`-style catch-up
  semantics (isolate one week's failure from the next) if useful.

**What the job should produce:** not silent model/code changes. Per this
repo's own process (root `AGENTS.md`: issue-first, PR review, no unreviewed
production changes), the job should:

1. Pull the week's actual results: which slates froze vs. did not (see the
   results ledger, [issue #143](https://github.com/cheeksmagunda/sports/issues/143),
   which already showed most of week 1 came back `no_freeze` due to the bug
   above), and for slates that did freeze, compare the committed lineup
   against the hindsight-best legal lineup using the already-built,
   already-tested `nfl_oracle.replay.harness` (`hindsight_best_lineup` /
   capture-ratio logic; see STATUS.md's "Value law decoded and replay
   harness verified" section for the exact numbers this harness already
   reproduces: 61.1% mean capture from a real walk-forward backtest, vs.
   79.9%/97.5% winner-capture figures that are the argmax of 12,000+ entries
   and not comparable to a single recommendation).
2. Pull the week's infrastructure incidents: worker crashes, gate refusals,
   TLS/exit-code issues, anything in the day-close results ledger or the
   Railway worker logs that indicates a reliability problem, not a model
   problem.
3. Open or update a single tracking issue (do not create a new markdown
   ledger; this repo's convention is "decision rationale belongs in issues,
   PRs, tests, code comments, or commits") with a prioritized punch list:
   model-quality findings separated from infra findings, each concrete
   enough to become its own issue/PR. Treat this as generating the *inputs*
   to improvement work, not a substitute for the normal issue -> branch ->
   PR -> review -> merge flow for any actual model or code change.

**Known related, still-open acceptance items from issue #156** worth folding
into this job's design rather than duplicating in a new tracker:
- Model TTL vs. NFL-week cadence: model trained 2026-09-09, `model_max_age_days=8`.
  Thursday 2026-09-17 TNF clears the freeze gate with only ~5m25s of margin;
  Sunday 2026-09-20 would refuse outright (10.7 days stale) without a retrain
  landing first. `fix/156-force-retrain` (a separate, already-in-flight
  branch as of this writing) addresses the retrain mechanism itself; the
  week-close job should verify a fresh retrain actually happened each week,
  not perform the retrain itself.
- No alerting when T-40 passes with no freeze (currently a human has to load
  the page to notice).
- No per-slate results capture built specifically for a weekly audit yet
  (this task IS that capture + audit, formalized and scheduled).

## Task 2: week-2 card boosts are live; verify/upgrade the pick path

**Why this matters now:** per `nfl-oracle/STATUS.md` ("Card boosts are
provider-assigned and absent in week 1"), boosts are confirmed all-zero for
the whole of week 1 and switch on at week 2 Thursday with a full 0.1-3.0
spread (verified against 91 real finalized contests). Week 2's Thursday
game is 2026-09-17. **Before that game, verify the live pick path is
boost-aware, not just zero-boost-aware** - this is explicitly listed as a
still-open acceptance item on issue #156 ("Boost regime transition (week 2
onward) verified before TNF").

**What is already boost-general (verify, do not assume further work is
needed here):**
- `nfl_oracle/recommendations/optimizer.py` implements
  `score = value * (slot + boost)` generically and uses `scipy.optimize.milp`
  exact search (bounded beam search fallback) per STATUS.md's freeze-path
  audit - this is the actual live production optimizer and reads as already
  general-purpose, not zero-boost-only. Confirm this with a live-boost
  integration test before trusting it in production, since STATUS.md also
  notes the optimizer "does not emit a rearrangement-inequality proof
  alongside its output" - it should be provably optimal by construction when
  milp runs, but that claim has not been tested against a real non-zero
  boost table end to end, only reasoned about.
- `nfl_oracle/replay/harness.py`'s `hindsight_best_lineup` already correctly
  handles the general boosted case (it was rewritten specifically to fix a
  zero-boost-only bug; see STATUS.md's "Bug found and fixed during this
  build" note) via the rearrangement-inequality decomposition: the
  optimal five reduces to a linear-time DP over the value-sorted pool
  regardless of boost. This is a good reference implementation/spec to
  diff the production optimizer's behavior against.

**What is confirmed zero-boost-only and needs real work, not just
verification:**
- `nfl_oracle/valuelaw/project.py` - STATUS.md describes it as returning
  "zero-boost slot recommendations in descending projected value." This is
  explicitly not correct once boosts are non-uniform (descending projected
  *value* order is only optimal for slot assignment when boost is equal
  across the five; the correct approach is descending order on
  `value * (something involving boost)` per the same rearrangement logic
  used in the replay harness, or simply: assign slots by descending value
  among the *chosen* five, as before, but select the five to maximize total
  score under real per-candidate boosts, which is a different (and harder)
  combinatorial problem than picking the top-5 by raw value).
- `nfl-oracle`'s manual/backup drafting script `full_pool_draft.py` was
  changed in PR #158 to **refuse outright once card boosts are live** rather
  than compute a correct boost-aware pick - a deliberate, documented safety
  gate ("descending projected value is optimal only under the zero-boost
  regime"), not a bug, but it means the manual fallback path has no working
  substitute once week 2 starts. Decide and build one: either reuse the
  production `optimizer.py` path for the manual script too (likely the
  right move, avoids maintaining two optimization implementations), or give
  it its own boost-aware selection logic mirroring the replay harness.
- Separately, STATUS.md's freeze-path audit lists a real, still-open gap:
  `nfl_oracle.contests.boosts.BoostObservation.all_zero` exists and is
  correct but "is never imported by `recommendations/`; the optimizer
  accepts whatever `card_boost` values a candidate carries with no explicit
  zero_boost-vs-published classification recorded on the frozen artifact."
  Wire this in so a frozen recommendation's artifact explicitly states which
  boost regime it ran under - this is cheap, high-value observability for
  exactly the transition happening this week, and directly closes the
  matching item on issue #156.

**Suggested acceptance check for this task:** a live or realistic-fixture
integration test with a real (non-uniform, non-zero) boost table, asserting
(a) `optimizer.py`'s chosen five-card lineup with committed slot order
matches the brute-force/DP optimum from the replay harness's approach on the
same candidate pool, (b) the frozen artifact records which boost regime
(`zero_boost` vs `provider_boosts_present`) it ran under, and (c) the manual
fallback path (`full_pool_draft.py` or its replacement) produces a correct
boost-aware pick instead of refusing, before 2026-09-17 Thursday kickoff.

## Process reminders for whoever executes this

- Read `AGENTS.md`, `nfl-oracle/AGENTS.md`, and current `nfl-oracle/STATUS.md`
  first; this brief is a snapshot from 2026-09-14 and STATUS.md will have
  moved on (check whether `fix/156-force-retrain` has merged, whether #156's
  remaining items have closed, etc.) before treating anything here as still
  open.
- Find or create one GitHub issue per the portfolio's "Start every task" rule
  before material work; link commits/PR to it.
- `make write-path-check` before pushing.
- Do not touch `fix/156-force-retrain` if it is still an active branch
  someone else (a Codex session, as of 2026-09-14) is working - check first.

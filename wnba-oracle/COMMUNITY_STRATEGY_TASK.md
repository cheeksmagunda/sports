# Community/Field Strategy Calibration — Copilot Task

## Why this exists

`MODEL_PICK_POSTMORTEM_2026-08-28.md` (read that first) investigated a
real-money lineup that scored 29.92 and placed 6384th of 6800 in a
declining-multiplier "Draft" contest. Verdict: the *predictions* were fine —
4 of 5 rostered players landed at or above their own model-predicted median.
The failure, to the extent there is one to chase, is downstream of
prediction quality: how accurate per-player projections get turned into a
5-player lineup for **this specific contest mechanic** (fixed descending
slot multipliers `2.0/1.8/1.6/1.4/1.2`, `card_boost` dominating the visible
multiplier, a 6,800-entrant field where beating the top of the leaderboard
(59-62 pts) requires several players *simultaneously* beating their own
ceiling, not just hitting median — see the postmortem's §4 for the full
argument, including why raw multiplier size is a misleading confidence
signal here).

The operator's framing, which this task is scoped around: the model-research
-benchmark sweep (separately running/queued, see `BENCHMARK_TASK.md`) tests
whether internal knobs improve outcomes *against our own predictions replayed
through box scores*. That answers "is our simulation self-consistent." It
does not answer "what does the actual competitive field do, and does it
differ from what we assume." This task is about that second, currently
unused axis: **we have three-plus months of real top-20 finisher data
already sitting in our own database, collected and unused for this
purpose.** Use it.

## What already exists — build on this, don't rebuild it

Read these before writing anything:

- **`contest_leaderboards`** (`wnba-oracle/migrations/versions/20260527_0003_contest_leaderboards.py`):
  one row per (contest_id, entry_id) for **every finalized contest since
  2026-05-27** — top-20 finishers only, but that's ~3 months of slates.
  Columns: `slate_date`, `rank`, `paged_rank`, `user_id` (the platform's
  opaque per-user slug — **stable across slates**, so repeat top-20 finishers
  are identifiable), `score`, and `lineup` (JSONB, verbatim from the
  platform's `/entries` endpoint: each of the 5 picks' `playerId`,
  `multiplier`, `multiplierBonus` (= card_boost), `value` (= realized
  raw score), `displayName`, team). Read via
  `wnba_oracle/src/wnba_oracle/db/reads.py::read_leaderboards`.
- **`wnba_oracle/src/wnba_oracle/picker/popularity.py`**: an existing
  draft-popularity/ownership estimator + "contrarian adjustment" (ported
  from a prior NBA project, citing a -0.457 correlation between draft
  popularity and realized boost). Prefers *measured* draft counts
  (`slate_labels.drafts`, captured pre-lock) over the heuristic when
  available.
- **`wnba_oracle/src/wnba_oracle/picker/field.py`**: ownership/field
  modeling with an explicit documented finding (D86) that estimating the
  competitive field from our *own* projections creates a feedback loop —
  the model ships chalk it likes, the real field also owns that chalk
  heavily, and the lineup finishes mid-pack. This is the same failure mode
  this task is chasing at the lineup-construction level, already solved once
  at the ownership level — check whether the same lesson generalizes.
- **`wnba_oracle/src/wnba_oracle/picker/optimize.py`**: `leverage_weight`,
  `ceiling_weight`, `duplication_weight` are real, wired-in objective terms
  (not aspirational) — `leverage = mean(-log(ownership))` over the 5 picks,
  rewarded when `leverage_weight > 0`. Confirm their actual production
  values (`Settings` in `wnba_oracle/src/wnba_oracle/common/settings.py`,
  and/or `model_provenance.serving_knobs` on a recent `frozen_lineups` row)
  before assuming they're on, off, or at what strength.
- **`wnba_oracle/src/wnba_oracle/ingest/contest_stats.py`**:
  `fetch_contest_stats` pulls three community-aggregate sections per contest
  — `highestBoostedValuePlayers`, `popularPlayers`, `mostCommon3xPlayers` —
  directly from the platform. Check whether these are persisted anywhere
  beyond transient use in the backfill/label pipeline; if not, that's a
  second underused data source worth capturing going forward (lower
  priority than the analysis below, which doesn't need it).
- **`committed_order_objective`** (`picker/optimize.py`), currently `False`
  in production: biases *selection* toward high-dispersion/volatile
  players. A prior 50-slate internal-simulation test was inconclusive
  (t=1.36, 95% CI [-0.459, 2.540]). This task's empirical field data is a
  second, independent way to get evidence on whether that bias matches or
  fights what actually wins.

## The task

Using `contest_leaderboards` (and `slate_labels` for our own side, where
useful) across its full available date range, build an empirical answer to:
**what do lineups that actually finish well in this contest do, and does our
current lineup-construction policy match or fight that?** Concretely,
answer as many of these as the data supports (drop ones the data can't
support rather than forcing a weak answer):

1. **Ownership/leverage validation.** For rostered players in
   `contest_leaderboards.lineup`, cross-reference against
   `slate_labels.drafts` (measured ownership) where available. Do top-20
   entries skew toward lower-ownership players relative to the full slate
   pool, and does the skew get stronger as rank improves (1st vs. 15th)?
   This is a direct empirical check on `popularity.py`'s ported -0.457
   correlation claim — does it hold in *our* data, at *our* contest's field
   size, or is that number specific to the NBA project it was ported from?
2. **Slot/card_boost pattern at the top of the leaderboard.** Across all
   captured top-20 entries, characterize how slot placement (which
   `slot_base` a player lands in) relates to `card_boost` and realized
   `value`. Does the field's winning behavior look more like p50-optimal
   ordering, p90/ceiling-tilted ordering (our current default,
   `ceiling_tilt_slots=True`), or something else? The postmortem's §4 has
   the exact method for this (`rearrangement_inequality`,
   `hindsight_max_score` in `eval/contest_score.py`) — apply it across the
   corpus, not just the one 2026-08-28 slate.
3. **Repeat top-20 `user_id`s as a "smart money" signal.** Identify
   `user_id`s appearing in the top 20 across multiple slates. Do their
   picks differ systematically from one-time top-20 finishers (e.g., lower
   average ownership, more/less stacking, different card_boost usage)? If a
   detectable, stable pattern exists, that's a candidate signal worth
   surfacing — but only report it if it survives an honest look at sample
   size and multiple-comparisons risk. Absence of a pattern is a valid,
   useful finding.
4. **`committed_order_objective` and `duplication_aware_payout`, re-examined
   against real field behavior**, not just internal simulation. Does the
   empirical field's own duplication rate on high-`value` players match
   what `duplication_weight` currently assumes? Does the volatility bias
   `committed_order_objective` would introduce match or fight what
   (1)-(3) show about what actually wins?
5. **`payout_regime='top_20'` vs. field dynamics.** The postmortem noted
   that beating every pick's own median projection nets ~32.7 points
   against this leaderboard's ~59-62 to lead — quantify that gap properly
   across the full corpus (not one slate) and characterize what percentile
   of *our own* simulated score distribution would need to be hit to
   realistically finish top-20 or win outright, historically.

## Constraints

- **Read-only.** This is corpus analysis against already-collected data —
  no live scraping needed, no writes to any production table.
- **Evidence-gated recommendations only.** If the data clearly supports a
  specific config change (a knob value, a new signal wired into the
  optimizer), propose it as a normal PR with the supporting numbers cited
  inline — don't ship a knob flip on vibes, and don't manufacture a
  recommendation if the data is genuinely inconclusive on a question (say
  so; that's a legitimate finding, matching how the postmortem and the
  prior 50-slate `committed_order_objective` test were both honest about
  inconclusive results).
- **Do not touch**: `starter_unknown_fade`, the `discover_wnba_contest_id`
  / `top_cid` window logic in `job_dayclose.py`, or anything in the
  placement-capture path — all separately handled or under separate
  investigation.
- **Do not auto-deploy.** Normal PR review and CI apply; nothing here
  should reach production without the operator's review, since it
  ultimately affects real-money entries.
- If useful, this analysis can and should run **before** the
  model-research-benchmark sweep's results land — the two are
  complementary (internal simulation vs. real field behavior), not
  sequential dependencies.

## Deliverable

A written analysis (suggested: `wnba-oracle/COMMUNITY_STRATEGY_FINDINGS.md`,
mirroring `MODEL_PICK_POSTMORTEM_2026-08-28.md`'s evidence-and-citation
style — exact tables/columns/files referenced, confidence levels stated,
what couldn't be answered listed explicitly) plus, only where the evidence
clearly supports one, a PR with the specific config or code change and its
supporting numbers.

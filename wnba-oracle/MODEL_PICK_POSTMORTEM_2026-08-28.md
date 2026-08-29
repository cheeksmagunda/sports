# Model Pick Postmortem — 2026-08-28 Slate

Investigation scope: read-only. Live production Postgres was queried via
`scripts/with-secrets wnba-oracle -- scripts/auth-check wnba-oracle --live`
(which reported `database` capability present) and a corrected, explicitly
read-only (`default_transaction_read_only=on`) SQLAlchemy connection using
`DATABASE_PUBLIC_URL`. No writes were made; no workflow was dispatched; no
fix was implemented.

## Summary verdict

The causal link is confirmed exactly, not just plausibly: the frozen
`frozen_lineups` row for 2026-08-28 (id=85, `model_sha=94f8e860…`, frozen
2026-08-28 22:52:53 UTC) reconstructs all five entered multipliers to the
decimal via the platform's own documented rule
(`slot_base + card_boost`), so this lineup is unambiguously the system's
output. The outcome was driven almost entirely by **which two of the five
rostered players had bad on-court games** (T. Fágbénlé, C. Leger-Walker),
not by slot/multiplier misassignment and not by `starter_unknown_fade`.
Recomputing the actual lineup with the best possible *hindsight* slot
reordering (same 5 players, optimal order) gains only ~0.14 points out of
~29.5 — slot assignment left almost nothing on the table. `starter_unknown_fade`
never touched any of the 5 rostered players' predictions: all five carried
`is_starter=1` in `job1_enrichment` and were therefore routed through the
"expected starter" branch (+10% multiplier), never the "unknown" branch the
fade knob controls. Separately, the task's own background hypothesis about
that knob has the direction backwards: a fade of 0.75 (< 1.0) *suppresses*
unknown-role predictions relative to the neutral 1.0, making the system
*more* cautious about rostering unknowns, not more willing — moot here since
it wasn't in play, but worth correcting. Four of five players' realized raw
scores landed at or above their own model-predicted p50, or (Fágbénlé)
almost exactly at the model's own p10 — i.e. within the uncertainty band the
system itself had already assigned them. The system's own pre-game EV
estimate for this lineup was already lukewarm (`expected_payout=1.065`,
`entry_recommendation='enter_with_caveat'`), so this reads as **defensible
variance around an already-hedged, marginal bet**, with one genuine
open structural question (below) that this single slate cannot resolve.

## 1. Causal link: CONFIRMED (exact, not approximate)

`frozen_lineups` for `slate_date = 2026-08-28`: exactly one row (append-only
table; `freeze_seq=1`, `frozen_via='job2_first_fire'`, `operation_key='first'`,
`payout_regime='top_20'`, `entry_recommendation='enter_with_caveat'`,
`expected_payout=1.065`). Its `lineup` JSONB lists, in order, Diamond Miller,
Isabelle Harrison, Megan DiLeo, Temi Fágbénlé, Charlisse Leger-Walker — the
same 5 players, same order implied by the task's multipliers.

`wnba_oracle/src/wnba_oracle/eval/contest_score.py` documents the verified
platform rule (D42, re-verified 2026-08-19 against real leaderboard
captures): `multiplier == slot_base + card_boost`, with
`DEFAULT_SLOT_BASES = (2.0, 1.8, 1.6, 1.4, 1.2)`. Applying that formula to
the frozen row's stored `slot_multipliers` (`[2.0,1.8,1.6,1.4,1.2]`, positionally
paired with `player_ids`) and each player's frozen `card_boost` reproduces
**all five** entered multipliers exactly:

| Slot | Player | slot_base | card_boost | slot_base+card_boost | Entered multiplier (task) |
|---|---|---|---|---|---|
| 0 | Diamond Miller | 2.0 | 2.2 | **4.2** | 4.2x ✓ |
| 1 | Isabelle Harrison | 1.8 | 1.0 | **2.8** | 2.8x ✓ |
| 2 | Megan DiLeo | 1.6 | 1.0 | **2.6** | 2.6x ✓ |
| 3 | Temi Fágbénlé | 1.4 | 2.6 | **4.0** | 4x ✓ |
| 4 | Charlisse Leger-Walker | 1.2 | 2.0 | **3.2** | 3.2x ✓ |

This is about as strong as causal-link evidence gets short of the operator's
own screenshot. There is no scenario in the data consistent with "manual
entry, not sourced from the system."

## 2. Per-player: prediction vs. real outcome

Box scores are from `wnba_game_logs` (nba_api-sourced, real per-game data,
independently keyed by `game_date=2026-08-28`). Predictions are the frozen
payload's `pred_real_score_{p10,p50,p90}` (post-copula/mixture-variance
sampling values that fed the actual slot-assignment decision — see §4 on
`ceiling_tilt_slots`).

| Player | card_boost | Model p10 / p50 / p90 | Actual raw (task) | Actual box score | Verdict |
|---|---|---|---|---|---|
| D. Miller | 2.2 | 0.57 / 2.07 / 8.16 | 2.9 | 20.3 min, 19 pts, 3 reb, 2 ast, 1 TOV (CON vs IND) | Above median, within band. Good process, good result. |
| I. Harrison | 1.0 | 1.06 / 2.19 / 6.85 | 2.3 | 24.3 min, 15 pts, 7 reb, 4 ast, 1 stl, 4 TOV (TOR vs LVA) | Essentially at median. Textbook expected outcome. |
| M. DiLeo | 1.0 | 1.00 / 2.04 / 6.41 | 2.6 | 26.7 min, 16 pts, 5 reb, 1 TOV (POR vs ATL) | Above median, within band. |
| T. Fágbénlé | 2.6 | **0.40** / 1.41 / 5.71 | 0.4 | 20.5 min, **0 pts**, 6 reb, 0 ast, 3 TOV (TOR vs LVA) | Landed almost exactly on the model's *own* p10. The model already rated her the lowest-confidence, highest-variance pick of the 5 (lowest p50, `archetype="leverage_spike"`, p90/p50 ratio ~4x). **Defensible variance** — the downside was already priced in; it just hit. |
| C. Leger-Walker | 2.0 | 0.90 / 2.16 / 5.83 | 0.8 | 24.4 min, 8 pts, 4 reb, 5 ast, 1 stl, **7 TOV** (CON vs IND) | ~11% below the model's own p10. A turnover-driven inefficiency game beyond the modeled downside, but n=1 — not enough by itself to indict calibration. |

Minutes context for all 5 vs. their own trailing 5/10/20-game averages
(from `job1_enrichment.features_json.head_features`): none show a
late-scratch, DNP, or meaningful minutes cut. Fágbénlé's 20.5 minutes was
*above* her l10/l20 averages (15.75 / 17.04). Leger-Walker's 24.4 was
in-line with her averages (25.1–26.9). **Both busts were pure on-court
production/efficiency outcomes (0-point scoreless night; 7-turnover game),
not availability, role, or blowout-garbage-time failures.** (Harrison
carried an `injury_status="GTD"` tag at capture time and also played a full,
normal workload — another instance of a pre-game flag that didn't translate
into a real availability event.)

Arithmetic check: `sum(raw_i * (slot_base_i + card_boost_i))` using the
task's rounded raw scores = 29.54, close to the reported 29.92 (the gap is
consistent with the task's raw scores being rounded to 1 decimal; the
platform's real per-player `value` almost certainly carries more precision).

## 3. `starter_unknown_fade`: did not contribute

Exact code path checked (not inferred from the commit message), in
`wnba_oracle/src/wnba_oracle/modeling/scoring.py:59-99`:

```python
def _effective_confirmed(f: dict, *, use_expected: bool) -> bool:
    if int(f.get("rotowire_confirmed", 0) or 0):
        return True
    return use_expected and bool(int(f.get("is_starter", 0) or 0))

def _starter_multiplier(features_json, *, enabled, use_expected=True, unknown_fade=1.0) -> float:
    if not enabled:
        return 1.0
    f = _features_dict(features_json)
    if not _effective_confirmed(f, use_expected=use_expected):
        return unknown_fade
    return 1.10 if int(f.get("is_starter", 0) or 0) else 0.82
```

`unknown_fade` (the knob calibrated 1.0 → 0.75 in commit `1840cad`) is
returned **only** when `_effective_confirmed()` is False, i.e. only for
players with `rotowire_confirmed=0 AND is_starter=0`. Pulling
`job1_enrichment.features_json` for all 5 rostered players
(`slate_date=2026-08-28`) shows **all five had `is_starter=1`**:

| Player | is_starter | rotowire_confirmed | Branch taken |
|---|---|---|---|
| D. Miller | 1 | 1 | confirmed starter → ×1.10 |
| I. Harrison | 1 | 0 | expected starter (via `use_expected=True`) → ×1.10 |
| M. DiLeo | 1 | 1 | confirmed starter → ×1.10 |
| T. Fágbénlé | 1 | 0 | expected starter (via `use_expected=True`) → ×1.10 |
| C. Leger-Walker | 1 | 1 | confirmed starter → ×1.10 |

None fell into the `is_starter=0 AND rotowire_confirmed=0` "unknown" bucket
the fade governs. `starter_unknown_fade=0.75` was confirmed active in this
exact freeze (`model_provenance.model_policy.starter_unknown_fade: 0.75` in
the frozen JSONB), but it had **zero effect on any of the 5 rostered
players' predictions** — the knob simply never fired for this lineup.

One correction to the investigation's starting premise: the background text
asserted the 1.0→0.75 change "relaxed the system to be MORE willing to
roster players with uncertain starter/role status." The opposite is true —
a multiplicative fade below 1.0 *suppresses* an unknown player's predicted
score (the settings.py comment says it explicitly: "pushes DNP-prone role
players down the stage-1 rank"), so the calibration made the system *more*
cautious about unknowns, not less. This doesn't change the conclusion (the
knob wasn't in play either way for these 5 players), but the causal story
in the background material doesn't hold up on its own terms independent of
that.

Checked and resolved: `job_runs` shows `job1late` fired repeatedly and
successfully on 2026-08-28 (16:00, 16:30, 17:01, 17:32, 18:01 UTC, all
`status='success', exit_code=0`, and presumably more through the 22:52 UTC
freeze at its ~30-minute cadence). It was not a failure to re-scrape —
Harrison/Fágbénlé's `job1_enrichment.captured_at` simply never advanced past
the initial 13:09:38 UTC value because their game's tip (02:00 UTC the next
day) is well after the *freeze* time (22:52 UTC, timed to T-40 of the
slate's *first* tip at 23:30 UTC, not its last). RotoWire confirmation for a
02:00 UTC game is not expected to exist yet at a 22:52 UTC freeze regardless
of how many times `job1late` polls. This is an expected consequence of
freezing once at T-40-of-first-tip on a multi-game slate, not a malfunction,
and it did not change the real-world outcome (both players played normal
minutes).

## 4. Format-alignment: the system models this exact contest mechanic — in depth

This is **not** a case of a salary-cap GPP optimizer misapplied to an
unrelated confidence-draft format. There is no "salary" concept anywhere in
the codebase (`grep -ri salary` returns nothing). The system has an
extensively developed, empirically-verified model of precisely this
mechanic:

- `picker/optimize.py`, `picker/sample.py`, `eval/contest_score.py`, and
  `picker/payout.py` all encode `DEFAULT_SLOT_MULTIPLIERS = (2.0, 1.8, 1.6,
  1.4, 1.2)` — "the platform fixes 5 descending slot multipliers and the
  user only chooses which player goes in which slot," verified against a
  320-entry real leaderboard corpus (D42) and re-verified 2026-08-19.
  `eval/contest_score.py` is deliberately written to NOT import from
  `picker`, specifically so a slot-assignment bug in production code can't
  hide from its own backtest.
- The optimizer **does** decide per-slot multiplier assignment — this is
  not the operator's manual guess and not a naive "sort by projection"
  default applied blindly. It is `rearrangement_inequality` applied to
  either the median (p50) or, when `ceiling_tilt_slots=True` (confirmed
  active in this freeze's `model_provenance`, a shipped D107/Phase-4
  default "validated with two years data"), the **p90 (ceiling)** of each
  chosen player's joint Monte Carlo sample distribution
  (`picker/optimize.py:992-999`). This slate's actual slot order matches a
  p90-descending sort almost exactly (Miller 8.16 > Harrison 6.85 > DiLeo
  6.41 > Leger-Walker 5.83 > Fágbénlé 5.71) — the one inversion (Fágbénlé's
  slot vs. Leger-Walker's, a 5.71-vs-5.83 near-tie) is well within Monte
  Carlo sampling noise at `n_samples=1000` and does not indicate a bug. This
  is a deliberate EV trade documented in `eval/contest_score.py`'s own
  `ev_optimal_order` (p50-based) vs. the shipped p90-tilt: sacrifice a
  sliver of expected value for more upside under a convex payout curve.

- **The structural finding**: the *number* a human reads off the leaderboard
  as "confidence" (e.g., 4.2x, 4x) conflates two things of very different
  character: a system-controlled slot component that only ranges 1.2–2.0
  (a spread of 0.8), and `card_boost` — a fixed, platform-assigned,
  per-player-per-card attribute the optimizer does not choose (it only
  chooses whether to roster that player at all) that ranges 0–3.0 across the
  slate (several players on Fágbénlé's own team alone showed `card_boost=3.0`).
  Card_boost dominates the observed multiplier's magnitude. This defuses the
  task's own diagnostic framing ("top entries put their biggest performers
  at LOW multipliers, we did the opposite"): C. Clark shows a *constant*
  2.1x across three different top-6 entries in the task's leaderboard
  excerpt — consistent with being placed in the **top** slot (2.0 base) by
  every one of them, plus a small, fixed card_boost (~0.1). Her multiplier
  *looks* low only because her card_boost is tiny, not because winners
  deprioritized her. Reading multiplier magnitude as a confidence signal,
  the way the task's background material does, is not a reliable diagnostic
  on this platform.

- **Quantified: slot order was not the problem.** Recomputing our own
  entered lineup's score under the *hindsight*-optimal slot order (same 5
  players and card_boosts, reordering only the slot_base assignment by
  realized value, per `eval/contest_score.py:hindsight_max_score`) yields
  29.68 vs. the actual 29.54 (both using the task's rounded raw scores) —
  a headroom of **~0.14 points, ~0.5%**. Essentially no value was left on
  the table by slot assignment. The lineup was already very close to its
  own best achievable ordering given these 5 players. The deficit versus
  the leaderboard is a **player-selection** story, not a
  confidence-ranking story.

- **Secondary observation (context, not a cause of this outcome):**
  recomputing the lineup at every player's own predicted p50 (i.e., "nothing
  goes wrong") gives ≈32.7 points, versus ≈59–62 for the task's top-6
  leaderboard entries. Competing near the top of a 6,800-entrant field in
  this scoring format appears to require several players *simultaneously*
  beating their own ceiling estimates, not just hitting median — a
  structurally variance-hungry format. `payout_regime='top_20'` (mildly
  convex, cash line at the 20th percentile) is a much more conservative EV
  posture than that dynamic might reward. This is a real calibration
  question worth a dedicated look, but it does **not** explain this specific
  outcome: the actual finish (6384/6800) is so far outside any reasonable
  cash line that no regime choice would have salvaged it — the two
  player-level busts are sufficient explanation on their own.

- One genuine, separately-flagged, currently-active knob worth naming:
  `committed_order_objective` (`picker/optimize.py:313-331`) defaults to
  `False` in production (`build_optimize_config` in `scheduler/job2.py`
  does not override it, and `model_provenance` confirms `false` for this
  freeze). In this mode, the **selection**-stage EV objective (which of the
  ~122-player pool becomes the 5 rostered players) scores each Monte Carlo
  draw by re-ranking slot assignment *within that draw* — "an objective no
  entrant can realize... which flatters high-dispersion lineups most,
  biasing selection toward volatility" (the code's own comment). Fágbénlé
  (archetype `leverage_spike`, a ~14x p10-to-p90 spread) is exactly the
  kind of player this objective would overvalue relative to a
  `committed_order=True` objective. A prior 50-slate measurement of
  flipping this knob was inconclusive (mean +1.04, sd 5.41, t=1.36, 95% CI
  [-0.459, +2.540], "NOT shipped — the interval includes zero"). I did not
  re-run the optimizer counterfactually for this slate (out of scope for a
  read-only investigation), so I cannot say whether Fágbénlé specifically
  would have been excluded under `committed_order=True`. This is a
  plausible, but unproven for this slate, contributor to player selection.

## 5. Process error vs. defensible variance — classification

| Element | Classification | Evidence |
|---|---|---|
| Causal link (system → entry) | N/A (fact, confirmed) | Exact multiplier decomposition, §1 |
| Fágbénlé's 0-point game | **Defensible variance** | Landed at the model's own p10; normal minutes; model already flagged her as its lowest-median, highest-variance pick |
| Leger-Walker's 7-TOV game | **Defensible variance, mild calibration flag** | ~11% below own p10; n=1, insufficient to indict; normal minutes |
| Miller / Harrison / DiLeo | **Good process, good-to-median result** | All landed at or above own p50 |
| `starter_unknown_fade` | **Not a contributing factor** | Concrete code path shows it never fired for any of the 5 (§3) |
| Slot/multiplier assignment | **Working as designed; immaterial to this outcome** | ~0.14-pt hindsight headroom (§4) |
| `committed_order_objective=False` | **Open structural question, medium confidence, unproven this slate** | Verified active; documented volatility bias; prior measurement inconclusive (§4) |
| `payout_regime='top_20'` vs. field dynamics | **Observation, not a cause of this outcome** | Deficit vs. leaderboard is too large to attribute to regime choice (§4) |
| Pre-game system self-assessment | **Context supporting "variance," not "process error"** | `expected_payout=1.065`, `entry_recommendation='enter_with_caveat'` — the system itself flagged this as a marginal bet before tip |

This is one slate. Per the task's own calibration bar (a 50-slate measurement
of a related knob was itself statistically inconclusive), a single-slate
result cannot support a confident process-error verdict on any of the
"open" items above, and this report does not attempt to force one.

## Candidate fixes (described only — not implemented)

1. **Re-measure `committed_order_objective=True` on the grown corpus.**
   Confidence: medium-low that it would help; medium that it's worth
   re-measuring. The code already prescribes the exact command
   (`scripts/lab.py variant --set committed_order_objective=True --last 0`).
   Raise confidence: a larger post-D88 corpus separates from zero in the
   same direction as the +1.04 preview. Lower confidence: it stays
   centered near zero or flips sign with more data (regression to the mean
   already happened once, per the code comment).

2. **Surface the card_boost/slot_base decomposition to the operator**,
   not just the combined multiplier, in whatever view/report the operator
   uses to decide entry. Confidence: high that this is cheap and correct;
   it directly prevents the "big multiplier = system confidence" misreading
   documented in §4. Low cost, no model risk (display-only). Raise
   confidence: confirm the operator's actual decision-time view only shows
   the combined multiplier today. Lower confidence: the frontend or
   operator workflow already surfaces `card_boost` separately somewhere
   (I did not check `wnba-oracle/frontend/` for this) — in that case the
   fix is redundant, not needed.

3. **Fix (or add) `entry_rank`/`entry_count` capture for non-top-20
   finishes.** Every visible historical `contest_placements` row (2026-08-23
   through 2026-08-27, the 5 most recent) has `entry_rank=None,
   entry_count=None` despite a populated `entry_score`. `contest_leaderboards`
   only ever ingests the platform's top-20 finishers per contest (per its
   own migration docstring), so an entry finishing 6384/6800 structurally
   cannot be found there. Confidence: high that this is a real, general
   instrumentation gap (not specific to this slate) — the system currently
   has no path to record where a below-top-20 entry actually placed, which
   means it cannot self-detect "are we chronically finishing in the bottom
   6%" across slates. Raise confidence further: check whether the Real
   Sports API exposes a "my entry" or full-field rank lookup distinct from
   the top-20 leaderboard endpoint `contest_stats.py` already calls. Lower
   confidence: if no such endpoint exists on the platform side, this is a
   real platform limitation rather than a fixable instrumentation bug, and
   the fix becomes "document the gap" rather than "add the capture."

4. **Reconsider single-freeze timing (T-40-of-first-tip) on multi-game
   slates.** Confirmed via `job_runs`: `job1late` fired repeatedly and
   successfully on 2026-08-28 (16:00, 16:30, 17:01, 17:32, 18:01 UTC, and
   presumably more through freeze), so this is not a re-scrape failure —
   Harrison and Fágbénlé's `job1_enrichment.captured_at` simply never
   advanced because their game's 02:00 UTC tip is hours after the 22:52 UTC
   freeze (tied to the *first* game's 23:30 UTC tip), well before RotoWire
   would plausibly confirm a lineup for the later game. Confidence:
   low-medium that changing this would help in general (D104's "expected"
   substitute is a deliberate, reasoned design choice, and it caused no
   harm this slate — both players played normal minutes). Raise confidence:
   find a slate where a later game's player was scratched/demoted between
   the single freeze and actual tip, i.e. a case where a per-game (rather
   than per-slate) freeze or a closer-to-tip re-evaluation would have
   changed the roster or slot order. Lower confidence: freezing later
   reduces the operator's own lead time to enter the contest, which may be
   a harder constraint than the confirmation-staleness risk it would fix.

## What could NOT be verified

- **The specific third-party leaderboard** in the task (mavrello, epicchang,
  redskiiin, phillyphilon, kiryukazuma4th, here4thehoops; 6800 entrants;
  our rank 6384) is **not yet in our own database**. `slate_labels`,
  `contest_leaderboards`, and `contest_placements` all return zero rows for
  `slate_date=2026-08-28`. The most recent `dayclose` run (2026-08-29
  06:01–06:02 UTC, `processed_slate_date='2026-08-28'`) came back
  **`status='degraded'`** with `placement_capture: {reason:
  'missing_labels_or_leaderboard', status: 'degraded'}` — the platform's
  own results/labels for this slate were not yet available at capture time.
  I corroborated the task's numbers only *indirectly*, via (a) the exact
  multiplier-decomposition match in §1 and (b) independently-sourced real
  box scores from `wnba_game_logs` that are consistent with the task's
  stated raw scores. I could not independently confirm the field size
  (6800), the specific competing usernames, or the exact rank (6384).
- **Whether rank 6384/6800 is typical or unusual for this system.** Even
  once `dayclose` succeeds, the last 5 successfully-captured
  `contest_placements` rows (2026-08-23 → 2026-08-27) all show
  `entry_rank=None` — see Candidate Fix #3. I cannot tell from our own data
  whether bottom-6% finishes are common or rare for this system in this
  contest type. `entry_score` history for those 5 days (21.6, 39.4, 43.7,
  28.8, 36.4) puts 29.92 mid-to-low-range but not an outlier *in score*,
  which is a different question from rank/percentile.
- **Whether `committed_order_objective=True` would have changed which 5
  players were selected this slate.** I verified the knob's current value
  and documented behavior but did not re-run the optimizer counterfactually
  (out of scope for read-only investigation; would also require
  reconstructing the exact ~122-player candidate pool and RNG seed state at
  freeze time).
- **Whether a `job1late`-style re-scrape ran and should have updated
  Harrison/Fágbénlé's confirmation status before freeze** — `job1_enrichment`
  shows no later update, but I did not check `job_runs` for a `job1late` row
  on this slate specifically.
- The `backups` branch fallback and the raw ingest-provider fallback were
  not needed — live read-only DB access via `scripts/with-secrets` worked on
  the first attempt (after correcting a stale absolute path baked into the
  local `DATABASE_PUBLIC_URL` secret's `sslrootcert` parameter, which pointed
  at `/Users/hanslarson/Desktop/wnba-oracle/.pgssl/server.crt` instead of
  this checkout's actual `/Users/hanslarson/Desktop/sports/wnba-oracle/.pgssl/server.crt`
  — noted here since it may bite the next person who runs this wrapper from
  this checkout).

---

# Follow-up — 2026-08-29: operator visibility (Task A) and dayclose diagnosis (Task B)

Scope: same read-only rules as above. No writes were made to the database at
any point (confirmed empirically — see methodology note under Task B). No
model/optimizer/picker/scoring code was touched. No commits, no pushes, no
workflow dispatch.

## Task A — does `entry_recommendation` / `expected_payout` reach the operator?

**Verdict: yes, already surfaced clearly, end to end. No code change made.**

Traced the full path:

- **DB**: `frozen_lineups` row id=85 carries `entry_recommendation='enter_with_caveat'`,
  `expected_payout=1.065` (as already established above).
- **API** (`wnba-oracle/src/wnba_oracle/api/lineup.py`): all three routes —
  `get_lineup` (`GET /lineup/{slate_date}`), `get_lineup_history`, and
  `list_recent_lineups` — explicitly `SELECT` and return both
  `entry_recommendation` and `expected_payout` (lines 33–34, 43–44, 75–76,
  106–107, 121–122). Nothing is dropped at the API layer.
- **Frontend types** (`frontend/src/lib/api.ts`): `FrozenLineup` (lines 69–83)
  and `SlateSummary` (lines 88–97) both declare `entry_recommendation` and
  `expected_payout` as required (non-optional) fields.
- **Fetch chain**: `fetchLatestLineup` (`api.ts:186`) →
  `useLineupData` (`frontend/src/hooks/useLineupData.ts`) →
  `useSlateLifecycle` (`frontend/src/hooks/useSlateLifecycle.ts`) →
  `PickerPage` (`frontend/src/pages/PickerPage.tsx`), which is mounted at the
  root route `/` (`frontend/src/App.tsx:16`) and is explicitly headed with the
  comment *"Morning view. Operator opens this once per day."*
- **Render** (`frontend/src/components/SlateBand.tsx`): renders
  `entry_recommendation` as a labeled, styled chip (lines 77–92; CSS classes
  `slate-band__chip--enter` / `--enter_with_caveat` / `--skip` confirmed
  present and non-trivial in `frontend/src/styles/partials/slate-band.css`)
  in **every** lifecycle branch — it is never conditionally hidden — and
  renders `expected_payout` as a distinct "Expected payout" stat specifically
  in the pre-tip / non-live branch (lines 128–145), i.e. exactly the decision
  window before an operator would manually key the lineup into the
  third-party contest.
- **Actionability layer** (`frontend/src/lib/actionability.ts`): computes
  whether the recorded recommendation is still actionable (lineup fresh,
  matches today, a production freeze path, picks not paused, before the
  effective lock, valid freeze timestamp) and labels it imperatively
  ("Enter now · Caveat") when so; every failure mode degrades gracefully to
  "Frozen call: Enter · Caveat" rather than hiding the recommendation. For
  this specific slate: `frozen_at`=2026-08-28 22:52:53 UTC, first tip
  =23:30 UTC, `frozen_via='job2_first_fire'` (a member of
  `PRODUCTION_FREEZE_PATHS`) — so, assuming the ordinary pipeline state
  (fresh lineup, not paused), the operator had a real ~38-minute window in
  which the root page showed an actionable "Enter now · Caveat" chip plus
  "Expected payout: 1.07" (1.065 rounded), before first tip.
- Sanity-checked the shipped build too: `frontend/dist/assets/index-*.js`
  contains the literal strings `"Expected payout"` and `enter_with_caveat`,
  so this is live, bundled code, not dead source.

No display gap exists for this field. Per the task's own instruction for
this outcome, no code was changed and no tests were added.

### Bonus (candidate fix #2): is card_boost shown separately from slot_base?

**Verdict: yes, already separate — resolves the original report's own stated
uncertainty ("I did not check `wnba-oracle/frontend/` for this"). No change
made.**

- `frontend/src/lib/lineup.ts` (`resolveOrderedLineup`) pairs each player
  with `slotMultiplier = lineup.slot_multipliers[index]` — the raw per-slot
  **base** (2.0/1.8/1.6/1.4/1.2), never combined with `card_boost`.
- `frontend/src/components/SlipRow.tsx` renders that slot base as
  `×{slotMultiplier}` (lines 109, 117) and separately renders
  `<BoostBadge cardBoost={player.card_boost} />` (line 111) whenever
  `card_boost > 0`.
- `frontend/src/components/BoostBadge.tsx` renders `card_boost` alone as
  `+{cardBoost}x` with its own tooltip ("Card boost …").
- Grepped all of `frontend/src` for any place that adds `slot_base` and
  `card_boost` together for display: none exists. The combined "4.2x"-style
  number that made the original report's §4 diagnostic framing misleading is
  never constructed in the UI at all — the operator only ever sees the two
  components apart.

## Task B — why did dayclose come back degraded for 2026-08-28?

**Verdict: the proximate trigger was most likely benign (platform
finalization timing), but the practical consequence is not fully benign —
one of the two affected tables will very likely self-heal automatically and
the other structurally cannot. Net: closer to "needs a manual step" than to
a clean "wait and it resolves."**

### Methodology note (read this before the data — two corrections beyond the task's own heads-up)

1. The literal invocation in the task, `scripts/with-secrets wnba-oracle --
   scripts/auth-check wnba-oracle --live`, fails as written from this
   checkout: `scripts/with-secrets` does `os.chdir(project_dir)` *before*
   `os.execvpe`-ing its command argument, so the relative path
   `scripts/auth-check` no longer resolves once cwd has moved to
   `wnba-oracle/` (only `wnba-oracle/scripts/auth-check-live` exists there,
   not `auth-check`). Used the portfolio-root's absolute path instead
   (`.../sports/scripts/auth-check`) to get it to run at all; it then
   confirmed the same `database` capability the prior investigation found.
   `DATABASE_PUBLIC_URL`'s value also turned out to be wrapped in a literal
   leading/trailing `"` character in addition to the previously-documented
   stale `sslrootcert` path; both were stripped/corrected before connecting.
2. My first query pass issued `SET default_transaction_read_only = on` as
   the first statement of an already-implicitly-open transaction
   (psycopg default `autocommit=False`), which only takes effect for
   transactions that start *after* the `SET` — so that pass, although it
   only ever ran `SELECT`/`SHOW`, was not actually inside a
   Postgres-enforced read-only transaction (`SHOW transaction_read_only`
   read back `off`). Corrected by passing
   `options="-c default_transaction_read_only=on"` at connection time
   instead (the same pattern `wnba_oracle/db/engine.py:get_api_engine`
   uses), then re-verified `transaction_read_only` reads `on` from the
   first statement **and** that Postgres itself rejects a write on that
   connection (`CREATE TEMP TABLE` → `ReadOnlySqlTransaction`). No writes
   were attempted or made under either connection; the second method is the
   one that actually enforces the hard constraint at the database level
   rather than by convention.

### What the data shows

`job_runs` has no rows before 2026-08-20 (table didn't exist yet). Full
`job_name='dayclose'` history since then (9 calendar days):

| Run started (UTC) | Status | `processed_slate_date` | `contest_discovery.contest_id` | `historical_backfill` window | `placement_capture` |
|---|---|---|---|---|---|
| 08-21 06:01 | success | *(pre-substep log format)* | – | – | – |
| 08-22 06:01 | success | *(pre-substep log format)* | – | – | – |
| 08-23 06:04 | **failed** (`game_log_refresh`) | 08-22 | 2092 | 2091→2080 | success (20 entries) |
| 08-23 07:28 | retryable_failure | 08-22 | *(discovery itself failed)* | – | – |
| 08-23 07:29 | success | 08-22 | 2092 | 2091→2080 | success (20 entries) |
| 08-24 06:04 | **failed** (`game_log_refresh`) | 08-23 | 2095 | 2094→2083 | success (20 entries) |
| 08-25 06:05 | success | 08-24 | 2098 | 2097→2086 | success (20 entries) |
| 08-26 06:02 | **failed** (`game_log_refresh`) | 08-25 | 2101 | 2100→2089 | success (20 entries) |
| 08-27 06:07 | success | 08-26 | 2104 | 2103→2092 | success (20 entries) |
| 08-28 06:03 | success | 08-27 | 2108 | 2107→2096 | success (20 entries) |
| **08-29 06:01** | **degraded** | **08-28** | **2111** | 2110→2099 | **degraded: `missing_labels_or_leaderboard`** |

This is the **first** `missing_labels_or_leaderboard` outcome in the entire
reliable-telemetry window — 8 of 8 prior runs succeeded at `placement_capture`
(including the three that failed *overall* for the unrelated
`game_log_refresh` reason). `test_missing_placement_data_is_degraded_not_green`
(`tests/unit/test_dayclose_outcomes.py`) confirms this outcome is a deliberately
designed, anticipated non-fatal state by the code's own authors (degraded, not
failed, not silently green) — but "anticipated in general" doesn't tell us
whether *this* occurrence was benign.

`slate_labels` / `contest_leaderboards` have complete, gap-free per-slate
coverage for every date 2026-08-08 → 2026-08-27 (exactly one `contest_id`
each, confirmed by direct query); 2026-08-28 is the only recent date with
zero rows in either table, **still zero as of 09:54 UTC on 08-29** (~4 hours
after the degraded run, ~8 hours after the slate's last game ended) — nothing
in this system retries mid-day, so this null result was expected regardless
of root cause, not itself informative.

Day-over-day WNBA `contest_id` deltas for the trailing three weeks (from the
`slate_labels` table): 2107←2102←2099←2097←2094←2090←2088←2086←2082←2078,
i.e. deltas of 5,3,2,3,4,2,2,4,4 — mean ≈ 3.2, no cadence spike around this
date. This rules out "the shared cross-sport id space suddenly started moving
much faster" as an explanation.

`discover_wnba_contest_id()` (`src/wnba_oracle/ingest/realsports.py:732`)
returns `max(seen_ids)` across **all** sports' contest-URL network requests
observed during one Playwright pass over realsports.io — its own comment:
*"both MLB and WNBA increment together... Caller validates sport."*
`job_dayclose.run()` (`src/wnba_oracle/scheduler/job_dayclose.py:357-358`)
then walks `[top_cid-12, top_cid-1]` — **deliberately excluding `top_cid`
itself**, on the assumption that `top_cid` is always "today's" contest
(not yet finalized, not the target) and yesterday's WNBA contest is strictly
less. Checking that assumption against every prior run I could verify against
`slate_labels`' recorded actual contest_id:

| Run (`processed_slate_date`) | `top_cid` | actual WNBA cid for that date | offset |
|---|---|---|---|
| 08-25 (08-24) | 2098 | 2097 | +1 |
| 08-27 (08-26) | 2104 | 2102 | +2 |
| 08-28 (08-27) | 2108 | 2107 | +1 |
| 08-23 07:29 (08-22) | 2092 | 2090 | +2 |
| 08-24 (08-23) | 2095 | 2094 | +1 |
| 08-26 (08-25) | 2101 | 2099 | +2 |

`top_cid` was **always** strictly greater than yesterday's actual contest_id
(+1 or +2) on every run I could check. Whether that held on 2026-08-29's run
is exactly the open question, because 2026-08-28's actual WNBA contest_id was
never captured anywhere in our own system — I checked (a) `job_runs` for
`job1`/`job1games`/`job1late`/`job2` on 2026-08-28 (none log a contest_id;
their `details_json` is the older minimal `{"source_exit_code": 0}` shape,
not the richer substep format), and (b) both `frozen_lineups.metadata_json`
(only key: `frozen_via`) and the top-level keys of `frozen_lineups.lineup`
for slate 2026-08-28 (`lineup_score_p10/p50/p90`, `model_provenance`,
`payout_curve`, `per_player`, `player_ids`, `serving_knobs`,
`slot_multipliers`, `source_assurance`, `stack_decision` — nothing
contest-id-shaped). So I cannot directly determine whether 2026-08-28's
contest_id was **(i)** ≤2110, inside the searched window, and simply not yet
finalized on the platform at 06:01 UTC, or **(ii)** exactly 2111 (=`top_cid`)
and excluded by the `top_cid-1` boundary. This is the one open item a live
platform query could resolve, which I did not make (out of scope).

Timing leans toward (i) as the plainer reading, absent contrary evidence:
this slate's last game tipped at 02:00 UTC (per the original postmortem),
ending roughly ~04:00 UTC — only ~2 hours before dayclose ran at 06:01 UTC.
The job's own docstring calibrates "06:00 UTC is the earliest fire time that
always catches the prior night" against a single historical precedent
(contest 1831, `processedAt` 05:07 UTC) for a slate whose own last-tip time
isn't stated, so whether that margin generalizes to a slate with an unusually
late 02:00 UTC final tip is unverified. Circumstantial, not proof.

**Regardless of (i) vs. (ii), the two affected tables have different recovery
outlooks, which is the more decisive, mechanism-independent finding:**

- `slate_labels` / `contest_leaderboards` will plausibly **self-heal without
  any human action**: `historical_backfill`'s window is contest-id-relative
  and deliberately re-sweeps overlapping ranges every day (upserts make
  re-processing "a cheap no-op," per its own docstring), so the
  **2026-08-30 06:00 UTC** run's window (`top_cid` presumably ≈2113–2116,
  walking back 12) will very likely still cover 2108–2111 under either
  hypothesis. **This is falsifiable**: re-check
  `SELECT COUNT(*) FROM slate_labels WHERE slate_date='2026-08-28'` after
  that run; if it is still 0, that upgrades hypothesis (ii) (or an even
  wider miss) from "possible" to "confirmed."
- `contest_placements` for 2026-08-28 will **not** self-heal, under either
  hypothesis, no matter how many days pass: `_auto_record_placement()`
  (`job_dayclose.py:44`) is only ever invoked for
  `processed_slate_date = previous_slate_date()` — strictly "yesterday"
  relative to whenever dayclose runs. No future run ever revisits
  2026-08-28 specifically once it stops being "yesterday," even after the
  labels/leaderboard data above recovers on its own.

So the task's own framing of outcome (a) — "a later re-run would succeed" —
is only half true here: the underlying labels/leaderboard data will most
likely recover on their own on the very next run, but this slate's own
placement/calibration record will not, unless an operator takes a manual
step. In effect this sits between (a) and (b): benign-looking proximate
trigger, but a real, un-self-healing gap in what gets captured.

### Recovery step (described only — not run; no DB writes made)

1. **To force-recover `slate_labels` / `contest_leaderboards` for
   2026-08-28 with certainty**, rather than waiting on the natural sweep —
   critically, the window must *include* `top_cid` itself this time, not
   stop at `top_cid-1`, specifically to rule out hypothesis (ii) instead of
   reproducing it:
   ```
   scripts/with-secrets wnba-oracle -- uv run --package wnba-oracle \
     python -m wnba_oracle.ingest.backfill --mode historical \
     --start-id <top_cid at run time, e.g. 2113-2116> --stop-id 2105 \
     --pause-seconds 0.5
   ```
   This requires an authenticated Real Sports session
   (`WNBA_DEVICE_UUID` + a cached/derived storage state). Confirmed via this
   machine's own `auth-check --live` output that this local checkout does
   **not** have one ("Real Sports derived session: not configured, browser
   recovery only") — this would have to run from the production cron
   container or another environment with `REALSPORTS_STORAGE_STATE_B64GZ`
   configured, not from here.
2. **To recover just our own `contest_placements` row for 2026-08-28**
   (independent of step 1, and already possible today, since it only reads
   `frozen_lineups`, which exists for this slate): the already-registered
   `oracle-placements` CLI (`pyproject.toml`:
   `oracle-placements = "wnba_oracle.scheduler.placements:main"`) does
   exactly this:
   ```
   scripts/with-secrets wnba-oracle -- uv run --package wnba-oracle \
     python -m wnba_oracle.scheduler.placements record \
     --slate-date 2026-08-28 --contest-id <real contest id> \
     --rank 6384 --count 6800 --score 29.92
   ```
   using the rank/field-size/score already known from the leaderboard in the
   original task. This only needs `DATABASE_URL` (writes straight to
   `contest_placements`, joining the existing frozen lineup for the forecast
   snapshot) — but `--contest-id` is required and is **not** recoverable
   from anywhere in our own database (confirmed above: neither
   `metadata_json` nor `lineup` carries it), so it has to come from the
   operator's own Real Sports session/entry history, or from step 1
   succeeding first.

Aside, not this incident: `contest_placements` has additional gaps at
several slate_dates between 2026-06-12 and 2026-08-20; `job_runs` has no
history before 2026-08-20 and the richer substep-JSON format only starts
appearing on the 2026-08-23 run, so those older gaps can't be diagnosed the
same way and most likely predate the current auto-placement-capture wiring
rather than being instances of this same failure mode. Not investigated
further — out of scope for this slate.

## Files changed

**None in the application source tree.** Both tasks concluded "already
correct" (Task A) or "diagnosis only, by instruction" (Task B):

- Task A: no code change — `entry_recommendation` and `expected_payout`
  already reach the operator end-to-end, and `card_boost`/`slot_base` are
  already shown separately. No tests added (nothing changed).
- Task B: diagnosis only. No DB writes were made (verified empirically — see
  methodology note); no backfill or recovery command was executed.
- This file (`wnba-oracle/MODEL_PICK_POSTMORTEM_2026-08-28.md`) is the only
  file modified, by appending this section. Scratch query scripts used for
  the read-only Postgres checks were written to the session scratchpad
  directory, outside the repository, and are not part of this diff.

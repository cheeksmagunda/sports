# Community Strategy Findings (issue #37), 2026-09-24

Answers `COMMUNITY_STRATEGY_TASK.md` as far as the reachable, PII-free data
allows. Read-only; no production table, knob, or behavior was changed.
Rerun with `scripts/analyze_field_intelligence.py` (usage in its docstring).

## Data sources actually used

| Source | What | Window |
| --- | --- | --- |
| `backups` branch commit `29c975cd` (2026-09-24T17:41Z), `wnba-oracle/data/backups/slate_labels.csv` | 6,922 rows, sha256 `490846cb...` matches its manifest | 2025-05-16 to 2026-09-22 |
| same commit, `manifest.json` only | row/slate counts for `contest_leaderboards` (4,520 rows, 226 slates) | same |
| Public API `GET /dossier/{date}` | 77 of 119 dates returned 200 | 2026-05-27 to 2026-09-23 |
| Public API `GET /lineup/{date}` | 87 frozen lineups; `lineup.serving_knobs` on 70 | same |

**Not used: `contest_leaderboards` rows.** The session's permission
classifier refused reading them (PII: stable per-user `user_id`), which also
rules out the local 2026-09-02 export in the main checkout. Every
leaderboard-dependent analysis (ownership skew by rank, slot/boost ordering
of top-20 entries, repeat finishers, top-20 duplication) is implemented and
unit-tested in the script but **has not been run**. Minimal authorized path:
the operator runs the script with `--leaderboards-csv` against the backups
snapshot (the script pseudonymizes `user_id` at load time and prints only
aggregates), or grants a permission rule for that one command. Durable fix:
a read-only `/leaderboard/{date}` endpoint that hashes `user_id` server side.

All intervals are 95% slate-bootstrap intervals over per-slate statistics;
the window is 2026-05-27 onward (94 label slates) unless stated.

## A. Data audit

- `slate_labels` is **not the slate pool**. It is the union of the
  platform's community sections: `highestBoostedValuePlayers` (1,913 rows,
  selected on realized outcome), `popularPlayers` (840, selected on
  drafts), `mostCommon3xPlayers` (294), `leaderboard_lineup` (141). Median
  34 rows per slate; 69 of 94 slates fall below the 37-row threshold
  `dossier.py` uses, so every dossier ceiling is a lower bound on the
  *observed* pool, not the true slate. High confidence.
- Calendar gaps: 2026-07-22 to 07-28 (6 days) and 2026-08-30 to 09-17
  (18 days). Only 6 slates after 2026-09-01. Whether these are no-game
  periods or capture gaps is unverified.
- `min_slate` 2025-05-16 predates the stated 2026-05-27 capture start
  (backfilled 2025 season; 116 slates). Not used for headline numbers.
- 4.9% of window rows lack `drafts`; 24 duplicate (slate, player) rows
  (same player in two sections), deduplicated in analysis.
- Dossiers: 17 label slates have no dossier (no frozen lineup, or other
  missing input). Our committed score is exact on only 31 of 77 dossiers,
  because our picks are often absent from the community sections.
- `contest_leaderboards` per manifest: 4,520 rows / 226 slates, exactly 20
  per slate on average. Per-slate completeness not verified (rows blocked).

## B. Field behavior (community sections)

1. **Popularity vs value (the ported -0.457).** On the deduplicated observed
   pool, drafts vs boosted value (`real_score * (2 + card_boost)`) is
   rho = -0.41 [-0.47, -0.34]; 2025 is similar. It is driven entirely by
   boost: drafts vs `card_boost` is -0.68 [-0.70, -0.66] while drafts vs raw
   `real_score` is +0.03 [-0.02, +0.08]. Within a single section the
   relationship vanishes or flips (for example +0.15 within
   `popularPlayers`), so the pooled figure partly reflects section selection.
   Least-drafted half / most-drafted half total boosted value:
   1.38 [1.30, 1.45] (basketball-main NBA: ~1.24 to 1.26). Medium confidence
   in the magnitude, high in the sign.
2. **Ceiling membership (audit comment Q5, unconditional form).** The
   realized-ceiling lineup's players sit at a mean drafts percentile of
   0.34 [0.31, 0.36]; on average 3.7 of 5 are in the bottom half of drafts
   and 0.36 in the top quartile. Their mean boost is 1.78 vs 1.49 for the
   observed pool. Popularity predicts *non*-membership in the ceiling. The
   conditional form (given Oracle's pre-tip predictions) was not run.
3. **Our ownership estimator ranks the field backwards.**
   `field._estimated_ownership_unnormalized` is monotone in
   `pred_real_score * (1 + card_boost)`. Even with a perfect forecast
   (realized score substituted), that proxy vs measured drafts is
   rho = -0.56 [-0.61, -0.50], negative on 93% of slates, because the field
   drafts low-boost players and the estimator assigns them low ownership.
   Per AGENTS.md (#38), live freezes always use this estimator. High
   confidence for the proxy; medium-high that the live estimator (real
   predictions, extra flags) shares the sign, since boost dominates.
4. **A leak-free measured prior exists.** A player's drafts percentile on
   their most recent earlier slate predicts today's percentile at
   rho = 0.51 [0.48, 0.54], covering 94% of observed rows, versus -0.56 for
   the estimator proxy on the same rows. High confidence.

## C. Objective evaluation

Live serving knobs (from `lineup.serving_knobs`, not code defaults):
`payout_regime=top_20` throughout; `leverage_weight` 0.0 from 2026-06-13,
0.28 from 2026-08-30; `committed_order_objective` and `ceiling_tilt_slots`
true from 2026-08-30 (unrecorded before); `duplication_weight` 0.0 and
`duplication_aware_payout` false throughout; no knobs recorded before
2026-06-13.

- **Winner vs ceiling (audit comment Q1 to Q3).** Field winner averages
  57.0 [55.5, 58.5] points, 0.87 [0.85, 0.89] of the observed ceiling
  (9.1 [7.7, 10.6] points short); within 5% of it on 10% of slates, above it
  once (the ceiling is a lower bound). The field is efficient but not at the
  ceiling. Medium confidence (ceiling censoring).
- **Us vs winner.** On 31 exact dossiers we score 0.67 [0.62, 0.71] of the
  winner (18.9 [16.3, 21.4] points short). Only 2 of those are under
  `leverage_weight=0.28`: no regime comparison is possible yet.
- **Payout regime / our distribution (task Q5).** The winner beat our own
  frozen `lineup_score_p90` on 18% of 76 slates and our p50 on 97%;
  winner / p90 = 0.82 [0.77, 0.87]. On 30 exact rows our realized score was
  below our p50 67% of the time and never above p90, and those rows are
  biased toward good outcomes (section selection), so our distribution is
  likely optimistic. Medium-low confidence (n=30).
- **`leverage_weight` (0.28).** Keep under review, flagged. Two independent
  problems: (a) #289: the benchmark that promoted it
  (`build_model_research_benchmark.py` `_precompute_slates`, shared by
  `model_tournament.py`) patched `job2._load_measured_drafts` to each
  slate's own post-lock drafts, information a live freeze never has
  (`backtest_walkforward.py` has the correct prior-slate guard); (b) B3
  above: the ownership live freezes actually feed `-log(own)` is
  anti-correlated with real ownership, so live the term likely rewards the
  field's chalk (low-boost players) rather than fading it. The +5.1 score
  evidence therefore does not transfer to production and the live sign may
  be reversed. High confidence that the evidence is invalid; medium that
  the live effect is harmful.
- **`duplication_weight` (0.0).** Keep at 0. It prices `prod(own_i)` with
  the same inverted ownership; no top-20 duplication data was reachable.
- **`committed_order_objective` (true).** Keep. It matches what the entrant
  can commit; field slot-ordering evidence (top-20 headroom) awaits the
  leaderboard run.
- **Contrarian adjustment (`strength=0.2`).** Consistent in sign with B1,
  but it keys on the same popularity estimate; revisit with B3.

## Decision log

| Item | Decision | Why |
| --- | --- | --- |
| Production knobs, tonight | No change | Live slate, freeze 22:20 UTC; evidence is not decisive enough for an unreviewed flip |
| `leverage_weight=0.28` | Keep (default-grid evidence) | #289 methodology fixed; #317 leak-free default-grid challenger `0.2` was ~9/92/8 W/T/L, mean dScore -0.036, flat payout — no flip. Dedicated E1 matrix optional; B3 inversion remains |
| Ownership source | Proposal only (not implemented): new flag, default off, feeding `field.project_ownership` the prior-slate measured percentile (B4) instead of the estimator | Leak-free and strongly predictive; needs a walk-forward backtest before arming |
| `duplication_weight`, `duplication_aware_payout` | Keep off | Depends on ownership quality; no field duplication data yet |
| `committed_order_objective`, `ceiling_tilt_slots`, `payout_regime=top_20` | Keep | No contrary evidence reachable |
| Leaderboard-dependent analyses | Implemented, tested, not run | PII permission block; needs operator run |

Remaining uncertain: everything that needs `contest_leaderboards` rows
(repeat finishers, rank-band skew, top-20 slot ordering and duplication),
the conditional form of audit Q5, and whether the two calendar gaps are
capture failures.

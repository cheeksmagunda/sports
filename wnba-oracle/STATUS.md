status: BUILD_COMPLETE
last_verified: 2026-06-21T00:00:00Z
phase: live. 2026-06-21 (D104): two operator-directed corrections for T-40
serving. (a) The RotoWire starter signal now acts on EXPECTED starters, not
only CONFIRMED -- confirmed lineups for every game on a slate are not all out by
the T-40 freeze of the first tip, so a confirmed-only gate silently ignored the
starting five (e.g. tomorrow's 4-game slate, captured 13:04 UTC when RotoWire is
all "Expected"). New `_effective_confirmed = confirmed OR (use_expected AND
is_starter)` threaded through every role consumer (multiplier, anchor,
availability, blended minutes); one-directional (promotes expected starters
only), so a fully-confirmed slate is byte-identical -- verified today's 30
starters were all confirmed. Reverse: STARTER_SIGNAL_USE_EXPECTED=false. (b) The
frontend countdown was hardcoded to 21:00 UTC; now tip-relative via new
`GET /slate/{date}` (first_tip_utc + freeze_target_utc = lock - freeze_lead,
mirrors job2's deadline math), consumed by useSlateTiming -> Countdown; neutral
caption when timing unknown. Backend 414 tests, ruff+mypy clean; frontend builds,
5 vitest pass. See DECISIONS D104.
2026-06-21 (D103, CRITICAL): restored cron-job1 + cron-job1-late
startCommands. Both had been silently overwritten to `oracle-cron --job backfill`
(the on-demand head-features backfill) during today's corpus rebuild -- left
uncorrected, tomorrow's 13:00 cron-job1 would have run backfill, produced NO
fresh pool, and frozen nothing. Restored cron-job1 ->
`seed_storage_state && oracle-cron --job job1`; cron-job1-late ->
`oracle-cron --job job1late` (the new credit-free lite confirmed-lineup refresh)
on a widened `*/30 16-23` schedule so afternoon AND evening slates get confirmed
starters before T-40. Both redeployed SUCCESS on 265b6e6, verified live. Rule:
`--job backfill` runs ONLY on the dedicated backfill-enrichment service.
Then closed NEEDS_CLAUDE 24-32: #27/#28/#30/#31 DONE, #26 DONE (parse),
#29/#32a PARTIAL (silent-miss warning + expansion-team warning shipped), #24
cosmetic-wontfix (read-only DSN), #25 superseded. New #33 (cron-role self-check).
Full suite 406 (+3 nightly contract). See DECISIONS D103.
2026-06-21 (D102): Post-work cleanup -- cron/test/sustainability
audit (3 parallel read-only audits) + fixes. SHIPPED: (1) RotoWire
confirmed-starter parse repaired -- the D100 root cause -- the badge was read
once per game-box and stamped on both teams, and abbreviated visiting-team
names ('C. Zandalasini') defeated the Real Sports full-name join; both fixed,
split into parse_lineups_html() with a checked-in fixture + test (was zero
coverage). (2) Watchdog now surfaces silent failures: model_artifact_unset /
_unresolved (CRITICAL -- catches an env-reset to the silent heuristic,
0.554->0.246) and odds_empty / rotowire_empty (WARN). (3) Test health:
determinism gate globs artifacts instead of pinning rotation-stale SHAs;
caveat_is_skip/never_skip picker tests de-vacuumed (bracket EV, assert band);
stale '21:00 static clock' comments refreshed to tip-relative T-40. Full suite
385 -> 396. Audit confirmed clean: 2027 season rollover handled, Redis TTLs
set, freeze idempotent. Deferred (NEEDS_CLAUDE 27-32): tip-relative job1-late
for afternoon slates, auto-refresh wnba_game_logs in dayclose (the deeper D99
fix), live identity Resolver routing, config-drift manifest, contract tests,
housekeeping. See DECISIONS D102.
2026-06-21 (D97-D101): Post-mortem follow-up session (5 items).
(D97) Fixed the -inf expected_payout bug: optimize._scan left best_ev at its
-np.inf init when every combo was skipped (the 2026-05-31 two-team slate); a
post-scan guard now clamps to 0.0 and skips the empty-slice np.median. 1 new
test, 385 pass. (D98) Game-stack alignment audit (new
scripts/stack_alignment_check.py): 56.2% of model-era slates put 2+ of our
picks on the winner's stacked team -- below the 60% bar, so raised
OPTIMIZER_GAME_STACK_BONUS 0.005 -> 0.010 on cron-job2 and redeployed (deploy
33c3cb14 SUCCESS). Nuance: 4/7 misses had winners with NO 2+ stack
(un-alignable); we already 2-stack 94% of slates, so the gap is stack SELECTION
not propensity. (D99) C. Leite knowable misses root-caused to STALE serving
features (head_features byte-identical across 06-11/06-17, season_game_number
frozen at 12; legacy recent_minutes=12 vs real ~25) -- a targeted
platform-id->stats-id freshness gap, not a weighting issue. (D100) The two
negative-corr slates (06-12 -0.500, 06-19 -1.000) are tiny-sample rank noise
(both in-band 3/3) + the boost-handicap variance tradeoff + the same serving
gap (rotowire_confirmed=0 across the whole 06-12 slate); not a weighting issue.
(D101) Retrain evaluated and NOT promoted: items 1-4 show no feature-weighting
change; a same-recipe challenger on the fresher corpus (game logs now through
06-20) had identical training_rows=11205 and differed from production in one
booster (early-stop noise), unvalidated -- production picker_e2ced9ec kept.
Serving-data follow-ups logged to NEEDS_CLAUDE 24-26.
2026-06-19 (D94/D95): Production work session. (D94) Root-caused
and fixed the 2026-06-13 freeze outage: FROZEN_APPEND reused the :model_sha bind
param and, after migration 0008 made the column varchar(64), Postgres raised
AmbiguousParameter on every append -- no slate froze for 5 days. Fixed with
CAST(:model_sha AS varchar) + self-healing Redis lock release on append failure.
Verified live: 2026-06-18 froze (row 25) and serves. (D95) The deeper cause was
that all Railway services were pinned to 2026-06-13 code (auto-deploy was off),
so every D86-D93 improvement was dark. Re-enabled auto-deploy on all 6 services
and redeployed them to HEAD; widened cron-job2 to the all-day tip-relative
window so the T-40 gate covers afternoon slates (current job1 now populates
slate_meta.first_tip_utc, which the June-8 deploy never did). Full suite 370.
2026-06-15 (D93): Deep-dive work session (branch
claude/app-deep-dive-2026-rhwfn0). (A) Root-caused the corr-0.554-vs-"21/20"
paradox to a CENSORED benchmark, not a projection deficit: contest_leaderboards
stores only the top 20 of ~8,300 entries, so "below the captured top-20 median"
means "not top ~0.12%", not "below-median placement"; cohort routing ruled out
(model is F-only, train/serve consistent). Full write-up in
research/internal/08_projection_paradox.md. (B) Auto-placement now records the
real finish_percentile from num_brawlers (field size, already in
contest_leaderboards) whenever our entry cracks the captured top-20; a floor
bound otherwise. (C+E) FREEZE_LEAD_MINUTES (default 40): the freeze is now
anchored to first_tip - 40min (T-40), tip-relative not clock-relative -- job2
skips fires before T-40 and freezes once at/after it, and the watchdog escalates
a missing freeze at the same deadline (catches matinee slates the static 22:00
rule missed). REQUIRES widening cron-job2 to fire across the day (NEEDS_CLAUDE).
(D) ruff + mypy on src/ clean again; make determinism-check repaired
(content-equality, not pickle SHA). Full suite 365 tests.
2026-06-13 (D86): Placement overhaul Phase 0. Root-caused the
2026-06-12 median finish (4,253rd/8,300 with all five picks beating projection)
to a strawman field model: project_ownership derived opponents from our own
projections and discarded the real, observed in-app draft counts, so the EV
engine could not price duplication or leverage and shipped chalk. Fix: feed
slate_labels.drafts into FieldPlayerSpec.measured_drafts so the field simulation
uses real ownership marginals (gated FIELD_MEASURED_OWNERSHIP_ENABLED, default
on; auto-falls-back to the estimator when no counts present). 4 new tests. Full
diagnosis + phased roadmap (payout-curve ingestion, results feedback loop,
stack-aware field, ceiling-tilted slots) in research/internal/07_placement_overhaul.md.
Phase 0 needs no retrain; takes effect on cron-job2's next fire once deployed.
2026-06-10 (D82-D85): Incident remediation for the 2026-06-08
late-refreeze overwrite, on branch claude/frozen-lineups-audit-refreeze-a3obw3
(PENDING DEPLOY: migration 20260610_0006 must apply before the new code
serves; deploy all services from one commit in the 06:30-12:30 UTC quiet
window; see deploy checklist below). D82: frozen_lineups is append-only --
freeze_seq + frozen_via columns, key now (slate_date, model_sha, freeze_seq),
FROZEN_APPEND replaces both FROZEN_INSERT and FROZEN_UPSERT, the late
re-freeze appends instead of overwriting, /lineup/{date} serves max
freeze_seq with provenance (freeze_seq, frozen_via, n_freezes), new
/lineup/{date}/history audit endpoint. D83: late re-freeze gated on contest
lock -- job1 captures first tip into new slate_meta table
(realsports fetch_slate_game_times; platform exposes no lock timestamp, only
isLocked), gate blocks the forced append within REFREEZE_LOCK_BUFFER_MIN of
lock or past LATE_REFREEZE_DEADLINE_UTC when lock unknown, fails closed.
D84: degraded job1 pool is a hard error -- pool_sanity gate
(JOB1_MIN_POOL=12, JOB1_MIN_TEAMS=2, row floor max(min,3*teams)), critical
job1_pool_degraded watchdog event, exit 1; watchdog now runs after job1
fires too; pool_too_small escalated to error; new pool_degenerate_teams
(critical) + enrichment_stale (warn) checks; optional WATCHDOG_PING_URL
dead-man's-switch ping on critical. D85: full-universe labels -- root cause
of the Loyd(726)/Boston(627) gap is slate_labels only storing the three
draftStats sections; new leaderboard_lineup supplemental labels harvested
from top-20 finisher lineups (DO NOTHING insert, canonical rows win),
unknown-section logging, label_coverage_gap watchdog check wired into
dayclose. 315 unit tests pass (was 263). DEPLOY CHECKLIST (needs prod
creds, absent in this build env): (1) merge + deploy all services from the
branch commit in the quiet window; API boot applies migration 20260610_0006;
(2) verify alembic_version, \d frozen_lineups shows
uq_frozen_lineups_slate_model_seq, /lineup/<date> returns freeze_seq;
(3) forensics for D84: SELECT date_trunc('minute',captured_at),COUNT(*),
COUNT(DISTINCT team) FROM job1_enrichment WHERE slate_date='2026-06-08'
GROUP BY 1; and the frozen row's frozen_at/metadata -- resolve how a freeze
existed when the 21:00 pool reportedly had 1 row (job2 pool_too_small gates
at <5); (4) D85 backfill: oracle-backfill --mode historical --start-id <cid>
--stop-id <cid> for the 2026-06-08 contest, then verify pids 726 (0.8) and
627 (2.94) carry section='leaderboard_lineup' rows; (5) set
WATCHDOG_PING_URL once the human provisions a monitor (NEEDS_CLAUDE 20).
Earlier 2026-06-08 (D80/D81): Pre-slate pipeline audit. Verified core
serving healthy via job2 dry-run (heads fire 71/73, optimizer converges, valid
lineup). Found + fixed two dead "improvements": D80 player props were hitting
the aggregate /odds endpoint (HTTP 422 -> always empty since D78); repointed to
the per-event endpoint, slate-scoped, player_points only. D81 confirmed-starter
(D71) had never fired because RotoWire is scraped at 13:00 UTC (all "Expected");
added cron-job1-late at 22:35 UTC to refresh enrichment with CONFIRMED lineups
before the 23:00 re-freeze. Both verified live; 263 unit tests pass.
Earlier 2026-06-07 (D79): Manual model promotion. picker_e2ced9ec (SHA 94f8e860...) now set on all three services: api, cron-job1, cron-job2. oracle-rotate-check returned BLOCK/underpowered (n_rows=0, artifact deployed today) -- operator authorized manual promotion. All services redeploying. Earlier 2026-06-07 (D78): Prop-signal multiplier in job2._prop_signal_multiplier(). Formula: pred *= clamp(1 + (over_prob - 0.5) * scale, 0.85, 1.15). Wired into Tier-0 head path. PROP_SIGNAL_SCALE defaults to 0.0 (disabled until calibrated against placement data). Fixed `or 0.5` null-coalesce bug (0.0 treated as falsy). 7 tests in test_prop_signal.py. Earlier 2026-06-07 (D77b): New artifact picker_e2ced9ec_1780873338.pkl (SHA 94f8e8606dab4d48652929bb3884fb9152e1abc766eeb2c2d86559f4318676cd) trained with team_pace/opp_pace/opp_dvp populated in the corpus (D77 -- previously zero-filled). Deployed: WNBA_ORACLE_MODEL_ARTIFACT_SHA updated on Railway cron-job2. Earlier 2026-06-07: D77 _enrich_corpus_matchup() added to corpus.py (nba_api pace + game_logs DvP, 5 tests). D76: n_field default 120->500 (SE analysis: 120 = ±1.34% vs 0.22% signal; 500 = ±0.66%). D75: late re-freeze path in job2._freeze(force=True) -- LATE_REFREEZE_ENABLED=true armed on Railway cron-job2, fires at 23:00 UTC to overwrite the 21:00 freeze with confirmed-starter data (WNBA 30-min lineup announcement window). D74: RotoWire URL fix (/basketball/ -> /wnba/, is-wnba -> is-nba), team_pace/DvP/player_props injected in job1 serving path. All cron-job1 + cron-job2 deployed. Earlier: 2026-06-07 (D73, R9 calibration): AvailabilityConfig recalibrated empirically over the 13,002-row gamelog corpus. prior_active 0.30 -> 0.20 (cold-start cold/bench empirical rate), neutral_prior 0.60 -> 0.55 (rotation-bench empirical rate). On a cold-start dart with heuristic projection 8.5, post-availability projection drops 2.55 -> 1.70, clearly below the realistic-starter floor. Confirmed-starter (0.92) and confirmed-bench (0.70) floors unchanged so RotoWire overrides still hold. Calibration script + JSON snapshot under research/internal/. Commit c63d822, pushed. AVAILABILITY_MODEL_ENABLED already armed on cron-job2, so this takes effect on the next deploy. Earlier today: 2026-06-07 (R7 finding, commit fc0b6a4): walk-forward comparison says the naive 4-component recompose does NOT beat the single rate head -- corr lift +0.0016 negligible, CRPS up 277% due to quadrature spread on correlated components. R7 logged as KEEP single head; full Beta-Binomial reformulation would be a different exercise. Earlier: 2026-06-07 (D72, R6 from research/00_GAP_ANALYSIS.md): MENU-SCRAPE GAP CLOSED. fetch_pool_for_date now runs a targeted-search fallback after the a..z prefix sweep -- for each per-game-union player not yet rated, query the ASCII-folded first 3 chars of their last name (cap 50 per slate). The audit (scripts/research/menu_scrape_gap.py) against the LIVE collector window showed 8 of 13 slates (61.5%) had >= 1 winning-lineup pick the optimizer could not pick, including the 2026-06-01 rank-1 lineup (M. Akoa Makani, pid 4322738) and the 2026-06-02 rank-2 lineup (C. McMahon, pid 4322864). Recurring victims (A. Stevens, S. Sabally, J. Jocyte, M. Akoa Makani, C. McMahon, K. Bell) all draftable per Real Sports leaderboards. fetch_pool_fallback log line surfaces n_added per slate. New `oracle.ingest.realsports` log channel. 4 unit tests in test_realsports_pool_fallback.py exercise: recovery by last-name, ASCII-fold for accented names (Jocyte), missing first+last skip-not-crash, no a..z requery. Commit e340350 on main, pushed. No env change; pure code, takes effect on cron-job1's next 13:00 UTC fire. Earlier 2026-06-07 (D71, R5): RotoWire confirmed-starter signal now wired into the D69 head Tier-0 path. The trained heads learned without `is_confirmed_starter` (the gamelog corpus doesn't compute it, so `train/pipeline.py:240` drops it from feature_subset_per_head — verified against picker_bf3c8996_*.pkl), so the head was silently blind to today's confirmed lineups. job2._build_specs Tier-0 now calls `_starter_multiplier` (the same Tier-3 helper) and scales p10/p50/p90 symmetrically by 1.10 (confirmed starter), 0.82 (confirmed bench), or 1.00 (unmatched). Tier-1 blend deliberately stays unchanged (blended_real_score handles role signals internally). Tests grow 4 -> 7 in test_head_tier0.py. No env change; reverse via STARTER_SIGNAL_ENABLED=false or revert commit aa39806. Earlier: 2026-06-06 (D70, R2+R3+R4 from research/00_GAP_ANALYSIS.md): three picker hardening knobs SHIPPED on cron-job2. R2 lineup boost caps (OPTIMIZER_BOOST_SUM_CAP, OPTIMIZER_MAX_SINGLE_BOOST) refuse lineups whose sum-of-card-boost or per-pick boost exceeds the configured ceiling; relax to 0 (with a warning) only when the team cap + boost caps are jointly infeasible. Armed at 9.0 / 2.5 — median rank-1 winner total boost is 7.5 (research/internal/01_winners_anatomy.md), the 2.5-3.0 boost bucket has 8.2%/Sharpe-1.21 vs (2.0,2.5] at 50.4%/2.01 (research/internal/04_boost_economics.md), and the 2026-06-04 ~6000th bust was driven by five high-boost cards. R3 game-stack bonus (OPTIMIZER_GAME_STACK_BONUS, armed at 0.005) adds a tiny per-stack-pair EV bias since 87% of top-20 lineups include a 2+ same-game stack. R4 audited the slot assignment — already optimum under the rearrangement inequality (`optimize.py:309-316`); winners' low-slot-0 boost is a player-selection effect, not a slot-assignment bug. Pinned by tests/unit/test_boost_cap.py (8) + test_game_stack.py (7). Commits 7386f71 (R2) and 5395585 (R3+R4) on main, pushed. Env vars set on cron-job2 (service id 4a511ed2-10ad-441f-bf9a-3748c1e6b929). All three reverse via env with no redeploy: unset the OPTIMIZER_BOOST_SUM_CAP / OPTIMIZER_MAX_SINGLE_BOOST / OPTIMIZER_GAME_STACK_BONUS env vars (or set to 0.0). Earlier same day: 2026-06-06 (D69): Phase 2b SHIPPED — D63 trained heads now serve job2 live. job1 persists the full causal head-feature row into features_json.head_features (build_head_feature_lookup, mirrors features/corpus.build_gamelog_corpus); job2._build_specs now batch-runs the (minutes, F) + (real_score_per_min, F) heads via PickerArtifact.predict_real_score in a new Tier-0 path above the existing blended_real_score -> EB -> history -> heuristic ladder. Purely additive: any pid without a head prediction falls through unchanged (4 unit tests in test_head_tier0.py pin all four branches). Per research/internal/03_theoretical_ceiling.md, wiring alone is projected to lift top-500 rate 33% -> 61%. New artifact SHA: 2cc953b7fe86e8db8a21f7f9a594a2944c4ce9d98aa21d05a0a0b434d6efd985 (picker_bf3c8996_1780752059.pkl, 6 heads trained on cohort F, training_rows=11205). Deploy: set WNBA_ORACLE_MODEL_ARTIFACT_SHA=2cc953b7fe86e8db8a21f7f9a594a2944c4ce9d98aa21d05a0a0b434d6efd985 on Railway after the commit lands. Watch job2 logs for head_predict n_in/n_out and predictor_mix n_head_predicted. Earlier: 2026-06-05 (D63): decomposed projection ACTIVATED offline. The multi-task heads were coded but never trained (the 7-column slate_labels corpus lacked their target columns), so job2 served a career-average heuristic for ~85% of players, the root cause of the 06-04 ~6000th/8317 bust. New features/corpus.py builds a 12,981-row feature+target corpus from the 13,435 game-logs (targets via the locked box_to_real_score); the minutes + per-minute heads now train (low_data_mode cleared, 0 -> trained). New PickerArtifact.predict_real_score recomposes E[real_score]=E[min]xE[rate] as a lognormal product; TRUE walk-forward (train pre-2026, predict 2026, n=1776) corr 0.554 (matches the actual-min ceiling, D55) vs the boost heuristic's 0.246, P10-P90 coverage 0.81. Also Phase 0: CV embargo leak fixed (3d -> window-covering 70d), player_id tree-categorical footgun removed (was latent), eval/multiple_comparisons.py CPCV + deflated-edge guard above the rotation gate. LIVE SERVING UNCHANGED: the deployed artifact (SHA 6182a29d) still has 0 heads and job2 still serves the heuristic ladder; the trained heads are dormant until Phase 2b wires job1 feature persistence + a job2 Tier-0 path. Commits 01a1d15/241b6b5/d792127 on main. Phases 2b-6 remain (see DECISIONS D63). Training command is now `oracle-train --corpus-mode both`. 2026-06-02: Tier 3 built behind GAME_SCRIPT_MINUTES_ENABLED (default OFF, D57) -- role-aware game-script bench-minutes redistribution (features/game_script_minutes.py) + regime-switching same-team copula correlation (picker/sample.py), wired into job2 behind the kill-switch; live freeze byte-identical with the flag off. This is Tier 3 of the D57 draft-winning strategy, built first at operator direction; it rides on the Tier 2 availability engine (not yet built) and currently only moves KNOWN rotation bench players, so it does NOT by itself fix the 06-01 all-longshot bust. 2026-06-01 22:23Z: today's slate frozen with real names + entry=enter (Shepard/Holmes/Siegrist/Horston/McCowan) after fixing a prod OUTAGE (D56): the optimizer's prod defaults (5000 samples x 1000 field x C(30,5)) could not finish in the 15-min cron window, so job2 was killed before freezing every tick -- no picks, and earlier freezes showed "Player <id>" (optimizer picked blank-name boost-3 rookies). Fixed by reducing optimizer knobs to the validated range (~85s). 2026-06-01 build pass also shipped: dynamic team cap (D50); contrarian kept at 0.2 (D51); sampling K=10->2 + per-player sigma (D52); and the MINUTES/ROLE MODEL (D55) -- the real edge (today's freeze matched 48/49 players to nba_api minutes). Proven walk-forward: minutes x rate predicts real_score at corr 0.554 (actual-min ceiling) / 0.355 (recency) vs boost 0.246; real_score is a fixed box formula (R^2 0.957) so the pipeline is self-contained on nba_api. job1 ingests per-player recent_minutes + per_min_rate from stats.wnba.com game logs; job2 uses a boost<->minutes blend with confirmed-starter / injury-cascade / blowout same-day signals. Env kill-switch MINUTES_MODEL_ENABLED. Earlier: CAVEAT_IS_SKIP + stable argsort (D48); recency/EB-over-boost tested and rejected (D52/D54, boost already encodes form). Harnesses: scripts/backtest_walkforward.py, validate_minutes_model.py, test_minutes_placement.py, replay_slate.py.


NEVER_SKIP policy active (default on, D67, formerly D49 in the originating PR): optimizer never recommends sitting out a slate; supersedes CAVEAT_IS_SKIP (a slate that would be demoted to 'skip' is promoted back to 'enter_with_caveat', with the EV signal preserved unchanged).

Player-name resolution hardened (D68, formerly D50 in the originating PR): slate_labels fallback in the freeze + contest-stats parser fallback, closing D49's two open loops so the frozen lineup never ships "Player <id>" placeholders.

# Build status

Set by the build automation. Allowed values: `IN_PROGRESS`,
`BLOCKED_NONFATAL`, `BUILD_COMPLETE`.

Live contest performance is tracked in `RESULTS.md`. First logged slate
(2026-05-28) sat Top 10% / 517th of 8,700 with 2 of 5 picks played.
Finalize a slate without a screenshot via `oracle-results --slate-date
YYYY-MM-DD` (reads frozen_lineups + slate_labels + contest_leaderboards).
DB stores only the top-20, so exact rank / field size still need a
screenshot. See D48.

The 7-day shadow run + watchdog drill are wall-clock operational phases.
All code paths are unit-tested; the manual fire path has been exercised
end-to-end via `scripts/manual_fire.py --fixtures`. The operator starts
the live shadow window via `oracle-rotate-check --window-days 7` after
the live collector has accumulated >= 7 slate labels in `slate_labels`.

## Live services (verified 2026-06-13)

- api:       https://api-production-7033.up.railway.app/health -> 200
- api:       https://api-production-7033.up.railway.app/lineup -> 200
- frontend:  https://frontend-production-a739.up.railway.app/ -> 200
- postgres:  internal + public TCP proxy (TLSv1.3, SSL via start-command cert,
  D61). Alembic head = 20260613_0007 (D90: contest_placements + player_slate_ownership
  applied 2026-06-13). CANONICAL corpus store: slate_labels + contest_leaderboards
  (141+ slates, 2025-05-16..ongoing) + wnba_game_logs (13,456+ player-games,
  2024-05-03..ongoing). All reads via `db.reads` helpers; local parquet files
  are archival backups only.
- redis:     internal, password-protected
- cron-backup (GitHub Action `corpus-backup`): `43 6 * * *` UTC, exports corpus
  to off-`main` `backups` branch (D61). 3-2-1 off-site copy.
- cron-job1: `0 13 * * *` UTC -- scrape Real Sports pool, nba_api minutes,
  odds, RotoWire lineups, player props, persist features_json enrichment.
- cron-job1-late: `*/30 16-23 * * *` UTC (D103, was `35 22`, service id
  2b0cd5aa) -- runs `oracle-cron --job job1late`, the credit-free lite refresh
  (D102/#27): re-scrapes RotoWire and JSONB-merges ONLY the starter/confirmed
  fields onto existing enrichment (no Odds/props re-fetch). Fanned across the
  afternoon+evening so every slate gets confirmed starters before its T-40
  freeze. No Real Sports auth needed (RotoWire + DB only).
- cron-job2: `*/15 14-23,0-3 * * *` UTC -- run heads + optimizer, freeze lineup
  to Redis + Postgres (tip-relative T-40, D93). Late re-freeze when
  LATE_REFREEZE_ENABLED (D75).
- cron-dayclose: `0 6 * * *` UTC -- extend corpus from finalized contest ids
  (D41/D60, service id 606d950d) + nightly wnba_game_logs refresh (D102/#28,
  WNBA_DAYCLOSE_REFRESH_GAMELOGS).
- backfill-enrichment: cron=None (on-demand) -- the ONLY service that should run
  `oracle-cron --job backfill` (historical head_features). Never repoint
  cron-job1/late at it (D103).

## Active Railway env vars (cron-job2, verified 2026-06-13, D91)

Production model: `WNBA_ORACLE_MODEL_ARTIFACT_SHA=94f8e8606dab...`
(picker_e2ced9ec_1780873338.pkl, D77b). Set on api, cron-job1, cron-job2.

| Var | Value | Decision |
|-----|-------|----------|
| PAYOUT_REGIME | top_20 | D48 |
| NEVER_SKIP | true (code default) | D67 |
| CONTRARIAN_ENABLED | true | D51 |
| CONTRARIAN_STRENGTH | 0.2 | D51/D53 |
| OPTIMIZER_MAX_PER_TEAM | 2 | D50 |
| OPTIMIZER_DYNAMIC_TEAM_CAP | true (code default) | D50 |
| OPTIMIZER_N_FIELD_LINEUPS | 500 | D76 |
| OPTIMIZER_BOOST_SUM_CAP | 9.0 | D70/R2 |
| OPTIMIZER_MAX_SINGLE_BOOST | 2.5 | D70/R2 |
| OPTIMIZER_GAME_STACK_BONUS | 0.010 | D70/R3, D98 (raised from 0.005; alignment 56.2%) |
| MINUTES_MODEL_ENABLED | true (code default) | D55 |
| STARTER_SIGNAL_ENABLED | true (code default) | D71 |
| AVAILABILITY_MODEL_ENABLED | true | D73 |
| GAME_SCRIPT_MINUTES_ENABLED | true | D57 |
| LINEUP_ANCHOR_FLOOR | 2 | D57/D58 |
| LATE_REFREEZE_ENABLED | true | D75 |
| PROP_SIGNAL_SCALE | 0.3 | D78 |
| FIELD_MEASURED_OWNERSHIP_ENABLED | true (code default) | D86 |
| CAVEAT_IS_SKIP | false | D48 (superseded by NEVER_SKIP) |
| SAMPLING_SCORE_OFFSET | 2.0 (code default) | D52 |
| FIELD_SAME_GAME_BOOST | 3.0 (D91 calibration, 12.1% beat-median) | D88 |
| FIELD_SAME_TEAM_BOOST | 2.0 (D91 calibration) | D88 |
| OPTIMIZER_DUPLICATION_AWARE_PAYOUT | false (no effect found, D91) | D88 |
| OPTIMIZER_LEVERAGE_WEIGHT | 0.0 (code default, synthesis: double-counts) | D87 |
| OPTIMIZER_CEILING_WEIGHT | 0.0 (code default, arm post-placement loop) | D87 |
| OPTIMIZER_DUPLICATION_WEIGHT | 0.0 (code default, arm post-placement loop) | D87 |
| OPTIMIZER_CEILING_SIGMA_BLOWOUT_BOOST | 0.15 (D89/D92, synthesis starting value, blowout signal active) | D89 |
| OPTIMIZER_CEILING_SIGMA_LOW_HISTORY_BOOST | 0.20 (D89/D92, synthesis starting value, post-D91 calibration) | D89 |
| FREEZE_LEAD_MINUTES | 40 (code default, D93) -- freeze at first_tip - 40min, tip-relative | D93 |

All flags reverse via env with no redeploy. Set *_ENABLED=false or unset numeric
knobs to revert to code defaults.

## Historical corpus (updated 2026-06-21)

All corpus data lives in Postgres (the canonical store). Local parquet
files under `data/historical/` and `data/processed/` are archival backups
only and are no longer read by any script.

### Raw Postgres tables

- `slate_labels`: 157 finalized slates (2025-05-16..2026-06-20), one row
  per player-slate, deduped by player per contest. ~4,500 rows.
- `contest_leaderboards`: top-20 finisher lineups per slate.
- `wnba_game_logs`: ~13.5k player-games across 2024-2026 seasons (454
  players), sourced from stats.wnba.com via nba_api.

### Two corpora, two roles -- DO NOT CONFUSE

The picker trains two distinct kinds of model on two distinct frames:

| Corpus | Builder | Grain | Target | Source | Consumed by |
| --- | --- | --- | --- | --- | --- |
| **Gamelog** (the heads corpus) | `features/corpus.build_gamelog_corpus()` | one row per player-GAME | per-game minutes + real_score-per-min | `wnba_game_logs` (~13k rows) | LightGBM heads (minutes + per-min rate, cohort F) -- the D63 keystone |
| **Label** (the contest corpus) | `features/corpus.build_label_corpus()` wrapping `db/reads.read_label_corpus()` | one row per player-SLATE | realized contest `real_score` | `slate_labels` (~4.5k rows) | EB baseline, real_score blend, CQR calibration |

The label corpus is *not* the training corpus for the heads. It is the
contest-platform corpus that carries `card_boost` and realized contest
points. The heads are starved if trained on it alone (the pre-D63 bug).

All reads go through `src/wnba_oracle/db/reads.py` (D62):
`read_label_corpus()`, `read_slate_labels()`, `read_leaderboards()`,
`read_game_logs()`, `read_player_history()`.

To re-run minutes backfill:
```
set -a && source .env && set +a
uv run python scripts/backfill_minutes.py
```

To re-run contest backfill:
```
set -a && source .env && set +a
export WNBA_DEVICE_UUID=<uuid matching storage_state>
uv run oracle-backfill --mode historical --start-id 1755 --stop-id 1900 \
    --pause-seconds 0.6
```

The day-close cron (`0 6 * * *` UTC) auto-extends the corpus nightly.

## Optimizer correctness (2026-05-27 10:00 UTC)

The pre-fire backfill (D38) surfaced two long-standing bugs in the picker:

- **Slot multipliers were [3.0, 2.5, 2.0, 1.5, 1.0]** (NBA precedent); actual
  WNBA platform uses **[2.0, 1.8, 1.6, 1.4, 1.2]** verified empirically
  across all 320 corpus entries. Fixed in commit `5fb6c6f` and pinned in
  `tests/unit/test_slot_scheme.py`. See D42.

- **Heuristic real_score was 15.0 * (1 + 0.2 * boost)** — wrong magnitude
  (5x too high) and wrong slope (positive; actual relationship is
  -0.45/boost-unit because card_boost is a handicap). Recalibrated to
  `max(0.5, 3.16 - 0.45 * card_boost)`. See D43.

Tonight's 21:00 UTC cron-job2 fire is the first to use the corrected
optimizer. Backtest on 2026-05-25 realized values produced 49.73 points
(brute-force optimum), vs the actual contest winner cpgooner at 40.60.

## Today's slate (2026-05-27) — what to expect

**Cron-job1 fires at 13:00 UTC (8 AM CDT / 9 AM EDT):**
1. Headless re-auth via REALSPORTS_STORAGE_STATE_B64GZ + WNBA_DEVICE_UUID
2. /home/wnba/next + /players/sport/wnba/search a..z pool fetch
3. The Odds API basketball_wnba pull (vegas signals -> features_json)
4. RotoWire WNBA lineups scrape
5. UPSERT into job1_enrichment

**Cron-job2 fires every 15 min from 21:00 UTC through 04:00 UTC** (16:00 CDT
to 23:00 CDT). First fire at 21:00 UTC is when the frontend's countdown
expires and the lineup lands.
1. Load slate from job1_enrichment + slate_labels (drafts if available)
2. Compute per-player heuristic real_score
3. Apply game_script_multiplier (Vegas-driven tier weights)
4. Apply anti-popularity contrarian adjustment
5. Optimize lineup (top-30 -> C(30,5), max_per_team=2)
6. Freeze via Redis SET NX + Postgres UPSERT (with per_player block — D36)

**Frontend** (https://frontend-production-a739.up.railway.app/) polls
/lineup/2026-05-27 every 5-60s with backoff:
- Until 21:00 UTC: full-bleed OracleLoader with countdown to lineup-freeze
- After 21:00 UTC (when job2 first writes): swaps to the 5-card grid

## Where to look if something goes wrong

| Symptom | First place to check |
|---|---|
| Frontend shows countdown past 21:00 UTC | Railway logs for cron-job2 service. Most likely `pool_too_small` (job1 didn't write rows) or `job2_failed` (DB / Redis hiccup) |
| Frontend shows ErrorState block | `curl https://api-production-7033.up.railway.app/health` first; if 200, check api Railway logs |
| Lineup loaded but card names show "Player 12345" | per_player block missing — should be impossible after D36; check job2's `_build_per_player` ran |
| Job1 fails with StorageStateStale | JWT inside REALSPORTS_STORAGE_STATE_B64GZ rotated. Re-run `scripts/realsports_login.py` locally and re-seed the env var on cron-job1 + cron-job2 (NEEDS_CLAUDE item 6) |
| Odds API returns 429 / 401 | Free-tier quota or rotated key. Job1 degrades to empty odds; game_script_multiplier reverts to 1.0x. Lineup still ships, just without the Vegas tilt |

Railway dashboard for logs:
https://railway.com/project/ab83f44c-0bbc-4a58-931c-37d9fbfda73a

## Audit findings + fixes (2026-05-27 03:30-05:30 UTC)

The pre-fire audit surfaced four issues; all fixed before the operator
went to bed.

1. **Critical UX fix — per_player block** (D36): job2 was writing the
   frozen lineup JSONB without a `per_player` array, so the frontend
   would have rendered 5 placeholder cards ("Player 12345", "—", "—",
   all-zero scores) for tomorrow's first slate. Now job2 materializes
   the full projection contract (display_name / team / opponent /
   position / card_boost / pred_real_score_p50 / pred_minutes_p10-p90)
   into the JSONB. Four tests pin the contract in `tests/unit/
   test_per_player_frozen.py`.

2. **Frontend countdown target** (D36): countdown pointed at 13:00 UTC
   (job1 ingest, not user-visible) instead of 21:00 UTC (job2 freeze,
   when the lineup actually appears). Re-targeted; caption changed
   from "Next fire in" to "Lineup freezes in".

3. **Settings env aliases** (D36): pydantic-settings has
   `case_sensitive=True`, so fields without explicit `alias=` (env,
   log_level, payout_regime, optimizer_*, contrarian_*) never picked
   up Railway's uppercase env vars — silently falling back to defaults.
   The current Railway values happened to match defaults so today's
   run was not affected, but any future env-var tuning would have
   silently no-op'd. Added aliases on every uppercase env-var consumer.
   Verified: `ENV=prod LOG_LEVEL=DEBUG CONTRARIAN_STRENGTH=0.25` now
   propagates correctly through `Settings()`.

4. **Railway env hardening** (D35): promoted operational config to
   shared env-scope via `${{shared.KEY}}` references; converted
   DATABASE_URL / REDIS_URL to `${{postgres.DATABASE_URL}}` /
   `${{redis.REDIS_URL}}` service refs; converted frontend
   VITE_API_URL to `https://${{api.RAILWAY_PUBLIC_DOMAIN}}`. Dropped
   GITHUB_TOKEN + RAILWAY_TOKEN from every runtime service; dropped
   REAL_SPORTS_* / WNBA_DEVICE_* / REALSPORTS_STORAGE_STATE_B64GZ from
   api + cron-job2 (only cron-job1 authenticates).

## Known caveats — multi-day work, not blocking tomorrow

These came out of the deep code audit (general-purpose subagent, 2026-05-27
05:00 UTC) and are documented for follow-up; they will NOT block
tomorrow's first frozen lineup.

- **RotoWire lineups fetched but not persisted** (NEEDS_CLAUDE item 7):
  `job1.py:114` calls `fetch_lineups()` and counts the result for the
  log line, but the rows aren't written to `job1_enrichment`. The
  injury-cascade port (D33) only fires through `features/build.py`
  which the live cron path never calls. Impact for tomorrow: players
  RotoWire flags OUT still draft into the optimizer pool; minutes
  redistribution does not apply. The lineup will still ship with
  reasonable picks (boost + Vegas signals carry it), just without the
  injury-aware adjustment.

- **Job2 `_freeze` is not strictly idempotent** (NEEDS_CLAUDE item 8):
  The Redis SETNX guards the lock metadata but the Postgres UPSERT
  fires every invocation. Subsequent cron-job2 fires within the same
  slate window can replace the frozen lineup if new draft data arrives
  via slate_labels and shifts the contrarian adjustment. Documented
  intent vs. behavior mismatch — should either skip the UPSERT when
  the lock is held, or accept the refresh-as-data-arrives semantics
  and rename "freeze" everywhere.

- **Watchdog not wired** (NEEDS_CLAUDE item 9): `scheduler/watchdog.py`
  is a stub returning `[]` and is not called from `cron.py`. Operator
  must read Railway logs manually for failure detection until the
  watchdog + alerting path lands.

## Quality gates

- 365 unit tests pass (D93; was 350). `uv run --extra dev python -m pytest -q`.
  Note: the global `uv run pytest` tool lacks the project deps -- use
  `--extra dev python -m pytest`.
- ruff + mypy on `src/` clean (D93 fixed pre-existing drift the docs had
  claimed clean: 3 ruff + 6 mypy).
- `make determinism-check` repaired (D93 / NEEDS_CLAUDE #14): compares model
  CONTENT via `pipeline.artifact_content_equal`, not pickle SHA.
- 72 source files in `src/wnba_oracle/`.
- 6 basketball-main patterns ported with zero new external dependencies.
- Frontend bundle: 209KB / 66KB gz, builds in ~470ms.

The eval/ bundle is seeded with placeholder JSON. It auto-populates once
the live collector accumulates enough slates (Part 0.4 deliverable list).

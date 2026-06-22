# Live Input Audit — what the picker actually ingests, and what is missing

Audit window: code as of commit `bf3c899` (HEAD, 2026-06-05). Live DB
inspected via `DATABASE_PUBLIC_URL` (`oracle_ro`, verify-ca). Slates checked:
`2026-05-26 .. 2026-06-05` (11 days of `job1_enrichment` + 4 days of
finalized `slate_labels`).

Facts are marked [V] (verified by reading code / DB / live request).
Reasoning is marked [R].

## The signals we say we use vs the signals that actually reach the optimizer

| # | SIGNAL | STATUS | EV impact if added or fixed |
|---|---|---|---|
| 1 | RotoWire confirmed-starter slot (`is_starter`, `rotowire_confirmed`, `starter_slot`) | **INGESTED, BROKEN** — scrape returns 404 [V]; matched-rows 0 across every slate 2026-05-26..06-05 [V] | **HUGE.** Currently the optimizer's anchor/starter signal is silently 0 for the whole league. Fixing it would (a) flip `_starter_multiplier` 1.0 -> 1.10/0.82, (b) populate the `is_anchor` flag for the `LINEUP_ANCHOR_FLOOR=2` seatbelt (today the floor is being satisfied only by minutes-history anchors), (c) feed `availability_probability` the role floors (0.92 starter / 0.70 bench) that collapse cold-start darts. D54 numbers say minutes x rate corr is 0.554 with same-day role and 0.355 without — most of that 0.20 gap is this one signal. |
| 2 | Field draft% (`slate_labels.drafts`) for **today's** slate | **MISSING at decision time** — populated only by `dayclose` cron at 06:00 UTC the morning AFTER the contest finalizes [V]. At freeze (21:00 UTC same day), `_load_measured_drafts(today)` returns empty for every fire I traced; the popularity input falls back to the `pseudo_ppg = 10 + (3 - boost) * 4` estimator [V code]. So our "anti-popularity contrarian" is operating on a card-boost-derived proxy, not actual public ownership. | **HIGH.** Real Sports exposes the live draft counts in-app (Daily Draft Stats panel: "3k / 1k / 384 / 13 ..." per player) per NEEDS_CLAUDE.md #17a. With actual ownership we get (i) correct contrarian penalties (today a 30%-owned boost-2 forward and a 2%-owned boost-3 forward look identical to the estimator) and (ii) a leverage term ceiling x (1 - ownership) instead of the softmax-over-own-projections field model. basketball-main Finding 4 cited a 24-26% value gap between low-owned and high-owned halves; we are leaving most of that on the table. |
| 3 | Per-player minutes & per-min rate (`recent_minutes`, `per_min_rate`, `minutes_vol`, `n_min_games`) | **INGESTED + USED** [V]. Built by `build_minutes_features` from stats.wnba.com `PlayerGameLogs` (league-wide pull) and joined by (initial, last_name, team). Match coverage 47/49 (96%) on 2026-06-01 and 48/48 (100%) on 2026-06-04 [V DB]. Drives `blended_real_score` in job2 plus the `is_anchor` flag plus the sampling sigma. | None — this is the working signal. The model's corr of 0.554 (D54) comes from this. |
| 4 | Card boost (`multiplierBonus`) | INGESTED + USED [V]. Sole source of `_heuristic_real_score` fallback and the visible-value stage-1 filter. | None — this is in. |
| 5 | Vegas total + spread + is_home (per game) | INGESTED + PARTIALLY USED [V]. Spread + total drive `game_script_multiplier` (0.95x..1.07x band, blowout penalty 0.92x) and `blowout_probability`. `is_home` is written into `features_json` but no caller reads it [V — grep returns 0 hits for `is_home` outside the writer in job1 and the build.py training path]. | Low-medium. The game_script multiplier band is +/-5%, much smaller than the per-player projection noise. `is_home` would matter as a small bias (WNBA home win rate ~57% historically [R]) if the model conditioned on it; today it does not. |
| 6 | OUT / IL / INJ / NA / INACTIVE drop | INGESTED + USED [V]. 4-14 OUT players per slate are dropped from the optimizer pool. BUT: the OUT signal does NOT seem to come from RotoWire — RotoWire is 404 [V], yet `is_out=1` rows have `injury_status="Out"` or `"Questionable"` which match Real Sports' own `p.get("injuryStatus")` field [V realsports.py line 502]. The path is: Real Sports `injuryStatus` -> `injury_status` -> `is_out_status()` token match -> drop. RotoWire is layered on top but never wins because it returns 0 matches. | None — this is working, just for a different reason than the comments suggest. Real Sports' own injuryStatus is the load-bearing source today. |
| 7 | Player history (per-player mean `real_score`) | INGESTED + USED [V] via `_load_player_history()` -> `read_player_history()`. Used as a fallback predictor tier between EB model and boost heuristic when no minutes history. | None — already working. |
| 8 | Trained model artifact (multi-task heads, EB baseline) | LOADED BUT DORMANT [V]. The deployed SHA `6182a29d` has 0 heads (per STATUS.md), and the D63 trained heads (corr 0.554) are NOT wired into job2 yet (Phase 2b pending). Without an artifact match, EB-fallback path triggers (`n_eb_predicted` will be 0). | HIGH. The D63 walk-forward corr is 0.554 vs the heuristic's 0.246 (STATUS.md numbers). Activating the trained heads should be the single biggest projection lift once Phase 2b lands. |
| 9 | Same-team / opp-team copula (negative same-team, positive opp-team) | INGESTED + USED [V]. Default rho_same = -0.25, rho_opp = +0.20. Regime-switching variant ARMED on cron-job2 (D57). | Low-medium. The team cap (max 2) already discourages same-team stacks, so the copula change at the margin is small. The 1-game-slate uncapped case (where 3+ stacks ARE the optimal play per top-20 corpus) is where this matters most. |
| 10 | Anti-popularity contrarian | INGESTED + USED [V] but operating on the boost-derived proxy (signal #2). Strength=0.2, max_penalty=0.8 -> peak penalty 0.16 real_score (~5% of median ~2.4). | Low. Even with real ownership the absolute magnitude (~5% nudge) is small because the cap was tuned to keep chalk in the lineup; this is more useful as a tiebreaker than as a top-line projection mover. |
| 11 | Field simulation lineup count | UNDER-PROVISIONED [V]. `optimizer_n_field_lineups=120`, but median actual field is **8,989** entries [V leaderboard parquets, 141 slates]. The 120-lineup field simulates 1.3% of the actual contest. | Medium. The expected_payout estimate is over rank histograms; with 120 sims we cannot estimate top-20 tail probabilities to better than ~10% relative SE. Bumping to 1000+ (after the `expected_payout` vectorization in NEEDS_CLAUDE.md #13a) sharpens the EV ranking among near-tied lineups. |
| 12 | `primary_ranking` (Real Sports' own internal player rating) | INGESTED, NOT USED [V]. Written into `features_json` but no downstream consumer. Range observed 16..32 on 2026-06-04 sample [V]. | Unknown / probably low. We do not know what this number means; the platform may use it for matchmaking, not skill. |
| 13 | Confirmed starters at tip / final inactives | **MISSING.** RotoWire's "Confirmed" badge (~30-90 min before tip per `rotowire.py` docstring) was supposed to be the source. With the 404 + 0 matches it is effectively never observed. job2 fires from 21:00 UTC every 15 min and freezes on the first fire, so a confirmed-status update later in the window would not change a frozen lineup anyway. | HIGH (overlaps with #1). |
| 14 | Late-scratch / pre-tip news (Twitter, beat reporters, "Crystal Ball" style) | **MISSING.** No news ticker, no Twitter feed, no beat-reporter ingest at all. Real Sports' own app has an in-app status string per player (we read `p.get('injuryStatus')` but not the longer status / projected-minutes strings). | MEDIUM. Most pre-tip status changes are reflected in `injuryStatus` already (e.g. Caitlin Clark "Questionable" on 2026-06-04 is captured), but a late scratch arriving after 21:00 UTC is missed because the lineup is frozen. |
| 15 | Vegas line movement vs opening | **MISSING.** `fetch_odds_for_slate` takes one snapshot near 13:00 UTC (job1) and a cached value carries to job2 [V cache TTL 6h]. We never compare to opening, so a sharp move (e.g. spread 8 -> 12) is invisible. | LOW-MEDIUM. WNBA betting markets are thin (basketball-main NBA finding); single-snapshot is probably fine vs the marginal cost of two pulls. |
| 16 | Player props markets (over/unders on points / rebounds / assists) | **MISSING.** Code comment in `odds.py` line 12: "`(later) player_points, player_rebounds, player_assists`". Never wired. | HIGH (potentially). Sportsbook prop lines bake in injury news, role, matchup, minutes — the same things our model reasons about, but priced by sharper analysts. NBA-side research consistently finds prop O/U is one of the best minutes-x-rate proxies available. Cost concern: separate Odds API endpoint, more credits. |
| 17 | Opponent defensive rating + pace | **MISSING from the live freeze.** `team_pace`, `opp_pace`, `opp_def_rtg` are columns in the training feature spec (`features/spec.py`) and `features/build.py` knows how to fill them via `nba_api` LeagueDashTeamStats Advanced. BUT job1 does not call `fetch_team_pace_stats`, and job2's features_json does not contain any of these keys [V — sample features_json above lacks pace/rating fields]. The trained heads will fall back to a per-cohort mean for these columns when activated. | MEDIUM. Per-game pace variance matters for fast-paced vs grind tier classification; today we are using only the Vegas total which is a noisier pace proxy. |
| 18 | Days rest / back-to-back / travel | **MISSING from the live freeze.** `days_rest` and `is_back_to_back` are in the training spec, but the live `features_json` does not have them. The training corpus has them (built from game_logs); the live path does not because job1 has no schedule ingest. `build.py` line 246 hardcodes `pl.lit(2).alias("days_rest")` in the slate path [V]. | LOW-MEDIUM. B2B effect on minutes is real (starters trimmed ~2-4 min on the 2nd night per NBA literature). |
| 19 | National TV game flag | **MISSING.** `FieldPlayerSpec.national_tv` exists with default False; `estimate_draft_popularity` takes an `is_national_tv` kwarg; no caller ever passes True [V grep]. Real Sports has a `tvBroadcaster` field on the game object per MLB precedent [R]. | LOW. National TV slates concentrate ownership ~15% per the existing `estimate_draft_popularity` multiplier; today the multiplier never fires because the input is always False. |
| 20 | Schedule features (`season_game_number`, travel_distance) | **MISSING** for same reason as #18 — no schedule ingest. Hard-coded to 0 in build.py. | LOW. |
| 21 | DvP (defense vs position) | **MISSING.** Allowlisted in `_BASE_FEATURES` + `COHORT_EXTRA_FEATURES`, zero-filled in `build.py` line 205. The trained heads will use the per-cohort mean (effectively zero info). | LOW-MEDIUM. Real DvP would matter for forward/center matchup spots more than guards. |
| 22 | Game time / tipoff for partial-slate windows | NOT USED in the way Real Sports allows. The Real Sports contest is locked at the first tip of the slate (a single freeze time); we DO freeze at the contest lock. Fine. | None. |

## Ranking by EV impact (highest first)

1. **Fix RotoWire scrape (#1, #13)** — restoring the same-day role signal closes the 0.355 -> 0.554 minutes x rate gap. Logged in NEEDS_CLAUDE.md #13b but still open as of 2026-06-05.
2. **Activate the trained heads (#8)** — D63 walk-forward 0.554 vs 0.246 already proven; the offline pickle exists; just needs Phase 2b wiring.
3. **Real ownership from Daily Draft Stats panel (#2)** — replaces the boost-derived popularity proxy and enables a real leverage term.
4. **Player props markets (#16)** — sharpest minutes-x-rate signal a DFS player would price in.
5. **Opponent defensive rating + pace + DvP (#17, #21)** — the training spec already expects these; they would lift the activated model.
6. **Bump field simulation count (#11)** — sharpens EV ranking once the upstream projections are right.
7. **Late inactives within ~1h of tipoff (#13)** — but only meaningful if we ALSO change the freeze policy to allow re-freeze on confirmed news up to a cutoff. Today the first-fire-wins SETNX semantics in `_freeze` make this hard to wire safely.
8. **Schedule features: B2B, travel, days_rest (#18, #20)** — bounded but real.
9. **`is_home` (#5 second half)** — cheap to wire (the data is already in features_json), small effect.
10. **Vegas line movement (#15)** — small effect in a thin market.

## Surprising / load-bearing facts

- The "RotoWire confirmed-starter" signal — described in 4 different code paths as the same-day role override — has been **0 across every player on every slate** observed (11 consecutive slates inspected). The signal is silently absent in production.
- RotoWire WNBA URL `https://www.rotowire.com/basketball/wnba-lineups.php` returns **404** (verified by live curl, 2026-06-05 23:32 UTC). The NBA equivalent `nba-lineups.php` returns 200 from the same User-Agent, so this is a WNBA-specific URL change, not an IP block.
- The OUT-player drop (4-14 per slate) is not really coming from RotoWire — it is coming from Real Sports' own `injuryStatus` field with values like `"Questionable"` and `"Out"`. The code comments suggesting "RotoWire overrides Real Sports" are aspirational right now.
- `_load_measured_drafts(today)` will return empty for every job2 fire, by design — `dayclose` writes `slate_labels.drafts` at 06:00 UTC the morning AFTER the contest finalizes. So the contrarian path is always on the estimator fallback in production, never on the measured value.
- `optimizer_n_field_lineups=120` while the median actual field is **8,989** entries (verified across 141 slates of leaderboard parquets). The field simulation is sampling 1.3% of the real contest.
- `is_home` is computed, written into `features_json`, and never read by anything downstream. Same for `primary_ranking`.

## Pipeline diagram (effective, after dead inputs removed)

```
job1 (13:00 UTC, daily):
  Real Sports pool fetch        [V working]
    -> player ids + boost + injuryStatus + position
  The Odds API (h2h+spreads+totals, 3-bookmaker median) [V working]
    -> per-team vegas_total, vegas_spread, is_home
  RotoWire scrape               [V 404 since at least 2026-06-01]
    -> empty list, 0 matches
  stats.wnba.com PlayerGameLogs [V working, 96-100% match]
    -> recent_minutes, per_min_rate, minutes_vol, n_min_games
  WRITES: job1_enrichment (per-player features_json)

job2 (21:00 UTC, every 15 min until freeze):
  READS: job1_enrichment for today (always pre-tip)
  READS: slate_labels.drafts for today (always empty pre-finalize)
  PREDICTOR mix per player:
    - if minutes_features present AND n_games >= 2:
        blended_real_score(boost, recent_minutes, rate)  [V D55 path, dominant]
    - else if EB baseline has this player_id: EB prediction
        (won't trigger today: deployed sha has 0 EB players)
    - else if player_history dict has pid: corpus mean
    - else: heuristic 3.16 - 0.45 * boost
  MULTIPLIERS applied per player:
    - game_script_multiplier(total, spread)  [V 0.95..1.07x band]
    - _starter_multiplier (only when rotowire_confirmed=1) [V never fires]
    - availability_probability (when minutes present + maybe rotowire role) [V partial]
    - injury_cascade bonus from OUT donors  [V firing 4-14 per slate]
    - contrarian_adjustment on boost-derived popularity  [V firing, weak]
  OPTIMIZER:
    - top-30 filter by visible_value
    - 120 field-lineup sims (vs actual ~9000)
    - C(30, 5) enumeration under team-cap + anchor-floor
    - first-fire-wins SETNX freeze
```

## Open questions

- Does `primary_ranking` (Real Sports' own per-player rating, range observed 16-32) encode something useful, or is it matchmaking metadata? Need to correlate with realized real_score.
- Real Sports' in-app Daily Draft Stats panel exposes live draft counts. Is it scrapable from the same auth flow as the pool, or does it require a different endpoint? NEEDS_CLAUDE.md #17a says "needs a new job1 scrape + parser; do NOT rush it live (RotoWire-404 caution)."
- The Real Sports pool already carries an `injuryStatus` string with values like "Questionable" / "Out" / "Active" / "Day-To-Day". Is there a longer status string available on the per-player endpoint that the pool fetch is dropping?

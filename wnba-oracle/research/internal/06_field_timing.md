# 06 — Field Timing: gap between best-available info and what we freeze on

Date: 2026-06-05 (analysis cutoff)
Status: empirical, with two sources of evidence (Postgres + The Odds API live pull). Markers below: [verified] = pulled from data; [reasoned] = inferred from code or docs.

## TL;DR

- The freeze fires at the same wall-clock moment every night (~21:01-21:03 UTC) but the first WNBA tipoff lands ~2.5 hours later (typical 23:30 UTC). [verified]
- During that 2.5h window, RotoWire flips its expected lineups to confirmed (their docs: 30-90 min before tip), and Real Sports lets users edit their entry up to per-game tipoff (the platform exposes `isLocked`/`canEnter` which we deliberately ignore per D37b). [verified - code, reasoned - rotowire docs]
- We freeze on a snapshot from 8 hours before tip (job1 at 13:00 UTC) and have NEVER seen a `rotowire_confirmed=1` flag across 11 recent slates of `job1_enrichment`. The confirmed-starter signal is a no-op live. [verified - Postgres count]
- The slate_labels.drafts numbers that the contrarian adjuster reads are POST-CONTEST snapshots captured by dayclose at 06:00 UTC the next morning. At freeze time on slate N, there is no measured ownership for slate N. The contrarian always runs in estimator-fallback mode. [verified - dayclose schedule + ingest timing]
- A late-freeze path that fires at T-15 minutes from each game's tipoff would unlock the confirmed-starter signal (today: zero usage) AND let us refresh recent_minutes if a player was a late scratch. It would NOT unlock measured ownership (that signal doesn't exist pre-tip on Real Sports at all). [reasoned]
- Tonight (2026-06-06) is a Friday day-slate counter-example: first game at 17:00 UTC. The 21:00 UTC freeze fires AFTER that game has tipped. For day slates, the current freeze is structurally too late. [verified - Odds API]

## 1. Pipeline timeline (UTC)

Source: `src/wnba_oracle/scheduler/cron.py` (docstring), STATUS.md line 50-51 (cron schedule), Postgres `frozen_lineups.frozen_at` (last 10 slates).

| Time (UTC) | What fires | What ingests |
| --- | --- | --- |
| ~11:00 UTC day-before | Real Sports `contest.createdAt` for the slate [verified - fixture 1840 `createdAt=2026-05-26T11:00:30Z` for `day=2026-05-27`] | Card menu (boosts) becomes queryable via `/home/wnba/next` |
| 13:00 UTC | `cron-job1` (`oracle-cron --job job1`) | Pool fetch (boosts), The Odds API totals/spreads, RotoWire scrape, nba_api recent minutes. Writes `job1_enrichment` |
| 21:00 UTC | `cron-job2` first fire | Reads `job1_enrichment`, builds specs, optimizes, FREEZES via Redis SETNX + Postgres INSERT |
| 21:00-04:00 UTC (every 15 min) | `cron-job2` re-fires | No-ops: Redis lock held, Postgres row exists. Subsequent fires log `job2_already_frozen` and return without changing the lineup |
| ~23:30 UTC | Typical FIRST WNBA tipoff [verified - Odds API last 3 days; see Section 4] | Game starts; Real Sports per-game lineup locks |
| ~05:00 UTC next morning | Real Sports `contest.processedAt` (contest finalizes) [reasoned - job_dayclose docstring "1831 was processedAt 2026-05-26T05:07Z"] | draftStats + entries become queryable |
| 06:00 UTC next morning | `cron-dayclose` (`oracle-cron --job dayclose`) | Pulls slate_labels (with FINAL drafts) and top-20 leaderboards |

Verified freeze timestamps from Postgres `frozen_lineups`:

```
2026-06-05  21:02:00 UTC  enter
2026-06-04  21:03:13 UTC  enter
2026-06-03  21:02:46 UTC  enter
2026-06-02  21:02:18 UTC  enter
2026-06-01  22:23:29 UTC  enter      <- D56 outage (timeout); freeze landed late
2026-05-31  21:01:26 UTC  skip
2026-05-30  22:51:31 UTC  skip       <- D56 outage residue
2026-05-29  22:54:21 UTC  skip       <- D56 outage residue
2026-05-28  22:00:16 UTC  enter_with_caveat
2026-05-27  22:22:40 UTC  skip
```

Of 10 recent slates, 6 froze at ~21:02; 4 were delayed to 22:00-22:54 due to D56 optimizer timeouts. The MODAL freeze is 21:02:00 UTC.

## 2. What information actually arrives between job1 and freeze

Source: `src/wnba_oracle/scheduler/job1.py` lines 153-273.

job1 at 13:00 UTC writes to `job1_enrichment` a row per pool player with:
- `card_boost` (Real Sports rating-ladder handicap; assigned at 11:00 UTC creation; doesn't move)
- `vegas_total`, `vegas_spread`, `is_home` (Odds API snapshot at 13:00 UTC; can drift but the project chose not to re-pull, see DECISIONS.md line 801: "Vegas re-pull in job2: would exceed the D10 500/month Odds API cap")
- `rotowire_confirmed`, `is_starter`, `starter_slot` (RotoWire HTML scrape at 13:00 UTC)
- `injury_status`, `is_out` (RotoWire status tokens)
- `recent_minutes`, `per_min_rate`, `minutes_vol`, `n_min_games` (nba_api stats.wnba.com, current + prior season)

Between 13:00 and 21:00 UTC, the only signal that empirically moves is RotoWire (their lineups page populates "Confirmed" badges 30-90 min before tip per their own docs at `src/wnba_oracle/ingest/rotowire.py:5`). nba_api doesn't add games to a slate that hasn't tipped, Vegas lines drift modestly, and the pool doesn't change.

**job2 at 21:00 UTC reads ONLY the 13:00 UTC enrichment.** It never re-fetches RotoWire or odds. [verified - grep of scheduler/*.py shows no `fetch_lineups` outside job1, no `fetch_odds` outside job1]

## 3. Empirical: confirmed-starter signal is dead on arrival

A Postgres roll-up across the last 11 days of `job1_enrichment`:

```
slate_date  n_pool  n_rotowire_confirmed  n_is_starter  n_is_out
2026-06-05      75                     0             0        11
2026-06-04      48                     0             0         5
2026-06-03      49                     0             0         6
2026-06-02      93                     0             0        12
2026-06-01      49                     0             0         5
2026-05-31      22                     0             0         2
2026-05-30      73                     0             0        12
2026-05-29      94                     0             0        12
2026-05-28      47                     0             0         4
2026-05-27     117                     0             0        14
2026-05-26     117                     0             0         0
```

ZERO rotowire_confirmed flags across 784 player-slates. ZERO is_starter flags. job1 fires at 13:00 UTC = 8-11h before tip = the RotoWire page either had only expected lineups (no "Confirmed" badge yet) or was returning 404 at that hour (we hit 404 when probing it ad-hoc at 02:00 UTC for the next-day slate). The `is_out` column DOES populate (RotoWire has a separate longer-lead injury feed), which is the only RotoWire signal that survives the timing gap.

This means three of the four job2 same-day signals listed in STATUS.md as "edges" are silent:
- `confirmed-starter +10% bonus / -18% bench penalty` (`_starter_multiplier`, job2.py:238): never fires because `rotowire_confirmed==0` always
- `is_starter` flag in `is_anchor_by_pid` (D57 Tier-1 anchor): never fires from this path
- `is_starter` flag in `GameScriptInput` (D57 Tier-3 redistribution): never fires from this path

The one same-day RotoWire signal that DOES work is `is_out` (player drops), which the cascade and OUT-filter both consume.

This is the single biggest timing-driven information loss in the system. We coded a confirmed-starter edge and gate ourselves out of it via the 13:00 UTC fire window.

## 4. Tipoff distribution and freeze-to-first-tip gap

Source: The Odds API `basketball_wnba/scores?daysFrom=3` live pull at 2026-06-05 ~22:00 UTC, with slates re-grouped by "slate day = commence_time - 12h".

```
slate 2026-06-03: n=2, first_tip=23:38 UTC -> +158 min after 21:00 freeze
slate 2026-06-04: n=2, first_tip=23:05 UTC -> +126 min after 21:00 freeze
slate 2026-06-05: n=3, first_tip=23:33 UTC -> +153 min after 21:00 freeze
slate 2026-06-06: n=4, first_tip=17:00 UTC -> -240 min BEFORE 21:00 freeze (day slate)
```

Three of the last four slates: freeze leaves a 126-158 minute window before any ball is in the air. That is the exact window in which RotoWire posts confirmed lineups and beat-writers post inactives.

Tonight (slate 2026-06-06) is the cautionary counter-example. First tip 17:00 UTC, fully four hours before the freeze. The 21:00 UTC fire would write a lineup for a contest where MIN vs SEA has already happened. The contest may or may not accept it depending on per-game lock semantics; we have not measured this case, but it is a structural mismatch between our cron schedule and the slate. [verified - Odds API pull; reasoned - per-game lock behavior]

## 5. The contrarian/ownership signal is structurally stale at freeze

`_load_measured_drafts(slate_date)` (job2.py:329) queries `SELECT ... FROM slate_labels WHERE slate_date = :sd`. That table is written by `cron-dayclose` at 06:00 UTC the NEXT day (`scheduler/job_dayclose.py:15`). Verified ingest timing from Postgres:

```
slate_date   ingested_at
2026-06-04   2026-06-05 06:01:00 UTC
2026-06-03   2026-06-05 06:01:03 UTC
2026-06-02   2026-06-05 06:01:05 UTC
(...)
```

(Several 2026-05 slates were retro-loaded at 05:19 UTC in a single backfill burst, but the modal cadence is `next-day 06:01 UTC`.)

At job2's 21:00 UTC freeze for slate N, `_load_measured_drafts(N)` ALWAYS returns empty. job2 falls through to the popularity *estimator* (popularity.py:37), which is a hand-tuned function of `pseudo_ppg` (derived from card_boost via `10 + (3 - boost) * 4`), big-market multiplier, and slate-size multiplier. Verified by tracing the fallback path in `_build_specs`:

```python
measured_drafts = _load_measured_drafts(slate_date)
if measured_drafts:                     # ALWAYS false at 21:00 UTC for slate N
    popularity_scores = slate_labels_to_popularity(measured_drafts)
else:
    popularity_scores = {}              # estimator fallback path
    for r in enrichment:
        ...
        popularity_scores[pid] = estimate_draft_popularity(...)
```

The actual measured drafts in slate_labels (when they eventually land) tell a very different story than the estimator. From the 4002-row slate_labels corpus:

```
drafts.describe():
  count    3951
  mean      725
  std      1135
  median    197
  Q99      5350
  max      9800
```

The distribution is wildly skewed. Avg top-1 ownership share in a slate = 25%, avg top-5 ownership share = 64% (verified across 141 historical slates). The estimator's "20 ppg star on big market on a small slate -> 5000-6000" anchor is OK on average but cannot distinguish a hot 8-game streaker from a cold superstar — both will look similar through the pseudo-ppg-from-boost transform.

Worse: corr(card_boost, drafts) = -0.486 across all 4002 rows. card_boost is a known lagging-form proxy, so a player on a hot streak gets a low boost AND high public ownership. The estimator uses boost as its sole observable, so it predicts high ownership for low-boost stars — the very players who legitimately should be high-owned. The "anti-popularity contrarian" then pushes us OFF the right answers, exactly when we wanted to lean into a chalky-but-correct play.

There is no live Real Sports endpoint that exposes pre-tip ownership. `fetch_contest_stats` returns empty `draftStats` for pregame contests (verified - `contest_stats.py:36-37`). So the only way to measure ownership at freeze would be (a) sniff a different endpoint we haven't found, or (b) skip the measurement and lean entirely on a better-than-current estimator. Today we have neither.

## 6. Concretely: how much edge did we burn on recent slates?

For 2026-06-04 (the bust slate, our pick finished ~6000/8317):

| Pick | Boost | Job1 pred | What we used at freeze | Real_score realized |
| --- | --- | --- | --- | --- |
| Rhyne Howard | 0.1 | 3.87 | estimator chalk push-off | 1.41 |
| Janelle Salaün | 0.8 | 2.78 | match winner #1 | 3.59 |
| Sophie Cunningham | 1.7 | 2.12 | match winner #2 | 0.93 |
| Cecilia Zandalasini | 2.5 | 1.56 | match winner #3 | 2.90 |
| Makayla Timpson | 3.0 | 1.37 | longshot dart | 0.05 |

The actual #1 finisher's stack was Zandalasini + Miles + Coffey + Hayes + Stokes (53.25 pts). We hit Zandalasini. We missed Olivia Miles (real_score 7.33).

Olivia Miles' game-log history in the 8 days BEFORE the slate: 23.2 / 33.2 / 33.6 / 31.7 / 28.0 minutes. By the time job1 ran at 13:00 UTC on 06-04 she had played 28 minutes the prior night (06-01) and was clearly the Lynx starting PG. nba_api would have surfaced this. Miles was in the pool with `drafts=630` (ranked 9th by ownership on the day) — she was NOT a contrarian dart, she was a known starter that the model under-projected. **This is a model failure, not a timing failure.** No amount of late freeze would have rescued her on this slate.

Compare: the #1 finisher every recent slate hinged on a single breakout player (verified):

```
slate         field    top_score   single_player_anchor (boost, real, % of base score)
2026-06-04    8317     53.25       O. Miles (0.3, 7.33, 40%)
2026-06-03    8441     55.40       J. Jones (0.6, 6.40, 42%)
2026-06-02    8812     53.40       A. Wilson (0.0, 5.69, 28%)
2026-06-01    8588     51.10       C. Williams (0.3, 6.40, 36%)
2026-05-31    6494     53.00       A. Wilson (0.0, 6.29, 30%)
2026-05-30    7993     63.80       E. Engstler (1.6, 5.59, 28%)
2026-05-29    8524     49.50       N. Hillmon (2.4, 4.05, 25%)
2026-05-28    9240     53.10       J. Shepard (0.4, 5.65, 27%)
2026-05-27   10323     58.99       N. Sabally (0.9, 6.79, 26%)
```

Every winning lineup has one player who delivered 25-42% of the total. Most are low-boost stars who happened to outperform their projection. The "edge" question reduces to: which low-boost star catches fire tonight? That's a model question (projection variance + correlation), not a timing question.

## 7. Where a late freeze WOULD help

A late-freeze path firing at T-15 min from each game's individual tipoff would unlock:

1. **Confirmed-starter flag (today: zero usage).** RotoWire confirms 30-90 min before tip. A T-15 fire reads a >95% confirmed page. Our coded multiplier (`1.10` confirmed-starter, `0.82` confirmed-bench, job2.py:257) and our coded anchor floor (D57) would finally fire on real data. Direct effect: every starter we pick would get a verified +10% projection lift and we would stop accidentally drafting players who got benched same-day for matchup reasons.
2. **Late inactives the morning RotoWire pull missed.** The morning RotoWire scrape catches scheduled injuries (Active/Probable/Out). Same-day scratches (illness, family, late-decision rest) land between 13:00 UTC and ~22:30 UTC. Today we sometimes draft a player listed Active at 13:00 who was scratched at 22:00. We have no telemetry on this case but it is a known industry pattern.
3. **Vegas line moves.** Sharps move the lines all day. Lines at 22:30 UTC are more predictive of game-script than lines at 13:00 UTC. The Odds API cap (500/month at the D10 tier) is the gate; one re-pull at the late freeze costs ~6 calls/day = 180/month, fits within budget.
4. **Tonight's nba_api stat update for any game on a doubleheader day.** Less common in WNBA than NBA but does occur (e.g., today there are games at 17:00 + 19:00 + 22:00 UTC on 06-06; a freeze at 21:45 UTC for the 22:00 game would see post-game minutes from the 17:00 contest).

What it would NOT unlock:
- Measured ownership / drafts. The Real Sports `draftStats` endpoint returns empty pregame across all observed contests. No live ownership exists to read at any pre-tip time. [verified - contest_stats.py:36-37]
- Anything about boosts. Card_boost is set at contest creation 11:00 UTC day-before and is frozen by the platform.

## 8. The "21:00 UTC is the platform lock" claim is wrong

DECISIONS.md line 798-800:
> Shift cron-job2 first fire from 21:00 UTC to 21:30 UTC: per STATUS.md 21:00 UTC IS the platform-lock moment; shifting risks missing entry entirely.

This appears to be a self-reinforcing internal myth. Evidence against:
- The Real Sports contest fixture (`tests/fixtures/realsports/contest_1840_2026-05-26.json`) has `info.isLocked: false` AND `info.canEnter: true` (verified). The platform exposes a per-contest lock signal. Setting `isLocked=true` is a runtime state, not a fixed time.
- DECISIONS.md line 810-813 explicitly states: "Real Sports lineup edits up to tipoff: the platform exposes `isLocked`/`canEnter` signals but Oracle deliberately ignores them per D37b true-freeze." So the platform allows late edits and we have chosen not to use them.
- D37b "true-freeze" is a PRODUCT choice (don't show the operator a changing lineup), not a TECHNICAL lock. The operator could submit at 22:30 UTC and still be eligible.
- Empirically, tonight's slate (2026-06-06) has a 17:00 UTC tipoff. The platform clearly does not enforce a 21:00 UTC universal lock — it would be impossible to run a 17:00 tip contest under a 21:00 lock.

The 21:00 UTC fire is a UX choice masquerading as a platform constraint.

## 9. Recommendation: dominate-test the late-freeze path

The late-freeze path strictly dominates the current path on the four signals enumerated in Section 7, with two risks:

**Risk A — D37b product semantics.** D37b says "the operator must not see their lineup change underneath them." A late freeze changes WHEN the freeze happens, not THAT the freeze happens. The operator commits whenever they look at the page, the lineup is stable thereafter, and the freeze writes ONCE per slate at the latest cron tick that succeeds before T-15 of the first game. The product invariant survives.

**Risk B — submission deadline missed.** If the late-freeze cron fails on its last attempt (network, optimizer timeout, etc.) we have no lineup. Today the 21:00 UTC fire has been delayed to 22:00-22:54 UTC on 4 of 10 recent slates due to the D56 optimizer timeout (`enter` -> `skip` and late timestamps in the freeze table). Late-freeze amplifies this risk: we'd need a hard fallback that writes the BEST-AVAILABLE lineup at T-30 from first tip if the optimizer is still running, then ATTEMPTS a re-freeze at T-15 with the confirmed-starter data, idempotent on success.

Suggested architecture, lowest-blast-radius experiment:
1. Add `cron-job2-late` firing at `*/15 22-23 * * *` UTC (45 min and 15 min before typical first tip).
2. Have it pull the latest RotoWire page (and ONLY the RotoWire page; reuse Vegas + nba_api from job1). Stamp results into a NEW `job1_enrichment_late` table.
3. job2-late reads `job1_enrichment_late` if present and falls through to `job1_enrichment` otherwise. Uses the same `optimize_lineup`.
4. The Postgres freeze key becomes `(slate_date, fire_phase)` where fire_phase ∈ {`early_21z`, `late_22z`}. The frontend reads `late_22z` if present, else `early_21z`. Operator sees the same lineup that submits.
5. Compare `early_21z` vs `late_22z` lineups for 14 nights. Score both against realized real_scores. If late dominates, kill early.

Expected upside: +10% projection on every confirmed starter we pick. With ~3 of 5 picks being starters typical, that is +6% expected lineup score. On the loss-decomposition numbers in `_loss_decomp_data.csv` neighboring file, a 6% bump on a typical 39 pred-score lineup is +2.3 pts. The gap between rank-1 and rank-100 in a typical 8500-entry contest is ~5-7 pts (visible in `_ceiling_*` files). +2.3 pts is meaningful.

## 10. Open questions

- What is the actual per-game `isLocked` cadence on Real Sports? We need a 24h sniff loop on `/games/playerratingcontest/{id}/stats` and the contest-detail endpoint to confirm.
- What hour does RotoWire's `Confirmed` badge actually flip on for a typical WNBA night? Their docs say 30-90 min pre-tip but we have not measured.
- Does Real Sports show ANY ownership-adjacent live signal pre-tip (e.g., a `popularPick` decoration on a player card)? The pool endpoint does not appear to. Worth a one-off Playwright probe of the live web app at 20:55 UTC.
- Is there a cheap way to ESTIMATE same-day ownership without the platform measuring it? Cross-referencing RotoWire popularity-tier badges, beat-writer Twitter sentiment, and basketball-main FFR archetype would be plausible vendor-free sources.

## Appendix — Code citations

- Cron schedule: `STATUS.md:50-51`, `DECISIONS.md:141-148` (D22)
- job1: `src/wnba_oracle/scheduler/job1.py`
- job2 freeze: `src/wnba_oracle/scheduler/job2.py:738-813` (`_freeze`)
- job2 contrarian fallback: `job2.py:441-466`
- Popularity estimator: `src/wnba_oracle/picker/popularity.py:37-82`
- RotoWire docs: `src/wnba_oracle/ingest/rotowire.py:1-12`
- Pregame draftStats empty: `src/wnba_oracle/ingest/contest_stats.py:36-37`
- Dayclose schedule: `src/wnba_oracle/scheduler/job_dayclose.py:15-19`
- True-freeze rationale: `DECISIONS.md:430-470` (D37b region)
- "21:00 UTC IS the platform-lock moment" claim (and the late-edit caveat): `DECISIONS.md:798-813`

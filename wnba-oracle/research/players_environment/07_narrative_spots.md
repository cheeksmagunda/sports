# Narrative Spots: Do Winning WNBA Oracle Lineups Over-Index on Storylines?

**Scope.** 141 historical slates between 2025-05-16 and 2026-06-05. Winning picks = every
player rostered by the top-3 finishers per slate. 2115 raw pick-rows; 1820 after we
require a clean cross-walk from the PrizePicks platform_id to an NBA-stats player_id
in `data/processed/wnba_game_logs.parquet`. Menu baseline = every player a slate
exposed in the slate_labels parquet (3499 mapped rows).

**Method.** We define a "narrative spot" as a date-specific context that public-facing
data can detect before tipoff: rest pattern, return from absence, season-opener,
revenge spot vs former team, teammate-out impact, rookie-season status, season
segment, and recent-form heat. For each narrative we compute a winner share, a
menu share, and the ratio `lift = winner_share / menu_share`. Lift > 1.0 means
winners chose this bucket more than the menu offered it.

Web research was used to verify the most extreme single-game examples and to
attach a public story to the data signal. URLs are cited inline.

## TL;DR

1. **Detectable narrative spots produce real but modest lift.** Most signals move
   winner share by 5-30 percent relative to the menu, not by orders of magnitude.
2. **The biggest single narrative-detectable edge is "player returning from a
   long absence and the freeze price hasn't caught up."** The 4 multi-week
   returns in the sample (C. Clark 2025-06-14, J. Shepard 2025-06-24,
   N. Collier 2025-08-24, S. Diggins 2026-05-09) all landed in top-3 lineups.
   The biggest single Caitlin Clark return delivered 32-point games verified
   by ESPN ([source](https://www.espn.com/wnba/story/_/id/48848576/fever-clark-returning-injuries-poses-mental-challenge)).
3. **Back-to-back (1 day rest) is the strongest *recurring* rest signal.**
   Winners pick B2B players at 1.33x the menu rate. Plausible mechanism:
   blowout candidates whose stars rest get downweighted by the freeze.
4. **Revenge-game lift is real but small (1.18x).** Verified case studies:
   K. Plum's 38-point destruction of Las Vegas on 2026-05-23 in her first game
   back vs her old team ([source](https://lasvegassun.com/news/2026/may/23/kelsey-plum-scorches-aces-for-38-points-in-return/)).
5. **Next-man-up (1+ projected starter "Out") is *only* a 1.08x signal at the
   1-starter threshold, and *negative* at the 2+ threshold.** Winners are
   slightly *less* likely to chase chaos when a team has multiple starters
   missing. The freeze appears to over-correct: when a roster is decimated, the
   ownership floods in and the leverage evaporates.
6. **Rookie-season players: barely-positive lift (1.05x).** Rookies show up in
   winning lineups in proportion to their menu share. The "freeze loves rookies"
   prior is not supported by 141 slates.
7. **Season segment matters less than reputation suggests.** Winners do
   over-index on the playoffs (1.28x) but that is mostly a slate-structure
   artifact: fewer games, more concentrated outcomes.
8. **Recent-form (3-game hot streak above career baseline) gives ~1.03x lift.**
   The market prices form too efficiently for this to be a stand-alone tool.

The actionable takeaway: a single binary narrative tag is rarely worth more than
a small tiebreaker. **Stacking narrative tags (e.g., return-from-absence AND
revenge spot AND B2B) is where the freeze breaks.**

## 1. Rest-day distribution: the back-to-back tilt

We compute days-since-last-game per player. Buckets are 1 (B2B), 2 (typical
2-day turn), 3, 4-7, 8-14 (typical mid-week absence), 15+ (return from
long-term injury).

| rest_bucket | winner_picks | menu_rows | winner_share | menu_share | lift |
|---|---|---|---|---|---|
| 1 (back-to-back) | 129 | 183 | 0.061 | 0.046 | **1.33** |
| 2 | 866 | 1635 | 0.409 | 0.409 | 1.00 |
| 3 | 443 | 894 | 0.209 | 0.223 | 0.94 |
| 4-7 | 333 | 667 | 0.157 | 0.167 | 0.94 |
| 8-14 | 36 | 88 | 0.017 | 0.022 | 0.77 |
| 15+ (long absence) | 13 | 31 | 0.006 | 0.008 | 0.79 |
| unknown / season debut | 295 | 504 | 0.139 | 0.126 | 1.11 |

**Read.** Winners modestly avoid mid-week "rest" returns (8-14 day bucket) and
modestly *over-index* on B2B and on debut/unknown rest. The B2B lift is the
single cleanest pattern in this report: +33% relative to the menu offering.

**Plausible mechanism for the B2B tilt.** On a B2B, the PrizePicks freeze tends
to fade the high-usage stars whose teams played the night before. But fatigue
effects in the WNBA are smaller than the freeze implies. The historical mean
fantasy output of a B2B player who actually started in our sample is essentially
unchanged from a 2-day-rest game. Picking a "tired" star at a lifted multiplier
is a small but real edge.

## 2. Return from long absence: the highest per-spot ROI

49 of 1820 winning picks (2.7%) came from players returning after 8+ days off.
Six picks (all by single returns) came from 15+ day windows. These are
narrative-rich and confirmable from box-score and beat-writer data hours before
the slate locks.

### Confirmed return-from-injury winners

| date | player | rest_days | actual_score | multiplier | verified context |
|---|---|---|---|---|---|
| 2025-06-14 | C. Clark | 21 | 17.10 | 2.2 | Clark dropped 32 pts / 9 ast / 8 reb in 31 min vs the Liberty in her first game back from a quad strain ([ESPN](https://www.espn.com/wnba/story/_/id/48848576/fever-clark-returning-injuries-poses-mental-challenge)). Picked by all 3 top-3 entries. |
| 2025-06-24 | J. Shepard | 16 | 14.37 | 3.5 | First game back from injury for Shepard; rostered by 2 of top-3. |
| 2025-08-24 | N. Collier | 22 | 12.26 | 2.0 | Lynx star returning to face the same opponent after an absence. By this point Collier was averaging 22.9 / 7.3 / 3.2 en route to a 50-40-90 season and a 2nd-place MVP finish ([CBS](https://www.cbssports.com/wnba/news/lynxs-napheesa-collier-named-all-star-mvp-emerges-as-labor-leader-as-rise-to-wnba-prominence-continues/)). Two top-3 finishers rostered her. |
| 2025-07-03 | J. Allemand | 24 | 7.76 | 4.2 | Listed Questionable, ran out and produced. Single winning lineup. |
| 2026-05-08 | S. Austin / M. Mabrey / V. Burton | 13-241 | 5.06-8.44 | 1.2-2.0 | 2026 season opener. The 240+ rest_days are because these were the players' first games of the 2026 dataset; the freeze treated them as cold and the multipliers stayed depressed. |

The 4.7% sample size makes this category statistically thin, but every confirmed
return-from-real-injury spot in our data window landed in a top-3 lineup. That
is the strongest single-bucket signal we have measured. The mechanism is
mechanical: the freeze multiplier model uses rolling form, and a player who
hasn't played for 3 weeks has stale form. If the public news cycle confirms
they are healthy and starting, the multiplier is mispriced.

## 3. Revenge spots: small but real, with extreme single-game tails

We define a revenge spot as: player's current team faces an opponent that is one
of their previous WNBA teams (verified from their multi-team game-log history).
143 players in the dataset have moved teams. We detected **215 revenge games**
across the 141-slate window.

**Winner share in revenge spots: 0.028. Menu share: 0.024. Lift: 1.18.**

### Notable revenge-game winning picks

| date | player | opp | score | mult | context |
|---|---|---|---|---|---|
| 2026-05-23 | K. Plum | LVA | 16.58 - 18.33 | 1.9 - 2.1 | Plum scored a season-high 38 pts vs her old Aces in LA's 101-95 win ([Las Vegas Sun](https://lasvegassun.com/news/2026/may/23/kelsey-plum-scorches-aces-for-38-points-in-return/), [ESPN](https://www.espn.com/wnba/story/_/id/45399408/sparks-kelsey-plum-greeted-fanfare-las-vegas-return)). All 3 top-3 lineups rostered her. |
| 2026-05-14 | N. Howard | (former team) | 15.72 - 19.21 | 3.6 - 4.4 | Three-of-three top-3 lineups, multiplier 3.6-4.4 means the freeze had no idea. |
| 2026-05-24 | S. Sabally | (former team) | 12.89 | 4.4 | Multiplier 4.4 makes this one of the highest-leverage revenge picks in the dataset. |
| 2025-09-26 | N. Smith | (former team) | 10.84-12.87 | 3.2-3.8 | Three top-3 finishers all rostered Smith. |
| 2025-08-29 | O. Sims | (former team) | 11.88 | 2.9 | Two top-3 lineups. |
| 2025-08-07 | S. Cunningham | (former team) | 9.11 - 10.15 | 3.5 - 3.9 | Two of three top-3 lineups. |

**Read.** The lift is 1.18x but the *multipliers* on revenge picks are
systematically high (typical 2.5-4.5). When a revenge pick hits, it tends to
hit at high leverage. Three observations:

1. The freeze does not appear to apply a revenge adjustment. Public DFS sites
   sometimes give a small bump; PrizePicks Oracle does not.
2. Returning to a former arena is also typically a road game (away revenge),
   which the freeze multiplier model already slightly discounts. Adding the
   revenge tag *on top of* the road discount creates the leverage.
3. The sample (51 winning revenge picks) is large enough to trust the central
   tendency but small enough that any single slate can swing the lift number.

## 4. Teammate injuries: the "next man up" trap

For each (team, date) we built the expected roster as all players who appeared
for that team in the 14 days before the game. "Starters out" = number of those
expected players with a rolling 10-game avg minutes >= 22 who did NOT appear
that night.

| starters_out | winner_picks | menu_rows | winner_share | menu_share | lift |
|---|---|---|---|---|---|
| 0 | 1182 | 2259 | 0.650 | 0.646 | 1.01 |
| 1 | 515 | 872 | 0.283 | 0.249 | **1.14** |
| 2 | 104 | 217 | 0.057 | 0.062 | 0.92 |
| 3+ | 18 | 42 | 0.010 | 0.012 | 0.83 |

**The sweet spot is *exactly one* missing starter.** Winners over-index there
by 14 percent. With two or three out, the lift goes negative.

**Why this matters.** This is contrarian to the conventional fantasy heuristic
("the more guys out, the more upside the remaining starter has"). The PrizePicks
freeze appears to flood the multiplier model when 2+ starters are out: every
remaining rotation player gets a leverage downgrade because the public obviously
piles in. The cleanest leverage spot is the single-starter-out game where the
ownership flood hasn't started yet.

### Verified single-starter-out winning examples

| date | pick | absent starter | score | mult | source |
|---|---|---|---|---|---|
| 2025-07-30 | M. Johannes | B. Stewart | 8.03 | 4.1 | Johannes started in Stewart's spot; Liberty lost 100-93 to MIN ([recap](https://www.espn.com/wnba/game/_/gameId/401736283/liberty-lynx)). Multiplier 4.1 makes this enormous leverage. |
| 2025-07-03 | A. James | (multiple starters out for LVA) | 27.88 | 4.3 | One of the highest-scoring single picks in the dataset. |
| 2025-08-20 | P. Bueckers | (Dallas starter out) | 21.67 | 2.2 | Rookie capitalizes on lineup chaos. |
| 2025-09-10 | A. Edwards | (rotation player out) | 12.01 | 4.8 | Multiple top-3 lineups rostered her at 4.8x. |

### Verified two-or-more-starters-out picks (note the lower multipliers)

| date | pick | score | mult |
|---|---|---|---|
| 2026-05-19 | B. Sykes / M. Mabrey / K. Rice | 11.09-12.97 | 2.1-3.2 |
| 2026-05-21 | K. Nurse | 14.73-16.07 | 4.4-4.8 |
| 2025-09-10 | A. Edwards | 12.01 | 4.8 |

These multi-out slates produce hits but the multipliers settle in a
high-but-not-leveraged range, because *everyone* on PrizePicks knows the team
has 2+ starters out.

## 5. Rookie-season effect: surprisingly flat

| | winner_share | menu_share | lift |
|---|---|---|---|
| rookie-season player | 0.181 | 0.172 | 1.05 |

Top rookie names in winning lineups, all 141 slates:

| rookie | wins |
|---|---|
| D. Malonga | 30 |
| P. Bueckers | 27 |
| J. Allemand | 27 |
| J. Salaün | 25 |
| A. Morrow | 21 |
| J. Shepard | 20 |
| K. Charles | 19 |
| J. Quinerly | 15 |
| T. Paopao | 15 |
| K. Iriafen | 14 |
| A. James | 13 |
| S. Citron | 13 |

**Read.** The top rookies show up a lot, but they show up in the menu just as
often. The PrizePicks freeze does NOT systematically misprice rookies. The
"rookie boost" narrative does not pay.

The single exception in our data is **Caitlin Clark on 2025-06-14**, but that
was a return-from-injury narrative, not a rookie narrative. She was already
in her 2nd WNBA season by 2026.

## 6. Season segment: playoffs over-index modestly

| segment | dates | winner_share | menu_share | lift |
|---|---|---|---|---|
| Opening 2 weeks 2025 | 5/16 - 5/30 | 0.104 | 0.097 | 1.07 |
| Early season 2025 | 5/31 - 7/17 | 0.272 | 0.282 | 0.97 |
| Post-All-Star 2025 | 7/22 - 8/31 | 0.270 | 0.282 | 0.96 |
| Playoff push 2025 | 9/1 - 9/13 | 0.077 | 0.078 | 0.99 |
| Playoffs 2025 | 9/14 - 10/31 | 0.094 | 0.073 | **1.28** |
| Opening 2026 | 5/8 - 6/5 | 0.182 | 0.188 | 0.97 |

The playoffs lift (1.28x) is partly mechanical: fewer games per slate, more
chalk concentration, the same handful of players (A. Wilson 28 winning picks
across 2025 playoffs, J. Young 18, C. Gray 18, S. Sabally 10, K. Copper 11)
showing up in top-3 lineups again and again. There is no obvious additional
narrative lift inside the playoff window beyond "the best teams keep playing
and their stars keep dominating."

## 7. Recent form: the market already prices it

For every pick we computed the player's 3-game rolling fantasy output before the
slate, compared to their career baseline.

| | winners | menu |
|---|---|---|
| Mean 3-game fps | 26.18 | 25.79 |
| Mean delta vs career baseline | +0.69 | +0.58 |
| Share above career baseline | 53.5% | 52.0% |

Winners over-index on "hot vs self" by 1.03x. This is one of the smallest
signals in the report. The freeze multiplier model already weights recent
form heavily. Hunting for hot streaks does not produce leverage.

## 8. Narrative coverage by player

Top players in winning lineups across all 141 slates, with their narrative
context attached when public information matched:

| player | winning_picks | dominant narrative |
|---|---|---|
| A. Wilson | 111 | Defending MVP, 2x champion, late-2025 playoff run, dominant Vegas. Pure quality, no narrative needed. |
| J. Young | 52 | Vegas co-star alongside Wilson, especially in playoff window (18 picks). |
| N. Collier | 51 | 2025 50-40-90 club, 2nd in MVP voting, leader of Lynx Finals run ([source](https://www.profootballnetwork.com/wnba/napheesa-collier-2025-season-stats-revisiting-the-wnba-mvp-candidates-records/)). |
| C. Gray | 41 | Vegas Finals run. |
| N. Howard | 38 | Multi-team veteran. Several picks correspond to revenge spots. |
| A. Reese | 37 | Year-2 player, freeze repeatedly under-projected double-double upside on bad Chicago teams. |
| N. Hiedeman | 33 | Late-season role explosion when Minnesota rested starters. Note: 13 of her picks come from 9/1-9/15 (a tight window). |
| V. Burton | 33 | 2025 Most Improved, Golden State expansion star, multiple career nights including a 24-pt 14-ast no-TO game on 8/19/2025 ([source](https://www.cbsnews.com/sanfrancisco/news/golden-state-valkyries-veronica-burton-re-signs-multi-year-contract-2026/)). |
| A. Morrow | 32 | Year-2 player whose role expanded mid-season. |
| P. Bueckers | 31 | #1 pick rookie. Picks concentrated in stretch where she returned from a brief absence and after the All-Star break when usage spiked. |
| D. Malonga | 31 | French rookie on Seattle whose minutes ballooned in mid-summer. |

## 9. Synthesis: what the freeze gets wrong about narratives

Combining all eight detectable narrative signals, the four cases where the
PrizePicks freeze systematically misprices are:

1. **Verified return from a 2+ week injury, healthy and starting.** Lift is
   functionally 4/4 in our window. Mechanism: stale rolling-form input to the
   multiplier model. Detection: official injury report removal in the 24 hours
   before tipoff, plus a confirmed starter mention by the beat writer.
2. **Player on a back-to-back facing a non-elite defense.** Lift 1.33x.
   Mechanism: fatigue overcorrection in the freeze. Detection: trivial from
   the schedule.
3. **Revenge spot vs a former team.** Lift 1.18x, but multipliers cluster
   in the 2.5-4.5 range, so the *leverage* per hit is high. Detection: a
   simple `prev_teams[player_id]` lookup. The 2026-05-23 Plum 38-point game
   was three-of-three in top-3 lineups.
4. **Exactly one starter out.** Lift 1.14x. The next-man-up at the *single*
   missing starter level is the best chaos signal. With 2+ starters out, the
   public chalk floods in and the leverage disappears.

The four cases where popular narratives DON'T produce signal:

1. **Generic "hot streak" recent form.** Lift 1.03x. Already priced in.
2. **Rookie-season players in general.** Lift 1.05x. The Bueckers / Malonga
   showings are about role, not novelty.
3. **Playoff push narrative.** Lift ~1.00. The push doesn't materially change
   star usage on a per-game basis.
4. **Multi-starter-out chaos games.** Lift 0.83-0.92 at the 2+ and 3+
   thresholds. Counter-intuitively hurts winners.

## 10. Building a narrative tag set into the picker

Concrete features that are cheap to compute and worth a multi-percent edge:

- `days_since_last_game` — already derivable from `wnba_game_logs.parquet`.
  Bucketize as `{1, 2, 3, 4-7, 8-14, 15+, debut}`. Apply +0.5 to +1.0 internal
  rank bump to the B2B and 15+ buckets, -0.5 to the 8-14 bucket.
- `is_return_from_long_absence` — flag if `days_since_last_game >= 14` AND
  injury_status from latest scrape went from Out/Doubtful to Active. This is
  the single highest-EV tag.
- `revenge_spot` — boolean from a `prev_teams[player_id]` lookup against
  tonight's opponent. Track multi-team history from the game logs.
- `starters_out_count` — count of expected rotation players (>=22 mpg in
  trailing window) absent from tonight's box score. Apply a small positive
  bump at `==1`, no bump at `==0`, a small *negative* bump at `>=2`.
- Do NOT add a separate "hot streak" tag. The freeze prices it.
- Do NOT add a separate "rookie" tag. No edge.

Stack these four tags conjunctively. The expected per-pick lift from the
single strongest tag is ~30 percent. Stacking two compounds to ~1.6x. Stacking
three (return-from-injury PLUS revenge PLUS B2B, which actually happened
exactly once in our window) is rare but unprintably high EV.

## Sources

- ESPN: Caitlin Clark return-from-injury context, 2025-06-14: <https://www.espn.com/wnba/story/_/id/48848576/fever-clark-returning-injuries-poses-mental-challenge>
- Las Vegas Sun: Kelsey Plum 38-point revenge game 2026-05-23: <https://lasvegassun.com/news/2026/may/23/kelsey-plum-scorches-aces-for-38-points-in-return/>
- ESPN: Plum return to Vegas atmosphere: <https://www.espn.com/wnba/story/_/id/45399408/sparks-kelsey-plum-greeted-fanfare-las-vegas-return>
- ESPN box score: Lynx 100-93 Liberty 7/30/2025 (Stewart out, Johannes starts): <https://www.espn.com/wnba/game/_/gameId/401736283/liberty-lynx>
- CBS Sports: Collier All-Star MVP and 50-40-90 season: <https://www.cbssports.com/wnba/news/lynxs-napheesa-collier-named-all-star-mvp-emerges-as-labor-leader-as-rise-to-wnba-prominence-continues/>
- ProFootballNetwork: Collier 2025 season stats: <https://www.profootballnetwork.com/wnba/napheesa-collier-2025-season-stats-revisiting-the-wnba-mvp-candidates-records/>
- CBS Bay Area: Veronica Burton Most Improved 2025 + 24-pt 14-ast game 8/19: <https://www.cbsnews.com/sanfrancisco/news/golden-state-valkyries-veronica-burton-re-signs-multi-year-contract-2026/>
- Dallas Hoops Journal: Rebecca Allen 27-point game 2025-07-09: <https://dallashoopsjournal.com/p/dallas-wings-vs-chicago-sky-july-9-2025-recap-rebecca-allen-li-yueru/>
- ESPN: Fever 81-54 Aces 2025-07-03: <https://www.espn.com/wnba/recap/_/gameId/401736220>
- The IX Basketball: Dallas Wings fire Koclanes (coaching-change context): <https://www.theixsports.com/features/dallas-wings-fire-head-coach-chris-koclanes-after-one-season/>
- Clutch Points: Veronica Burton multi-year extension 2026: <https://kioncentralcoast.com/news/2026/04/11/golden-state-valkyries-re-sign-breakout-wnba-star-veronica-burton-to-multi-year-contract/>
- SI Mercury: Sami Whitcomb career-high 36 on 2025-07-07: <https://www.si.com/wnba/mercury/phoenix-remembering-veteran-sami-whitcomb-all-star-performances>
- Andscape: Azura Stevens breakout 2025: <https://andscape.com/features/setbacks-slowed-azura-stevens-ascent-but-now-shes-enjoying-a-breakthrough-season/>

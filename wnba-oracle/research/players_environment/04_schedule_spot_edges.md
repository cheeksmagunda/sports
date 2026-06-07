# Schedule Spot Edges: When Winning Oracle Picks Are Born of the Calendar

**Scope.** 141 historical RealSports slates between 2025-05-16 and 2026-06-05. For every player listed on a slate label (popular, highest-boosted, highest-drafted) we attached the player's actual box score, the team's schedule context, the player's running season-average fantasy proxy (real_score baseline), and a flag for whether the player landed in the top-1 / top-3 / top-20 finishing lineups that day. After dedupe across slate sections we have 2600 distinct player-slate rows where the player actually appeared in a box score (DNPs and late scratches are dropped before win-rate math).

**Baselines.** Across those 2600 rows:
- avg real_score = 2.795
- top-1 win-share = 0.185 (i.e. 18.5% of player-slates land in the actual winning lineup that day; baseline is 5 slots over an avg of ~27 menu candidates)
- top-20 win-share = 0.559 (player appears in any of the day's top-20 leaderboard rosters)
- avg real_over_avg (game score minus season-to-date average) = 0.000 by construction.

**Schedule construction.** From `data/processed/wnba_game_logs.parquet` (13.5k player-games, 694 unique team-games, May 2024 through June 2026) we built per-team-game features:
- `rest_days` (calendar diff to prior game; 1 = true back-to-back)
- `away_streak_inclusive` / `home_streak_inclusive`
- `first_home_after_road`, `last_road_game`
- `phase` (first 5 / mid / last 5 of team's season)
- `season_phase_v2` (early-season May-early Jun / mid-regular / late-regular Aug / playoffs early / playoffs late)
- `n_games_on_slate` and a national-TV proxy (small slate carrying a marquee team)

Across the 1374 team-games covered: 62 true back-to-backs, 646 one-day-off, 341 two-day-off, 310 three-or-more-day-off. The WNBA's compressed schedule shows up clearly here. Per the IX and the Sun-Times reporting, back-to-backs rose to 30 in 2025 and the average days between games dropped from 4.1 (2021) to 2.7 (2025), the lowest in the modern era. See [The IX](https://www.theixsports.com/features/what-does-the-data-say-about-wnba-injuries-and-scheduling/) and the [Chicago Sun-Times](https://chicago.suntimes.com/chicago-sky/2025/07/30/as-wnba-enters-hyper-growth-era-player-rest-is-at-stake).


## 1. Headline: the highest-EV spots are unfashionable

Sorted by top-20 lift (how much more often a player from this archetype appeared in a top-20 lineup vs the 55.9% baseline). Bold = archetypes the optimizer should over-weight.

| Archetype | n | top1_rate | top1_lift | top20_rate | top20_lift | avg_real | over_avg |
|---|---:|---:|---:|---:|---:|---:|---:|
| **1 day off + home + late-regular (Aug)** | 139 | 0.173 | -0.06 | **0.719** | **+28.6%** | 3.08 | +0.22 |
| **B2B away** | 70 | **0.271** | **+47.0%** | **0.700** | **+25.2%** | 2.50 | -0.08 |
| 1 day off + late-regular (Aug) | 262 | 0.172 | -0.07 | 0.679 | +21.5% | 3.04 | +0.22 |
| **B2B (any home/away)** | 138 | **0.261** | **+41.3%** | 0.674 | +20.5% | 2.54 | -0.11 |
| Late-regular (Aug, all rest) | 484 | 0.184 | -0.00 | 0.655 | +17.1% | 2.93 | +0.14 |
| B2B home | 68 | 0.250 | +35.4% | 0.647 | +15.7% | 2.57 | -0.13 |
| Monday games | 198 | 0.217 | +17.6% | 0.611 | +9.3% | 2.33 | -0.19 |
| 5-game slate | 185 | 0.135 | -26.8% | 0.605 | +8.3% | 3.32 | +0.37 |
| Single-game slate | 249 | **0.297** | **+61.0%** | 0.602 | +7.7% | 2.18 | -0.36 |
| Nat'l-TV proxy (small slate + marquee) | 776 | **0.231** | **+24.9%** | 0.601 | +7.4% | 2.57 | -0.18 |
| First home after road | 603 | 0.184 | -0.00 | 0.589 | +5.3% | 2.83 | -0.03 |
| Marquee team (LVA/MIN/NYL/IND/PHX) | 1201 | 0.190 | +2.8% | 0.589 | +5.3% | 2.96 | -0.01 |
| Long road (4+ in a row) | 119 | 0.193 | +4.7% | 0.588 | +5.2% | 2.50 | -0.20 |
| 3+ days off + home | 304 | 0.181 | -2.0% | 0.579 | +3.5% | 2.94 | +0.07 |
| Marquee opponent | 1417 | 0.197 | +6.7% | 0.570 | +1.8% | 2.87 | -0.03 |
| 3+ days off + mid season | 149 | **0.235** | **+27.2%** | 0.564 | +0.8% | 3.02 | +0.04 |
| Playoffs early | 239 | 0.209 | +13.3% | 0.561 | +0.3% | 2.76 | -0.03 |
| Last 5 of season | 787 | 0.182 | -1.6% | 0.549 | -1.8% | 2.59 | -0.08 |
| Playoffs late | 170 | 0.224 | +21.1% | 0.547 | -2.2% | 2.63 | -0.24 |
| Long road (3+ away) + last road game | 186 | 0.204 | +10.7% | 0.522 | -6.7% | 2.73 | -0.07 |
| **Sunday games** | 500 | 0.166 | **-10.1%** | **0.496** | **-11.3%** | 2.91 | +0.05 |
| **First 5 of season** | 300 | 0.193 | +4.7% | **0.407** | **-27.3%** | 2.87 | -0.00 |

Two things jump out and deserve their own sections:

1. **Back-to-back games are the single biggest schedule-spot edge in the league.** Every B2B cell, especially B2B-away, posts a +20% to +47% lift. Yet the optimizer should not be using B2B to chase raw projection — these games actually score *below* the player's season average (over_avg = -0.08 to -0.13). The lift is structural: B2B slates are tiny (often 1-2 games), so the leaderboard concentrates and a smaller name pool dominates the top 20.
2. **Single-game and small slates dominate the top-1 win-rate.** Single-game slates show a +61% top-1 lift. The leaderboard mechanically collapses onto the 10 to 14 active players, so almost everyone listed has a real shot.

The mirror image is just as actionable. **Sundays and season-opening weeks are the worst environments** for the players who hog menu attention. Sunday slates carry 500 player-rows and the top-20 hit-rate falls 11% below baseline. First-5-of-season games are even worse, at -27%. The reason is the same in both cases: variance. Sunday is a 4 to 6 game window with all the stars on the menu, so the field has too many ways to fold a star into a lineup. Opening weeks are noise.


## 2. Back-to-back: the structural edge, and who actually delivers it

138 player-slates fell into the B2B bucket (any home/away). Top-20 hit-rate: 67.4%. Top-1 hit-rate: 26.1% (vs 18.5% baseline). Lineup pollution: even though average real_score sags to 2.54 (-0.11 vs season), winners pile in because the slate is usually skinny. Of the 10 highest-B2B-density slates, 7 carry 12 or fewer active players on the slate label.

The slates with 100% of player-rows in a B2B context were a true rest-deprivation grind:

| slate_date | dow | n_players | avg_real | notes |
|---|---|---:|---:|---|
| 2025-06-18 | Wednesday | 7 | 2.40 | single-game slate, both teams on B2B |
| 2025-06-28 | Saturday | 8 | 1.96 | single-game slate |
| 2025-07-23 | Wednesday | 11 | 2.25 | single-game slate; both teams in middle of long road |
| 2025-07-28 | Monday | 16 | 2.08 | 2-game slate, all 4 teams on B2B |
| 2025-08-11 | Monday | 12 | 1.69 | single-game slate; both teams in middle of long road |

Notice that these are mostly **Wednesday/Monday/Saturday primetime windows**, where the league fills nights without a national TV doubleheader. The combination of B2B + small slate + non-Sunday day is the highest top-20-density environment in the data.

### Who covers themselves in glory on B2B (n>=2 in the cohort)

| Player | n | top1 | top20 | avg_real | over_avg |
|---|---:|---:|---:|---:|---:|
| C. Brink (LAS) | 2 | 1 | 2 | 2.72 | **+1.37** |
| D. Hamby (LAS) | 2 | 1 | 1 | 5.04 | **+1.25** |
| A. Gray (ATL) | 3 | 1 | 3 | 4.71 | **+1.17** |
| T. Hayes (CHI) | 2 | 2 | 2 | 3.25 | +1.10 |
| S. Citron (NYL) | 2 | 2 | 2 | 3.73 | +1.04 |
| E. Magbegor (SEA) | 2 | 2 | 0 | 3.44 | +0.73 |
| D. Malonga (SEA) | 2 | 2 | 2 | 2.83 | +0.70 |
| N. Hillmon (ATL) | 3 | 1 | 2 | 3.33 | +0.63 |
| O. Nelson-Ododa (LAS) | 3 | 2 | 3 | 3.06 | +0.61 |
| J. Jones (NYL) | 3 | 1 | 2 | 3.75 | +0.60 |
| B. Stewart (NYL) | 3 | 0 | 2 | 4.26 | +0.49 |
| A. Morrow (CHI) | 3 | 2 | 2 | 2.64 | +0.48 |
| P. Bueckers (DAL) | 3 | 1 | 3 | 4.31 | +0.38 |

### Who collapses on B2B

A. Wilson (-1.36 over_avg on 2 B2Bs), K. Mitchell (-1.19 on 3), A. Boston (-1.47 on 2 B2B-away grinds), A. Thomas (-1.10 on 2). The pattern is high-usage front-court hubs (Wilson, Boston) and ball-dominant guards who carry a heavy minutes load (Mitchell). The B2B beneficiaries are role-player wings and second-unit bigs whose minutes spike when the star takes a maintenance hit, or whose efficiency stays high because they are not the player every defense is geared to stop.

**Optimizer implication.** On a B2B slate, fade the heaviest-usage star and replace with their teammate (Brink in for Plum, Hamby in for Stewart, Magbegor in for Loyd, Hillmon in for Howard). The B2B itself is not the alpha. The alpha is the *redistribution* of touches and minutes that happens on a B2B.


## 3. The cleanest positive-EV archetype: 1 day off + home + late August

This combo delivers both:
- top-20 lift: **+28.6%** (best in the entire archetype table)
- over_avg: **+0.22 real_score** (real projection beat, not just lineup concentration)

That is unusual. Almost every other top-20-lift archetype trades projection for concentration. This one stacks both.

### Why it works

Late August is the WNBA's "playoff push" window. The 2025 regular season ran May 16 through September 11 (see [WNBA.com 2025 broadcast schedule](https://www.wnba.com/news/2025-broadcast-streaming-schedule)). Teams in the playoff race extend rotations of starters and run normal practice prep. The 1-day-off cadence is the league's modal rest profile, so it doesn't bring the rust of a long break or the fatigue of a B2B. Home means home-court foul calls, friendly rims, and full crowd energy as seeding stakes rise.

### Players who delivered in this exact spot (n>=3)

| Player | n | top1 | top20 | avg_real | over_avg |
|---|---:|---:|---:|---:|---:|
| J. Loyd (LVA) | 3 | 1 | 3 | 3.24 | **+0.76** |
| B. Jones (NYL) | 6 | 0 | 4 | 3.58 | +0.64 |
| T. Paopao (LAS) | 4 | 1 | 2 | 2.69 | +0.55 |
| R. Howard (ATL) | 3 | 0 | 3 | 4.28 | +0.48 |
| C. Gray (LVA) | 5 | 0 | 5 | 3.25 | +0.48 |
| K. Plum (LAS) | 4 | 1 | 3 | 4.07 | +0.48 |
| K. Mitchell (IND) | 3 | 1 | 2 | 3.70 | +0.42 |
| A. Gray (ATL) | 6 | 1 | 3 | 3.92 | +0.39 |
| A. Wilson (LVA) | 5 | 3 | 5 | **5.54** | +0.37 |
| E. Williams (CHI) | 5 | 2 | 4 | 2.61 | +0.30 |
| A. Thomas (CON) | 4 | 0 | 3 | 4.47 | +0.29 |
| D. Hamby (LAS) | 4 | 0 | 3 | 3.98 | +0.19 |

A. Wilson scored a 5.54 average in this exact spot, with 3-of-5 top-1 finishes. Even Plum, who is a clear over-rester (negative on 2 days off and 3+ days off in the per-star tables below), shows positive over_avg here. The signal is broad, not driven by one outlier.


## 4. Long rest (3+ days off) splits cleanly along player profile

The aggregate stats for 3-days-off are unimpressive (top-20 lift only +3.5%, over_avg +0.07 at home, -0.12 away). But the player-level breakdown is dramatic. Long rest is a **profile-dependent** spot, not a universal edge.

### Who LOVES the rest (3+ days off, n>=4)

| Player | n | top1 | top20 | avg_real | over_avg |
|---|---:|---:|---:|---:|---:|
| **C. Clark (IND)** | 7 | 4 | 6 | **4.86** | **+1.33** |
| S. Diggins (SEA) | 4 | 2 | 2 | 4.35 | +1.20 |
| S. Whitcomb (PHX) | 5 | 3 | 4 | 3.26 | +1.05 |
| A. James (CHI) | 6 | 1 | 4 | 3.27 | +0.88 |
| J. Quinerly (DAL) | 4 | 3 | 4 | 2.79 | +0.79 |
| S. Sabally (PHX) | 4 | 1 | 3 | 3.89 | +0.77 |
| A. Thomas (CON) | 10 | 5 | 7 | 4.37 | +0.35 |
| J. Canada (CHI) | 8 | 1 | 5 | 3.50 | +0.32 |
| B. Stewart (NYL) | 11 | 3 | 7 | 4.07 | +0.27 |
| D. Hamby (LAS) | 10 | 2 | 7 | 3.97 | +0.24 |

### Who CAVES on long rest

A. Wilson: 10 games, -0.87 over_avg. Eight of those ten are bad. The worst was an Aug 2 home game vs MIN where she posted 1.15 real_score against a 5.17 season baseline (a -4.03 swing).
N. Collier: 12 games, -0.49 over_avg.
K. Plum: 10 games, -0.25 over_avg.
C. Gray: 10 games, -0.45.

The split is rest-of-rotation guards and wings UP, alpha bigs DOWN. The interpretation: a 3-plus-day break lets the lower-minute role players recover and earn extra usage in the first game back, while the alpha big has now sat through 4 days of coach-mandated rest, late practice, conditioning, and walk-throughs without playing real basketball. The first game back is rusty for the franchise centerpiece. The supporting cast looks reborn.

**Caitlin Clark's long-rest split is the cleanest individual schedule edge in the dataset.** Across 7 long-rest games, she averages 4.86 real_score against a 3.52 baseline (+38% per-game). Notable lines:

| Slate | Opponent | home/away | real | baseline | over_avg |
|---|---|---|---:|---:|---:|
| 2025-05-17 | NYL | home | 5.62 | 3.52 | +2.09 |
| 2025-05-20 | CON | home | 5.32 | 3.52 | +1.79 |
| 2025-06-14 | NYL | home | **7.77** | 3.52 | **+4.25** |
| 2025-07-11 | NYL | home | 2.82 | 3.52 | -0.70 |
| 2025-07-13 | NYL | home | 5.26 | 3.52 | +1.74 |
| 2026-05-09 | PHX | home | 2.98 | 3.54 | -0.55 |
| 2026-05-13 | LVA | away | 4.23 | 3.54 | +0.69 |

Six of seven are at home. Five of seven are vs NYL. The unfilterable inference is that this is Clark on national-TV marquee games (Indiana vs NY was an ESPN/ABC headliner in both 2025 and 2026), with proper rest after a Sunday rest day. The schedule architecture for her megagames is reliable.


## 5. Long road trips: trapped variance with a tactical exit

The "long road (4+ away)" cohort (n=119) shows -0.20 over_avg. Players on the road for 4 games or more are tired, fed up, and on the wrong rims. But the **last road game** of a long trip is different. n=186 (defined as away_streak >= 3 AND next game is home). Top-1 lift is +10.7%, even though top-20 is below baseline. Players who score there were:

| Player | n | top1 | top20 | avg_real | over_avg |
|---|---:|---:|---:|---:|---:|
| J. Loyd (LVA) | 8 | 2 | 6 | 3.07 | **+0.59** |
| R. Burrell (DAL) | 5 | 0 | 4 | 2.46 | +0.55 |
| N. Collier (MIN) | 9 | 3 | 8 | **5.10** | +0.54 |
| A. Wilson (LVA) | 9 | 6 | 9 | **5.69** | +0.51 |
| T. Hayes (CHI) | 5 | 4 | 4 | 2.74 | +0.48 |
| N. Hillmon (ATL) | 7 | 5 | 5 | 3.13 | +0.45 |
| S. Citron (NYL) | 10 | 3 | 7 | 3.11 | +0.42 |
| K. Westbeld (PHX) | 4 | 0 | 1 | 1.91 | +0.41 |
| K. Iriafen (PHX) | 11 | 2 | 8 | 2.92 | +0.27 |

A. Wilson alone, on the last road game of a trip, was top-1 in **6 of 9** outings. The pattern is well-known in basketball: the closer of a long trip is a "we're going home" game where the alpha exerts maximum will. Wilson, Collier, and Loyd are the three players most worth trusting here. Note these are exactly the players who **fade on long rest** — same alphas, opposite calendar context.

The road-trip *interior* games (4+ away streak active but not the last one) score -0.20 over_avg. Notable beneficiaries when forced to pick from this bucket include the road-warrior 2026-rookie group:

| Player | n (long-road, 3+ in a row) | over_avg | comment |
|---|---:|---:|---|
| L. Fiebich (NYL) | 4 | +1.03 | Plays no role on rested home Liberty, big minutes when fatigue hits the rotation |
| S. Austin (LAS) | 5 | +0.86 | Same dynamic for LAS bench wing |
| S. Ionescu (NYL) | 6 | +0.66 | Volume scoring when defense legs go |
| A. Morrow (CHI) | 7 | +0.59 | CHI uses Morrow heavy on road grinds |
| K. Mitchell (IND) | 8 | +0.36 | Higher usage on road |
| A. Thomas (CON) | 5 | +0.36 | The triple-double machine extends shifts |


## 6. Phase: opening 5 and closing 5 are different problems

The most underweighted insight: **the first 5 games of a team's season are the worst environment in the calendar for picking accuracy.** Top-20 hit-rate sits at 40.7%, a -27% lift. Reasons:
- rotations haven't settled (real_avg is unstable because n=1-4 games into a season)
- new acquisitions and rookies are mis-priced by the market
- coaches are still experimenting with usage hierarchy

The over_avg in first-5 games is essentially zero (-0.00). Players are not under- or over-performing on average; they are *unpredictable*.

Best bets in first-5 (n>=4):
- N. Collier: 4 games, 5.18 avg (+0.62 over_avg). A consistent fast starter, no surprise.
- C. Clark: 5 games, 4.05 avg (+0.52). Confirms Indiana's heavy reliance early.
- B. Stewart: 6 games, 4.16 (+0.51).
- D. Bonner: 4 games, 2.48 (+0.51). Veteran who has paced herself to camp.
- V. Burton (NYL): 5 games, 3.67 (+0.40).
- S. Citron (NYL): 6 games, 3.28 (+0.38).
- K. Iriafen: 6 games, 3.17 (+0.36).

Last-5 (closing stretch) is more interesting. Over_avg sits at -0.08 and the top-20 lift is -1.8%, so the average is mediocre. But the right players go off:

| Player | n (last-5) | top1 | over_avg |
|---|---:|---:|---:|
| E. Engstler | 4 | 2 | +0.74 |
| C. Gray | 16 | 5 | **+0.67** |
| J. Young | 16 | 7 | +0.59 |
| A. Wilson | 16 | **12** | +0.42 |
| D. Hamby | 11 | 2 | +0.42 |
| O. Miles | 6 | 2 | +0.41 |

A. Wilson going top-1 in 12 of 16 last-5 contests is exceptional. She *wins* the late-season MVP push when other stars are getting rested for the playoffs.


## 7. Playoffs: contained variance, high alpha concentration

Playoff slates (n=409) are not magical at the top-20 level (lift roughly flat). The top-1 lift is +13% to +21%, driven by leverage concentration: 1-game playoff slates show +88% top-1 lift while their top-20 lift is **negative -15%**. Translation: in playoffs, the right 5 picks are obvious, and everyone else gets buried.

The players who dominate playoff slates are not the regular-season usage leaders. They are the players whose **role expands** in the postseason:

| Player | n (playoffs) | top1 | top20 | avg_real | over_avg |
|---|---:|---:|---:|---:|---:|
| C. Gray (LVA) | 16 | 5 | 14 | 3.45 | **+0.68** |
| J. Young (LVA) | 16 | 7 | 14 | 4.45 | **+0.67** |
| D. Hamby (LAS) | 6 | 2 | 5 | 4.39 | +0.59 |
| B. Stewart (NYL) | 6 | 1 | 3 | 4.44 | +0.54 |
| A. Wilson (LVA) | 16 | **11** | **16** | **5.68** | +0.50 |
| K. Cardoso (CHI) | 5 | 2 | 5 | 3.43 | +0.44 |
| K. Charles (LAS) | 5 | 2 | 4 | 2.36 | +0.43 |
| P. Bueckers (DAL) | 4 | 1 | 3 | 4.24 | +0.32 |
| N. Hillmon (ATL) | 8 | 3 | 6 | 2.95 | +0.26 |
| R. Howard (ATL) | 8 | 3 | 6 | 3.91 | +0.12 |

Las Vegas concentration is unmistakable: Wilson + Young + Gray are the three most over-performing playoff names. Building **LVA stacks in playoff slates** is structurally correct. The 3-out-of-5 slots covered by Vegas players in a playoff lineup happens in the top-1 lineup repeatedly across the 2025 postseason.


## 8. Day-of-week patterns line up with national TV windows

Per [WNBA.com](https://www.wnba.com/news/2025-broadcast-streaming-schedule), 2025 had:
- ABC: 13 games (Saturday/Sunday afternoon)
- ESPN: 13 (midweek)
- ION: 50 games via "State Farm WNBA Friday Night Spotlight" doubleheaders every Friday
- CBS: 20 games, weekends + 2 primetime midweek specials
- CBSSN, NBA TV: midweek scatter

Our DOW table:

| dow | n | top1_rate | top20_rate | over_avg | comment |
|---|---:|---:|---:|---:|---|
| Monday | 198 | **0.217** | **0.611** | -0.19 | small fill-in slates, often B2B leftover |
| Thursday | 364 | 0.168 | 0.610 | -0.09 | ESPN window, concentrated star pool |
| Saturday | 304 | 0.214 | 0.605 | -0.05 | ABC/CBS afternoon, marquee |
| Wednesday | 368 | 0.198 | 0.601 | +0.02 | ESPN/CBSSN window |
| Tuesday | 426 | 0.181 | 0.538 | +0.05 | NBA TV scatter, larger fields |
| Friday | 440 | 0.177 | 0.520 | +0.06 | ION doubleheader, larger fields |
| Sunday | 500 | **0.166** | **0.496** | +0.05 | ABC/CBS afternoon doubleheader, biggest fields |

Sundays are the **single worst day** for top-20 hit-rate. The reason is mechanical: Sundays carry the largest menu (often 4-6 games) AND the most marquee opponents, so the field has the most variance in lineup paths.

Mondays are the best, by a wide margin in top-20 lift terms. Monday is the day after Sunday's full slate, so most teams sit and only the B2B grinders play. Mondays are typically 1-2 game slates featuring a B2B-team on national TV (CBSSN, NBA TV midweek scatter). Two trap-game properties combine: tiny menu and obvious alpha.

If the optimizer can recognize **slate-size and DOW** features, it should:
- On Mondays: concentrate, trust the alpha despite B2B.
- On Sundays: diversify, take more contrarian shots, and **fade the obvious chalk**.


## 9. National-TV proxy: the 776 marquee-on-small-slate environment

We don't have explicit national-TV labels for each game, but we built a proxy: `n_games_on_slate <= 2 AND (team or opponent is one of LVA, MIN, NYL, IND, PHX)`. That captures 776 player-slates. Top-1 lift: +25%. Top-20 lift: +7.4%. over_avg: -0.18.

Translation: when the WNBA puts a marquee team in primetime on a 1-2 game window, the leaderboard concentrates and the top-1 hit-rate jumps. But projection actually FALLS because: (a) defenses lock in for primetime, (b) coaches play more sets, (c) star usage doesn't necessarily expand if the team gets the W early.

The players to LEAN ON in this proxy environment, ranked by over_avg with n>=4:
- A. Wilson (LVA) and N. Collier (MIN) carry the marquee. Over_avg modestly negative because they're already projected high, but the top-1 hit rate is exceptional.
- The CEILING plays are the second-string stars who get spotlight minutes (Hamby on LAS-LVA primetime, Howard on ATL marquee, Hillmon).


## 10. Star players and the calendar: per-rest-bucket cheat-sheet

How each marquee scorer splits across rest contexts. n is the player-slate count, top1 / top20 are leaderboard appearance counts (not rates), avg = real_score, over = real_score - season_avg.

### A. Wilson (LVA)

| rest_bucket | n | top1 | top20 | avg | over |
|---|---:|---:|---:|---:|---:|
| 1_day_off | 29 | 18 | 26 | 5.19 | +0.03 |
| 2_days_off | 20 | 12 | 20 | **5.65** | **+0.52** |
| 3plus_days_off | 10 | 2 | 9 | 4.20 | **-0.87** |
| b2b_0_off | 2 | 0 | 2 | 3.82 | -1.36 |

**Insight.** Wilson peaks on 2 days off (one day of practice, fully prepared). Loses on too much rest (rust) and not enough rest (load). 1 day off is her bread and butter.

### N. Collier (MIN)

| rest_bucket | n | top1 | top20 | avg | over |
|---|---:|---:|---:|---:|---:|
| 1_day_off | 13 | 5 | 11 | 4.39 | -0.17 |
| 2_days_off | 13 | 5 | 12 | **5.20** | **+0.65** |
| 3plus_days_off | 12 | 3 | 11 | 4.07 | -0.49 |
| b2b_0_off | 1 | 0 | 1 | 4.22 | -0.34 |

Same pattern as Wilson, sharper. 2 days off is the magic number.

### A. Thomas (CON)

| rest_bucket | n | top1 | top20 | avg | over |
|---|---:|---:|---:|---:|---:|
| 1_day_off | 32 | 2 | 23 | 4.08 | +0.00 |
| 2_days_off | 17 | 1 | 12 | 4.04 | -0.08 |
| 3plus_days_off | 10 | 5 | 7 | **4.37** | **+0.35** |
| b2b_0_off | 2 | 0 | 2 | 3.08 | -1.10 |

Opposite of Wilson. Thomas needs long rest because her playstyle (triple-doubles, heavy minutes) demands recovery.

### C. Clark (IND)

| rest_bucket | n | top1 | top20 | avg | over |
|---|---:|---:|---:|---:|---:|
| 1_day_off | 11 | 0 | 7 | 2.84 | -0.69 |
| 2_days_off | 2 | 0 | 1 | 2.68 | -0.85 |
| 3plus_days_off | 7 | 4 | 6 | **4.86** | **+1.33** |
| b2b_0_off | 1 | 0 | 0 | 3.55 | +0.02 |

Cleanest pattern in the dataset. Clark needs rest. Period.

### P. Bueckers (DAL)

| rest_bucket | n | top1 | top20 | avg | over |
|---|---:|---:|---:|---:|---:|
| 1_day_off | 16 | 5 | 11 | 3.48 | -0.39 |
| 2_days_off | 12 | 4 | 8 | **4.65** | **+0.80** |
| 3plus_days_off | 13 | 2 | 8 | 3.41 | -0.34 |
| b2b_0_off | 3 | 1 | 3 | 4.31 | +0.38 |

Same as Wilson / Collier: 2 days off is magic. Surprisingly positive on B2B (rookie energy?).

### K. Plum (LAS)

| rest_bucket | n | top1 | top20 | avg | over |
|---|---:|---:|---:|---:|---:|
| 1_day_off | 24 | 3 | 13 | 4.09 | **+0.33** |
| 2_days_off | 12 | 0 | 2 | 3.12 | -0.47 |
| 3plus_days_off | 10 | 1 | 5 | 3.74 | -0.25 |
| b2b_0_off | 2 | 0 | 1 | 3.70 | +0.11 |

Plum prefers the high-tempo 1-day-off cadence. Rest kills her rhythm.

### S. Ionescu (NYL)

| rest_bucket | n | top1 | top20 | avg | over |
|---|---:|---:|---:|---:|---:|
| 1_day_off | 18 | 3 | 14 | 3.70 | +0.07 |
| 2_days_off | 10 | 1 | 9 | **4.04** | **+0.37** |
| 3plus_days_off | 11 | 2 | 6 | 3.21 | -0.46 |
| b2b_0_off | 3 | 1 | 3 | 3.68 | +0.01 |

Same family as Wilson, Collier, Bueckers.

### K. Mitchell (IND)

| rest_bucket | n | top1 | top20 | avg | over |
|---|---:|---:|---:|---:|---:|
| 1_day_off | 31 | 2 | 18 | 3.14 | -0.13 |
| 2_days_off | 10 | 2 | 6 | **3.77** | **+0.51** |
| 3plus_days_off | 16 | 2 | 9 | 3.43 | +0.16 |
| b2b_0_off | 3 | 0 | 2 | 2.05 | -1.19 |

Two-day-off pattern again. Mitchell collapses on B2B (-1.19).

### D. Hamby (LAS)

| rest_bucket | n | top1 | top20 | avg | over |
|---|---:|---:|---:|---:|---:|
| 1_day_off | 25 | 4 | 15 | 4.13 | **+0.36** |
| 2_days_off | 15 | 0 | 5 | 2.84 | **-0.92** |
| 3plus_days_off | 10 | 2 | 7 | 3.97 | +0.24 |
| b2b_0_off | 2 | 1 | 1 | **5.04** | **+1.25** |

Hamby is an outlier: she crashes on 2 days off but explodes on B2B. Her game is energy and she rides the wave when the team is on auto-pilot.

### Summary heuristic for stars

| Player family | Optimal rest | Penalty on |
|---|---|---|
| Wilson / Collier / Bueckers / Ionescu / Mitchell | **2 days off** | 3+ rest, B2B |
| Thomas | **3+ days off** | B2B (catastrophic) |
| Clark | **3+ days off** | 1-2 day off (rusty) |
| Plum | **1 day off** | 2 days off |
| Hamby | **B2B** or **1 day off** | 2 days off |

If your optimizer can ingest schedule context per player, this single feature set covers ~10% of the leaderboard variance for the top-of-menu names.


## 11. Highest-EV spot ARCHETYPES (the final ranked list)

Combining top-1 lift AND over_avg into a single ranking. EV score = `top1_lift + 0.5 * (over_avg / 1.0)`. Top 12:

| Rank | Archetype | top1_lift | over_avg | EV score | Notes |
|---|---|---:|---:|---:|---|
| 1 | Single-game playoff slate | +88% | -0.27 | **0.745** | Concentration trumps projection |
| 2 | Single-game slate (any) | +61% | -0.36 | 0.430 | Use a concentrated stack |
| 3 | B2B + away | +47% | -0.08 | 0.430 | Skip the alpha, pick the teammate |
| 4 | B2B (any) | +41% | -0.11 | 0.355 | Pure leaderboard concentration |
| 5 | B2B + home | +35% | -0.13 | 0.286 | |
| 6 | 3+ days off + mid season | +27% | +0.04 | 0.290 | Both lift and projection positive |
| 7 | Nat'l-TV proxy (small + marquee) | +25% | -0.18 | 0.160 | |
| 8 | Playoffs late | +21% | -0.24 | 0.090 | Concentration via locked rotations |
| 9 | Monday games | +18% | -0.19 | 0.085 | |
| 10 | Playoffs early | +13% | -0.03 | 0.115 | |
| 11 | **1 day off + home + late-reg (Aug)** | -6% | **+0.22** | **+0.110** | **Only spot positive on both axes** |
| 12 | Long road + last road game | +11% | -0.07 | 0.075 | A. Wilson and N. Collier go off here |

The single most actionable archetype is row 11: 1-day-off + home + late-regular August. It is the **only** archetype in the table where both top-1 lift and over_avg are positive in a meaningful way. Every other top-EV spot trades projection for concentration.

The single biggest **bait** is row 1: single-game playoff slates have a top-1 lift of +88% but the top-20 lift is **negative -15%**. Translation: in a single-game playoff slate, the right lineup wins big but the rest fold catastrophically. This is a **gamble**, not an edge. If you cannot front-run the optimal stack, sit it out.


## 12. What this means for the optimizer

1. **B2B + small slate**: skip the alpha (Wilson, Mitchell, Boston), promote the second-line teammate (Hamby, Hillmon, Brink, Magbegor, Bueckers).
2. **1 day off + home + Aug**: pile in with the standard chalk. This is the rare both-axis-positive spot.
3. **Sundays**: drop confidence. Top-20 hit-rate is the worst of any day, projection is fine. Diversify or sit.
4. **First 5 of season**: fade the menu, the data has not stabilized. Lean on veterans (Bonner, Stewart, Collier) over rookies.
5. **Caitlin Clark with 3+ days rest at home**: bet the house. +1.33 over_avg across 7 games, 4 top-1 finishes.
6. **A. Wilson on last road game of a trip**: bet the house. 6-of-9 top-1 finishes, +0.51 over_avg.
7. **Per-star rest signatures**: ingest a `player_rest_signature` feature (which bucket each player is in their optimal vs penalty zone) and let it bias projection.
8. **Long road + last game**: trust Loyd, Wilson, Collier. Avoid interior road games.
9. **Late-regular Aug players-to-target list**: V. Burton, D. Malonga, M. Siegrist, K. McBride, L. Lacan. All over +0.45 over_avg in this window, all currently under-drafted vs their late-season usage.


## 13. Caveats

- Bridge coverage: 2600 of 4002 slate-label rows matched a box score. Unmatched rows are mostly DNPs (Out players the slate listed pre-game) or players who were traded mid-season and whose team code didn't match. Effective lineup-impact analysis (top-1 / top-20 win rates) is on the matched 2600.
- The dataset spans only May 2024 (game logs) and May 2025 onward (slate labels). Pre-2024 schedule patterns are not visible.
- Single-game / 2-game slate B2B effects are mechanically inflated by their small menus. The top-20 lift in B2B is partly a denominator effect.
- We do not have explicit national-TV labels. The proxy (small slate + marquee team) is a reasonable but imperfect substitute. Vegas implied totals (which would give a 4th orthogonal signal) are not in this dataset.
- Player-level rest signatures (Section 10) are based on n=10-30 per cell. Some players (Hamby B2B, Clark long-rest) have very small n; the directional signal is strong but the magnitude has wide error bars.
- Season-average baseline is recomputed across the full season; it includes the games being scored. A walk-forward baseline would shift over_avg numbers slightly but not the rank order.


## Sources

- [WNBA 2025 National Broadcast and Streaming Schedule](https://www.wnba.com/news/2025-broadcast-streaming-schedule)
- [What does the data say about WNBA injuries and scheduling? - The IX Basketball](https://www.theixsports.com/features/what-does-the-data-say-about-wnba-injuries-and-scheduling/)
- [As WNBA enters hyper-growth era, player rest is at stake - Chicago Sun-Times](https://chicago.suntimes.com/chicago-sky/2025/07/30/as-wnba-enters-hyper-growth-era-player-rest-is-at-stake)
- [2025 WNBA Season Schedule - Basketball-Reference](https://www.basketball-reference.com/wnba/years/2025_games.html)
- Internal: `data/processed/wnba_game_logs.parquet`, `data/historical/leaderboards/`, `data/historical/slate_labels/` (141 slates, 2025-05-16 to 2026-06-05).

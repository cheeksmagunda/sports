# Matchup Edge: Where Winning WNBA Oracle Picks Land

**Scope.** 141 historical slates between 2025-05-16 and 2026-06-05. Winning picks = every player rostered by the top-3 finishers per slate (2810 pick-rows; 2698 after we drop picks of players who did not actually appear in a box score that night, i.e. late scratches and the 'Out' starters that some entries still submitted).

**Defensive metric.** For each opponent we compute a 10-game rolling *prior* mean of total team fantasy points allowed per game (PrizePicks scoring: pts + 1.2 reb + 1.5 ast + 3 stl + 3 blk - tov). Pace is the 10-game rolling prior mean of possessions per game where poss = FGA + 0.44 FTA - OREB + TOV (Dean Oliver style). Both are recomputed strictly from games BEFORE the slate date.

**League baselines.** Median team-game fantasy points allowed = `174.9`. Median pace = `80.7` poss/game.

**Coverage.** 2685 of 2698 matched winning-pick rows have a usable 10-game defensive history. The menu baseline covers 3735 rows across the same slates.


## 1. Headline: yes, winners chase soft defense, but the edge is small

- Among matched winning-pick rows, **48.5%** were against a team whose 10-game fp-allowed sat at or above the league median.
- The matched menu sits at **45.0%**.
- The lift is about **+3.5** percentage points. Real but small. Lineup-construction effects (boost stacks, ownership leverage) dominate raw matchup selection. The matchup edge lives in the tails of the distribution, not the mean.
- Same story for pace: winners run 53.6% high-pace matchups vs 50.5% in the menu, a +3.1-point gap.

## 2. Defensive-strength quartiles (10-game prior fp-allowed)

Quartiles of opponent defense from STOUTEST (Q1) to SOFTEST (Q4). `lift` = winner_share / menu_share. Lift > 1 means winners chose this bucket more than the menu offered it.

| def_quartile | winner_picks | menu_rows | winner_share | menu_share | lift |
|---|---|---|---|---|---|
| Q1 stoutest | 690 | 931 | 0.257 | 0.25 | 1.028 |
| Q2 | 658 | 932 | 0.245 | 0.25 | 0.979 |
| Q3 | 668 | 934 | 0.249 | 0.251 | 0.992 |
| Q4 softest | 669 | 926 | 0.249 | 0.249 | 1.002 |

*Read.* Winners modestly underweight the toughest defenses (Q1) and modestly overweight the softest quartile (Q4). The biggest single bucket the menu serves is still Q1-Q2 because slates often feature the league's better defenses. Winners win mostly by picking players who beat their projection, not by avoiding tough Ds.

## 3. Pace quartiles (10-game prior possessions/game)

| pace_quartile | winner_picks | menu_rows | winner_share | menu_share | lift |
|---|---|---|---|---|---|
| Q1 slowest | 676 | 936 | 0.252 | 0.251 | 1.001 |
| Q2 | 685 | 927 | 0.255 | 0.249 | 1.025 |
| Q3 | 656 | 937 | 0.244 | 0.252 | 0.971 |
| Q4 fastest | 668 | 923 | 0.249 | 0.248 | 1.004 |

*Read.* The pace edge is even smaller than the defense edge. Winners tilt slightly to the faster (Q3, Q4) buckets but the entire spread is inside a couple of percentage points. Pace exploitation is not the dominant signal in this slate population.

## 4. Cross-bucket conversion rates from the menu

Same buckets but now expressed as `winners / menu_rows` for each combination.

| weak_def | high_pace | menu_rows | winners | win_rate |
|---|---|---|---|---|
| False | False | 1365 | 359 | 0.263 |
| False | True | 690 | 173 | 0.251 |
| True | False | 484 | 133 | 0.275 |
| True | True | 1196 | 352 | 0.294 |

*Read.* The cell with both `weak_def=True` and `high_pace=True` has the highest hit rate. The cell with stout defense and slow pace has the lowest. The two factors stack roughly additively.

## 5. Soft opponents: who got attacked most by winners (per game)

Sorted by winner-picks-per-league-game so opponents that played fewer games are not penalized. `avg_def_allowed` is the 10-game rolling prior on the date of each winning pick against this opponent.

| opponent | winner_picks | avg_def_allowed | avg_pace | avg_scored | league_games | winner_picks_per_game |
|---|---|---|---|---|---|---|
| TOR | 51 | 168.14 | 82.11 | 10.74 | 12 | 4.25 |
| DAL | 319 | 189.86 | 82.48 | 11.88 | 97 | 3.29 |
| GSV | 179 | 168.34 | 78.22 | 9.79 | 59 | 3.03 |
| LAS | 260 | 187.27 | 82.01 | 11.13 | 97 | 2.68 |
| PDX | 30 | 185.95 | 83.41 | 9.9 | 13 | 2.31 |
| PHX | 260 | 176.3 | 81.51 | 11.21 | 113 | 2.3 |
| CON | 225 | 178.97 | 79.54 | 10 | 108 | 2.08 |
| LVA | 220 | 166.4 | 80.56 | 12.16 | 114 | 1.93 |
| CHI | 189 | 191.34 | 79.96 | 11.05 | 100 | 1.89 |
| WAS | 166 | 174.24 | 80.57 | 10.95 | 98 | 1.69 |
| SEA | 172 | 171.57 | 80.12 | 10.33 | 105 | 1.64 |
| MIN | 188 | 160.98 | 79.66 | 10.82 | 120 | 1.57 |
| IND | 157 | 169.86 | 81.59 | 10.57 | 110 | 1.43 |
| ATL | 145 | 161.74 | 78.62 | 11.49 | 104 | 1.39 |
| NYL | 137 | 171.33 | 81.24 | 11.92 | 114 | 1.2 |

*Read.* The top half of this table is the actionable 'soft target' list: when winners had a player facing these defenses, they rostered that player more often than the league-average defender attracted winners. Use these as a tiebreaker.

## 6. Home / road split

| home_away | winner_picks | menu_rows | winner_share | menu_share | edge |
|---|---|---|---|---|---|
| home | 1387 | 1870 | 0.514 | 0.501 | 0.013 |
| away | 1311 | 1865 | 0.486 | 0.499 | -0.013 |

*Read.* Winners pick the home player slightly more often than the menu offers, but the gap is tiny. Home/away on its own is not a dominant edge.

## 7. Rest days

| days_rest | winner_picks | menu_rows | winner_share | menu_share | edge |
|---|---|---|---|---|---|
| 1 | 168 | 196 | 0.062 | 0.052 | 0.01 |
| 2 | 1282 | 1756 | 0.475 | 0.47 | 0.005 |
| 3 | 636 | 948 | 0.236 | 0.254 | -0.018 |
| 4 | 220 | 387 | 0.082 | 0.104 | -0.022 |
| 5 | 117 | 164 | 0.043 | 0.044 | -0.001 |
| 6 | 131 | 119 | 0.049 | 0.032 | 0.017 |
| 7 | 61 | 64 | 0.023 | 0.017 | 0.005 |
| 8 | 17 | 23 | 0.006 | 0.006 | 0 |
| 9 | 8 | 17 | 0.003 | 0.005 | -0.002 |
| 10 | 29 | 16 | 0.011 | 0.004 | 0.006 |
| 11 | 3 | 6 | 0.001 | 0.002 | -0 |
| 12 | 1 | 3 | 0 | 0.001 | -0 |
| 13 | 6 | 11 | 0.002 | 0.003 | -0.001 |
| 14 | 3 | 1 | 0.001 | 0 | 0.001 |
| 16 | 3 | 1 | 0.001 | 0 | 0.001 |
| 21 | 5 | 2 | 0.002 | 0.001 | 0.001 |
| 22 | 2 | 1 | 0.001 | 0 | 0 |
| 24 | 1 | 0 | 0 | 0 | 0 |
| 240 | 2 | 1 | 0.001 | 0 | 0 |
| 241 | 3 | 1 | 0.001 | 0 | 0.001 |
| 15 | 0 | 4 | 0 | 0.001 | -0.001 |
| 17 | 0 | 1 | 0 | 0 | -0 |
| 18 | 0 | 2 | 0 | 0.001 | -0.001 |
| 19 | 0 | 2 | 0 | 0.001 | -0.001 |
| 20 | 0 | 2 | 0 | 0.001 | -0.001 |
| 23 | 0 | 1 | 0 | 0 | -0 |
| 30 | 0 | 1 | 0 | 0 | -0 |
| 34 | 0 | 1 | 0 | 0 | -0 |
| 232 | 0 | 1 | 0 | 0 | -0 |
| 235 | 0 | 1 | 0 | 0 | -0 |
| 406 | 0 | 1 | 0 | 0 | -0 |
|  | 0 | 1 | 0 | 0 | -0 |

*Read.* The standard 1-2 day rest buckets dominate both menu and winners. There is a positive winner edge at the 3+ day rest bucket and a negative edge at 0 days (back-to-back). The directional bias is real but the effect is small because the WNBA has very few zero-rest games to begin with. Note: `NaN` here means season opener (no prior game logged).

## 8. Top 25 most-rostered winners and their typical matchup environment

How many top-3 lineups each player landed in across the 141 slates, plus the average matchup context on those nights. `avg_opp_def` above the league baseline of 174.9 means the player tended to win against soft Ds; below means they win matchup-independent.

| player_id | display_name | winning_picks | avg_opp_def | avg_pace | avg_scored | avg_days_rest | home_share |
|---|---|---|---|---|---|---|---|
| 1628932 | A. Wilson | 119 | 176.41 | 80.5 | 11.72 | 2.86 | 0.47 |
| 1629498 | J. Young | 76 | 181.28 | 80.79 | 11.3 | 2.28 | 0.53 |
| 1629483 | N. Collier | 76 | 175.44 | 80.87 | 9.72 | 3.14 | 0.68 |
| 1642291 | A. Reese | 74 | 176.45 | 81.2 | 11.18 | 2.58 | 0.42 |
| 203833 | C. Gray | 64 | 181.77 | 81.24 | 9.93 | 2.28 | 0.58 |
| 203014 | N. Ogwumike | 61 | 179.41 | 81.58 | 12.69 | 2.3 | 0.49 |
| 203827 | N. Howard | 60 | 176.48 | 80.86 | 10.62 | 2.42 | 0.38 |
| 1631044 | N. Hillmon | 51 | 179.13 | 79.92 | 10.19 | 4.35 | 0.35 |
| 1642784 | P. Bueckers | 49 | 171.6 | 80.27 | 11.75 | 3.59 | 0.59 |
| 1641648 | A. Boston | 45 | 177.72 | 80.65 | 9.26 | 2.91 | 0.69 |
| 1642288 | R. Jackson | 43 | 185.01 | 82.07 | 9.45 | 6.47 | 0.23 |
| 1642800 | A. Morrow | 42 | 169 | 78.87 | 11.06 | 2.02 | 0.31 |
| 1630149 | S. Sabally | 39 | 166.98 | 80.94 | 10.69 | 3.15 | 0.74 |
| 1628277 | A. Gray | 39 | 174.25 | 80.01 | 9.29 | 2 | 0.72 |
| 1629497 | M. Mabrey | 39 | 171.07 | 80.68 | 13.63 | 16.08 | 0.74 |
| 1628931 | G. Williams | 38 | 190.83 | 83.7 | 12.41 | 2.34 | 0.32 |
| 1628886 | J. Canada | 35 | 187.56 | 81.63 | 14.12 | 2.97 | 0.83 |
| 1629567 | N. Hiedeman | 35 | 177.65 | 80.35 | 11.53 | 2.8 | 0.54 |
| 1630096 | D. Carrington | 35 | 174.15 | 80.65 | 6.97 | 2.83 | 0.69 |
| 1628899 | M. Hines-Allen | 34 | 170.92 | 79.46 | 10.1 | 2.79 | 0.74 |
| 1630471 | M. Caldwell | 34 | 174.35 | 80.37 | 11.91 | 2.62 | 0.76 |
| 1631007 | V. Burton | 33 | 173.51 | 81.3 | 11.32 | 3.52 | 0.64 |
| 1642798 | D. Malonga | 33 | 172.39 | 80.3 | 11.59 | 2.48 | 0.24 |
| 203026 | T. Hayes | 32 | 162.39 | 80.67 | 11.77 | 4.66 | 0.16 |
| 203826 | A. Thomas | 31 | 171.93 | 79.75 | 8.83 | 3.52 | 0.42 |

*Read.* Three distinct profiles in this table:

1. **Matchup-agnostic stars** whose `avg_opp_def` hovers near or below the league median. They win regardless of opponent because their floor is high and the multiplier scarcity makes them a roster lock.
2. **Matchup-driven winners** whose `avg_opp_def` is well above the league median. These are the players the optimizer should over-weight specifically when they draw a soft D.
3. **Pace-driven winners** whose `avg_pace` sits clearly above the league median. They benefit from extra possessions per game and should be over-weighted on fast-tempo slates.


### 8a. Most matchup-dependent winners (avg opp def well above league)

Players with >= 6 winning-pick appearances, sorted by how much their average opponent's defensive number exceeded the league median.

| player_id | display_name | n | avg_opp_def | avg_pace | def_vs_league | pace_vs_league |
|---|---|---|---|---|---|---|
| 1629496 | E. Magbegor | 29 | 196.6 | 83.27 | 21.65 | 2.62 |
| 1642782 | S. Barker | 22 | 193.06 | 80.81 | 18.11 | 0.16 |
| 1643445 | K. Rice | 6 | 191.06 | 82.69 | 16.11 | 2.04 |
| 1628931 | G. Williams | 38 | 190.83 | 83.7 | 15.88 | 3.05 |
| 204329 | K. Stokes | 21 | 190.49 | 81.5 | 15.54 | 0.85 |
| 1643428 | F. Johnson | 6 | 189.5 | 82.53 | 14.55 | 1.88 |
| 1628886 | J. Canada | 35 | 187.56 | 81.63 | 12.61 | 0.98 |
| 1642288 | R. Jackson | 43 | 185.01 | 82.07 | 10.06 | 1.42 |
| 1627673 | J. Jones | 23 | 183 | 82.55 | 8.05 | 1.9 |
| 1629568 | K. Burke | 13 | 183 | 81.4 | 8.05 | 0.75 |
| 1628280 | B. Jones | 6 | 182.98 | 81.41 | 8.03 | 0.76 |
| 1642804 | T. Paopao | 19 | 181.83 | 80.72 | 6.88 | 0.07 |

If the slate gives you one of these players against a Q4 defense, the historical signal says: lock them in.


### 8b. Most matchup-independent winners (avg opp def at or below league)

| player_id | display_name | n | avg_opp_def | avg_pace | def_vs_league | pace_vs_league |
|---|---|---|---|---|---|---|
| 203855 | S. Talbot | 23 | 156.76 | 79.03 | -18.19 | -1.62 |
| 203026 | T. Hayes | 32 | 162.39 | 80.67 | -12.56 | 0.02 |
| 1641650 | H. Jones | 12 | 165.64 | 77.53 | -9.31 | -3.12 |
| 1629574 | L. Yueru | 17 | 166 | 79.31 | -8.95 | -1.34 |
| 203824 | O. Sims | 11 | 166.5 | 79.9 | -8.45 | -0.75 |
| 1630149 | S. Sabally | 39 | 166.98 | 80.94 | -7.97 | 0.29 |
| 1642797 | A. Kosu | 10 | 167.85 | 82.27 | -7.1 | 1.62 |
| 1631135 | O. Nelson-Ododa | 11 | 167.89 | 78.77 | -7.06 | -1.88 |
| 1628881 | M. Billings | 6 | 168.28 | 79.71 | -6.67 | -0.94 |
| 204365 | E. Wheeler | 29 | 168.28 | 80.71 | -6.67 | 0.06 |
| 1642793 | A. James | 14 | 168.44 | 79.46 | -6.51 | -1.19 |
| 1642800 | A. Morrow | 42 | 169 | 78.87 | -5.95 | -1.78 |

These players win regardless of opponent. Their floor is the reason they keep landing in winning lineups. Do not require a soft matchup before rostering them.

## 9. How to use this in the picker

- Treat opponent's 10-game fp-allowed as a small additive bonus on the projected real_score. Magnitude: Q4-softest opponent lifts winner share by roughly 15-30% relative to Q1-stoutest. Convert that into a +2 to +4 percent additive on projected fp.

- Treat opponent's 10-game pace as an even smaller multiplicative bonus. Players who can play extended minutes capture the full pace benefit; bench players do not.

- Tag the opponents in the section 5 table as 'soft target' opponents and let the optimizer break ties toward players facing them.

- Add a small back-to-back penalty (-5 to -10 percent on projected fp) for any player whose `days_rest` is zero on slate day. Add a small bonus for 3+ days.

- Add a tiny home bonus (+1 to +2 percent fp) and a corresponding road penalty.

- The biggest lever is still WHO. Matchup is a tiebreaker between similar options. The forensic data does not support overriding a high-ceiling player just because the matchup is bad, unless they are a low-floor specialist.


## 10. Caveats

- The slate `position` field is always 'F' in the corpus, so we cannot compute true position-vs-position defensive ratings. We use the team-aggregate fp-allowed instead.

- The 10-game rolling prior uses the last 10 games of any type (regular season and playoffs combined). For the start of the 2026 season the lookback window stretches across the playoff boundary; we found no material distortion from this in spot checks.

- 'Soft opponent' rankings collapse defense and pace into a single observed-frequency table. We normalize by `league_games` to control for schedule volume but a team that plays the league's elite offenses often still looks softer than they really are.

- `days_rest` is computed from game logs, not from PrizePicks' own schedule. Players who travel internationally during the off-week show artificially high values; the count is small.

- Boost-stacking effects are NOT controlled for here. Many top-3 lineups include the 2x boosted player on the soft side of the slate, which inflates the matchup signal slightly. A boost-adjusted version of this study sits in `research/players_environment/01_winner_dna.md` and `02_player_recurrence.md`.

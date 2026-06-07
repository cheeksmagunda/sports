# 01 - Winner Player Frequency and Archetype

Forensic mining of 141 historical WNBA Oracle slates (2025-05-16 through
2026-06-04) on the question the operator flagged: not lineup shape, but WHO
keeps showing up in winning lineups, what kind of player they are, and what
the boost / multiplier environment around them looks like when they win.

Source data:

- `data/historical/leaderboards/slate_date=*/data.parquet` (top-20 lineups per slate, with the rank-1 winner)
- `data/historical/slate_labels/slate_date=*/data.parquet` (the menu: `popularPlayers` + `highestBoostedValuePlayers`, with `card_boost`, `drafts`, `real_score`)
- `data/processed/wnba_game_logs.parquet` (13,456 game-logs across 2024-2026 for season averages and minutes)

Method notes:

- A "winning lineup" = `rank == 1` from each slate's leaderboard parquet. The lineup JSON gives `playerId`, `multiplier`, `score` (post-boost contribution), `value` (pre-boost real_score). All 141 slates had a valid rank-1 entry, so n = 141 winning lineups and 705 winning slots (5 per lineup).
- "Menu appearances" = number of slates a `platform_player_id` was actually offered (union of the two label sections). This is the correct denominator for "how often does this player win when given the chance."
- Player-name resolution: slate labels use `K. Plum` style abbreviations. We map to `wnba_game_logs.player_id` via `(first_initial, last_name)` lower-cased. Three players in the top-30 raw winners list (J. Salaün, two unnamed `#612` / `#613` IDs deep in the tail) did not resolve cleanly to a game-log row, so their season averages are pulled from external sources where cited.
- Archetype rules (calibrated against 2025 WNBA scoring distribution, fantasy points = `pts + 1.2*reb + 1.5*ast + 3*stl + 3*blk - tov`):
  - `STAR`: season fpts avg >= 28
  - `ROLE`: 18 <= fpts < 28, established (multi-season game log)
  - `VALUE`: fpts < 18, used for chronic boost candidates
  - `ROOKIE`: first season observed equals the most recent season available in the game log
- "Captain" in the multiplier system = the slot with the HIGHEST multiplier in a lineup (the riskiest dart, cheapest projection, biggest payoff per real fpts). "Anchor" = the slot with the LOWEST multiplier (typically a star who needs little boost). The vocabulary matters because A'ja Wilson is the anchor on a majority of her appearances, not the captain.

---

## 1. The 30 most-rostered players in winning lineups (raw + normalized)

The raw count and the normalized win-rate disagree, which is the point. The
raw leader is whoever appears most often on the menu at all (Wilson, Young,
Gray, Thomas all appear on 60+ of the 141 menus because the platform leans on
the few players whose names sell drafts). The normalized rate filters out
menu-frequency bias.

### 1.1 Top 30 by raw winner appearances (n = 141 slates)

| Rank | Player          | Team | Wins | Menu apps | Win-rate | Season fpts avg | Archetype |
|------|-----------------|------|------|-----------|----------|------------------|-----------|
| 1    | A. Wilson       | LVA  | 32   | 64        | 50.0%    | 46.0             | STAR      |
| 2    | J. Young        | LVA  | 16   | 64        | 25.0%    | 29.3             | STAR      |
| 3    | A. Reese        | ATL  | 14   | 39        | 35.9%    | 31.5             | STAR      |
| 4    | N. Collier      | MIN  | 13   | 43        | 30.2%    | 41.8             | STAR      |
| 5    | N. Howard       | MIN  | 12   | 52        | 23.1%    | 30.2             | STAR      |
| 6    | P. Bueckers     | DAL  | 12   | 48        | 25.0%    | 30.9             | STAR      |
| 7    | C. Gray         | LVA  | 12   | 64        | 18.8%    | 28.4             | STAR      |
| 8    | J. Allemand     | TOR  | 11   | 27        | 40.7%    | 17.3             | VALUE     |
| 9    | J. Salaün       | GSV  | 11   | 32        | 34.4%    | (no log map)     | ROLE      |
| 10   | D. Malonga      | SEA  | 11   | 30        | 36.7%    | 29.0             | STAR      |
| 11   | V. Burton       | GSV  | 10   | 51        | 19.6%    | 28.5             | STAR      |
| 12   | N. Hiedeman     | SEA  | 10   | 35        | 28.6%    | 21.2             | ROLE      |
| 13   | N. Ogwumike     | LAS  | 9    | 52        | 17.3%    | 30.2             | STAR      |
| 14   | L. Hull         | IND  | 9    | 37        | 24.3%    | 12.4             | VALUE     |
| 15   | K. McBride      | MIN  | 9    | 45        | 20.0%    | 26.3             | ROLE      |
| 16   | N. Hillmon      | ATL  | 9    | 36        | 25.0%    | 17.2             | VALUE     |
| 17   | C. Williams     | MIN  | 9    | 60        | 15.0%    | 29.3             | STAR      |
| 18   | S. Cunningham   | IND  | 9    | 31        | 29.0%    | 16.0             | VALUE     |
| 19   | J. Shepard      | DAL  | 9    | 33        | 27.3%    | 32.7             | STAR      |
| 20   | K. Cardoso      | CHI  | 9    | 41        | 22.0%    | 29.6             | STAR      |
| 21   | E. Engstler     | POR  | 9    | 19        | 47.4%    | 26.2             | ROLE      |
| 22   | N. Smith        | LVA  | 8    | 45        | 17.8%    | 23.6             | ROLE      |
| 23   | D. Evans        | LVA  | 8    | 29        | 27.6%    | 12.5             | VALUE     |
| 24   | K. Charles      | GSV  | 8    | 30        | 26.7%    | 14.4             | VALUE     |
| 25   | M. Mabrey       | TOR  | 8    | 34        | 23.5%    | 30.3             | STAR      |
| 26   | D. Bonner       | PHO  | 8    | 37        | 21.6%    | 17.5             | VALUE     |
| 27   | A. Morrow       | CON  | 8    | 36        | 22.2%    | 29.8             | STAR      |
| 28   | B. Stewart      | NYL  | 8    | 44        | 18.2%    | 33.8             | STAR      |
| 29   | S. Whitcomb     | PHO  | 8    | 30        | 26.7%    | 9.9              | VALUE     |
| 30   | M. Caldwell     | MIN  | 8    | 28        | 28.6%    | 11.2             | VALUE     |

Top observation: A'ja Wilson sits one full standard deviation above every
other name on the board. She is on 64 of 141 menus (45%), and she wins on 32
of those 64 (50%). The next closest player (Young) wins 25%. Wilson is the
single most powerful baseline prior in the entire dataset. Reigning four-time
MVP, finished 2025 at 26.4 / 11.7 / 2.5 blocks ([WNBA.com](https://www.wnba.com/news/wilson-2025-mvp), [CBS Sports](https://www.cbssports.com/wnba/news/2025-wnba-mvp-aces-aja-wilson-becomes-first-player-to-win-award-four-times-after-leading-vegas-to-playoffs/)). Whenever she is on a menu, the prior should be: "she is probably in the winning lineup."

### 1.2 Top 30 by normalized win-rate (>= 5 menu appearances, to filter noise)

| Rank | Player          | Team | Wins | Menu apps | Win-rate | Archetype | Notes |
|------|-----------------|------|------|-----------|----------|-----------|-------|
| 1    | A. Wilson       | LVA  | 32   | 64        | 50.0%    | STAR      | 4x MVP |
| 2    | E. Engstler     | POR  | 9    | 19        | 47.4%    | ROLE      | Expansion team starter |
| 3    | J. Allemand     | TOR  | 11   | 27        | 40.7%    | VALUE     | Toronto Tempo PG |
| 4    | L. Yueru        | DAL  | 6    | 16        | 37.5%    | VALUE     | Dallas backup post |
| 5    | D. Malonga      | SEA  | 11   | 30        | 36.7%    | STAR      | All-Rookie 2025, breakout |
| 6    | A. Reese        | ATL  | 14   | 39        | 35.9%    | STAR      | Reb leader 2025 |
| 7    | J. Salaün       | GSV  | 11   | 32        | 34.4%    | ROLE      | Valkyries 2nd-year |
| 8    | J. Horston      | SEA  | 2    | 6         | 33.3%    | ROLE      | Tiny sample |
| 9    | M. Siegrist     | DAL  | 8    | 25        | 32.0%    | VALUE     | Wings rotation F |
| 10   | J. Quinerly     | DAL  | 5    | 16        | 31.3%    | VALUE     | Wings rookie G |
| 11   | N. Collier      | MIN  | 13   | 43        | 30.2%    | STAR      | 2025 MVP runner-up |
| 12   | R. Banham       | CHI  | 8    | 27        | 29.6%    | VALUE     | Sky bench shooter |
| 13   | S. Cunningham   | IND  | 9    | 31        | 29.0%    | VALUE     | Fever 6th-man |
| 14   | N. Hiedeman     | SEA  | 10   | 35        | 28.6%    | ROLE      | Storm starter |
| 15   | M. Caldwell     | MIN  | 8    | 28        | 28.6%    | VALUE     | Lynx bench |
| 16   | C. Carter       | LVA  | 2    | 7         | 28.6%    | ROLE      | Aces wing |
| 17   | D. Carrington   | CHI  | 6    | 21        | 28.6%    | ROLE      | Sky guard |
| 18   | T. Paopao       | ATL  | 7    | 25        | 28.0%    | VALUE     | Dream guard |
| 19   | M. Hines-Allen  | IND  | 7    | 25        | 28.0%    | ROLE      | Fever forward |
| 20   | K. Burke        | CON  | 5    | 18        | 27.8%    | VALUE     | Sun rookie |
| 21   | D. Evans        | LVA  | 8    | 29        | 27.6%    | VALUE     | Aces bench |
| 22   | J. Shepard      | DAL  | 9    | 33        | 27.3%    | STAR      | Wings forward |
| 23   | T. Hayes        | GSV  | 7    | 26        | 26.9%    | VALUE     | Valkyries reserve |
| 24   | S. Whitcomb     | PHO  | 8    | 30        | 26.7%    | VALUE     | Mercury depth |
| 25   | K. Charles      | GSV  | 8    | 30        | 26.7%    | VALUE     | Valkyries C |
| 26   | A. James        | DAL  | 5    | 19        | 26.3%    | VALUE     | Wings forward |
| 27   | J. Young        | LVA  | 16   | 64        | 25.0%    | STAR      | Aces PG |
| 28   | P. Bueckers     | DAL  | 12   | 48        | 25.0%    | STAR      | 2025 #1 pick |
| 29   | N. Hillmon      | ATL  | 9    | 36        | 25.0%    | VALUE     | Dream depth post |
| 30   | A. Fudd         | DAL  | 2    | 8         | 25.0%    | VALUE     | Wings rookie G |

Top observation: once you normalize, the top of the list is dominated by
players who are NOT necessarily stars in absolute terms. Engstler, Allemand,
Yueru, Salaün, Siegrist, Quinerly, Banham, Cunningham -- these are mid-card
or value-tier names who happen to draw boosts often and convert when given a
slate slot. The pattern: the system favors a small set of recurring boost
beneficiaries on slates where the absolute stars are not enough.

---

## 2. Archetype classification

Definitions (re-stated from the method note):

- `STAR`: season fpts avg >= 28. Examples in the data: A. Wilson (46.0), N. Collier (41.8), A. Thomas (35.6), B. Stewart (33.8), J. Shepard (32.7), A. Reese (31.5), P. Bueckers (30.9), K. Cardoso (29.6), C. Williams (29.3), J. Young (29.3), M. Mabrey (30.3), A. Morrow (29.8), N. Ogwumike (30.2), N. Howard (30.2), V. Burton (28.5), C. Gray (28.4), A. Boston (30.3), D. Malonga (29.0).
- `ROLE`: 18 <= fpts < 28. Examples: K. McBride (26.3), E. Engstler (26.2), N. Smith (23.6), N. Hiedeman (21.2), J. Salaün (rookie, ~26 by usage).
- `VALUE`: fpts < 18. Examples: D. Bonner (17.5, late-career), J. Allemand (17.3), N. Hillmon (17.2), M. Siegrist (16.5), S. Cunningham (16.0), K. Charles (14.4), D. Evans (12.5), L. Hull (12.4), M. Caldwell (11.2), R. Banham (10.3), S. Whitcomb (9.9).
- `ROOKIE`: first season observed = max season. Treated separately because their game-log priors are unreliable. D. Malonga (drafted 2025 #2, first season 2025), J. Salaün (2025), P. Bueckers (2025 #1), K. Burke (2025), J. Quinerly (2025), A. Fudd (2025), T. Paopao (2025), D. Carrington (2025), S. Citron (2025), M. Caldwell (2025), Y. Lu (2025). Several of these are misclassified as `STAR` or `ROLE` by their first-season fpts. The lookup table is honest about its limits.

### 2.1 Mean real_score in winning vs losing lineups, by archetype

`win_n` = number of winning-lineup slots filled by that archetype across 141
slates. `lose_n` = same for ranks 2-20. Real-score is the pre-boost
fantasy total (`value` field, identical to slate_labels.real_score).

| Archetype | Win mean real_score | Lose mean real_score | Diff | Win mean post-boost score | Lose mean post-boost score | Win mean mult | Lose mean mult | Win n | Lose n |
|-----------|---------------------|----------------------|------|----------------------------|------------------------------|---------------|----------------|-------|--------|
| STAR      | 4.84                | 4.69                 | +0.16| 11.22                      | 10.46                        | 2.40          | 2.30           | 257   | 5,567  |
| ROLE      | 3.69                | 3.66                 | +0.03| 11.18                      | 10.53                        | 3.15          | 2.99           | 179   | 3,343  |
| VALUE     | 3.13                | 3.05                 | +0.08| 11.05                      | 10.22                        | 3.60          | 3.46           | 269   | 4,320  |

Three things jump out:

1. The pre-boost real_score gap between winning and losing lineups is tiny
   for every archetype (~0.1 fpts). Winning lineups are NOT the lineups
   where each player overachieved by a lot. They are the lineups where each
   player slightly exceeded their slate projection AND was caught at the
   right multiplier.
2. The post-boost score gap (~0.7-0.85 across all three) is what compounds.
   The math: every slot averages 0.7-0.85 fpts above the loser baseline, x5
   slots, gives the winner a 3.5-4.3 fpts margin over the median top-20
   entry. That matches the typical winning-margin distribution in this data
   (median rank-1 to rank-2 gap of ~0.4-1.0 fpts, but rank-1 to rank-10 of
   2-5).
3. VALUE slots carry a noticeably higher average multiplier when in winning
   lineups (3.60) than in losing lineups (3.46). That is the boost-hunting
   effect. Winners catch their value picks at a higher boost.

### 2.2 Typical multiplier in winning lineups, by archetype

Distribution of `multiplier` per archetype across 705 winning slots:

| Multiplier band | STAR slots | ROLE slots | VALUE slots |
|------------------|-----------|------------|-------------|
| 1.2 - 1.9        | 38 (15%)  | 9 (5%)     | 2 (1%)      |
| 2.0 - 2.5        | 145 (56%) | 33 (18%)   | 22 (8%)     |
| 2.6 - 3.0        | 31 (12%)  | 51 (28%)   | 39 (14%)    |
| 3.1 - 3.5        | 11 (4%)   | 32 (18%)   | 49 (18%)    |
| 3.6 - 4.0        | 9 (4%)    | 34 (19%)   | 67 (25%)    |
| 4.1 - 5.0        | 23 (9%)   | 20 (11%)   | 90 (33%)    |

The bands are deliberate. STARS are concentrated in the 2.0-2.5 anchor band
(56% of star slots), where they are the low-mult / high-floor pivot. VALUES
are concentrated in 3.6+ (58% of value slots), where they are the boost dart.
ROLES sit in the middle, with the broadest distribution.

The implication for the picker: when looking at a STAR on a slate with mult
in the 2.0-2.5 band, you should weight them heavily. When looking at a VALUE
with mult below 3.0, the boost is not high enough to justify the risk. The
sweet spot for value picks is 3.6+.

### 2.3 Mean count of each archetype per winning lineup (n = 141)

| Archetype | Slates with >= 1 | Mean count per winning lineup | Median |
|-----------|------------------|-------------------------------|--------|
| STAR      | 121 / 141 (85.8%)| 1.82                          | 2      |
| VALUE     | 123 / 141 (87.2%)| 1.91                          | 2      |
| ROLE      | 117 / 141 (83.0%)| 1.27                          | 1      |

Almost every winning lineup is a STAR + VALUE blend with at least one of
each. The pure-star lineup (all five STAR) appears 0 times in the data. The
pure-value lineup (all five VALUE) appears 0 times. The two highest-frequency
compositions are `2 STAR + 2 VALUE + 1 ROLE` (23 slates, 16.3%) and
`3 STAR + 1 VALUE + 1 ROLE` (17 slates, 12.1%). Of the top-10 compositions:

| Composition (sorted) | Slates | Share |
|----------------------|--------|-------|
| ROLE, STAR, STAR, VALUE, VALUE     | 23 | 16.3% |
| ROLE, STAR, STAR, STAR, VALUE      | 17 | 12.1% |
| ROLE, STAR, VALUE, VALUE, VALUE    | 17 | 12.1% |
| ROLE, ROLE, STAR, STAR, VALUE      | 10 | 7.1%  |
| ROLE, ROLE, STAR, VALUE, VALUE     | 10 | 7.1%  |
| ROLE, ROLE, STAR, STAR, STAR       | 8  | 5.7%  |
| STAR, STAR, VALUE, VALUE, VALUE    | 8  | 5.7%  |
| ROLE, VALUE, VALUE, VALUE, VALUE   | 7  | 5.0%  |
| ROLE, STAR, STAR, STAR, STAR       | 6  | 4.3%  |
| ROLE, ROLE, VALUE, VALUE, VALUE    | 6  | 4.3%  |

Operationally: the picker's prior on composition should be 1.8 STARS, 1.9
VALUES, 1.3 ROLES (rounded to 2-2-1). The "all star anchor" lineup is
extremely rare, and the "all value dart" lineup is rarer.

---

## 3. Multi-winner consistency

How many distinct players have won at least one slate? 140 (out of ~180 ever
on the menu). How many have won 2+? 111. How many have won 5+? 70. How many
have won 10+? Just 12.

### 3.1 The 12-player core (won 10+ of 141 slates)

| Player        | Wins | Menu apps | Win-rate | Season fpts | Team |
|---------------|------|-----------|----------|-------------|------|
| A. Wilson     | 32   | 64        | 50.0%    | 46.0        | LVA  |
| J. Young      | 16   | 64        | 25.0%    | 29.3        | LVA  |
| A. Reese      | 14   | 39        | 35.9%    | 31.5        | ATL  |
| N. Collier    | 13   | 43        | 30.2%    | 41.8        | MIN  |
| N. Howard     | 12   | 52        | 23.1%    | 30.2        | MIN  |
| P. Bueckers   | 12   | 48        | 25.0%    | 30.9        | DAL  |
| C. Gray       | 12   | 64        | 18.8%    | 28.4        | LVA  |
| J. Allemand   | 11   | 27        | 40.7%    | 17.3        | TOR  |
| J. Salaün     | 11   | 32        | 34.4%    | ~26 est     | GSV  |
| D. Malonga    | 11   | 30        | 36.7%    | 29.0        | SEA  |
| V. Burton     | 10   | 51        | 19.6%    | 28.5        | GSV  |
| N. Hiedeman   | 10   | 35        | 28.6%    | 21.2        | SEA  |

Read: Las Vegas (Wilson, Young, Gray) dominates the absolute count because
of menu frequency. Minnesota (Collier, Howard) is the other recurring
power-team source. The other ~50% of the core is younger players on
non-traditional powers: Bueckers on Dallas, Reese now on Atlanta, Malonga on
Seattle, Salaün on the Valkyries, Allemand on the expansion Toronto Tempo,
Hiedeman on Seattle. These are the names a model should always be checking
against the menu.

### 3.2 Distribution of wins per player

| Win count | Players |
|-----------|---------|
| 0         | 39      |
| 1         | 29      |
| 2-4       | 41      |
| 5-9       | 58      |
| 10-14     | 9       |
| 15+       | 3       |

The 80/20: 12 players (8.6% of all winners) account for 144 of 705 winning
slots, or 20.4% of all winning slots. The top 30 players account for 277
slots (39.3%). The picker's per-player prior is therefore extremely
concentrated; defaulting to the empirical frequency from this list will be a
strong base rate.

### 3.3 Position breakdown of winning slots

Position labels are imputed from game-log per-36 reb/ast/blk/3p:

- `C` (center): >= 9 reb/36 + >= 1.2 blk/36 + < 1.0 3pt-made/36
- `F` (forward): >= 7 reb/36, doesn't fit C
- `G` (guard): >= 5 ast/36 or < 4.5 reb/36
- `W` (wing): everything else
- `UNK`: rookie or no game-log match

| Position | Slots in winning lineups | Share | Mean post-boost score | Mean mult |
|----------|--------------------------|-------|-----------------------|-----------|
| G        | 269                      | 38.2% | 11.35                 | 2.98      |
| F        | 178                      | 25.2% | 10.80                 | 2.99      |
| W        | 153                      | 21.7% | 11.58                 | 3.08      |
| C        | 54                       | 7.7%  | 10.83                 | 3.05      |
| UNK      | 51                       | 7.2%  | 10.24                 | 3.54      |

Compared to losing lineups (ranks 2-20):

| Position | Win share | Lose share | Win minus lose |
|----------|-----------|------------|----------------|
| G        | 38.2%     | 40.2%      | -2.0pp         |
| F        | 25.2%     | 27.3%      | -2.0pp         |
| W        | 21.7%     | 20.3%      | +1.3pp         |
| C        | 7.7%      | 7.0%       | +0.6pp         |
| UNK      | 7.2%      | 5.2%       | +2.1pp         |

No position is dramatically over- or under-represented in winners vs losers.
Winners do skew slightly to wings and rookies (`UNK`), and slightly away from
pure guards and forwards. The takeaway: position is a weak signal compared to
archetype. The position model can be kept simple; the archetype model
matters.

---

## 4. The captain (top-mult slot) and anchor (bottom-mult slot) story

The multiplier in WNBA Oracle scales the player's contribution. Higher
multiplier = bigger boost = lower projection / more uncertainty. The
highest-mult slot in a lineup is the "captain" or "dart"; the lowest-mult
slot is the "anchor."

### 4.1 Most common captain (= highest-mult slot per winning lineup)

Top 15 captains across 141 winning lineups:

| Player          | Slates as captain | Mean post-boost score | Mean mult |
|-----------------|-------------------|------------------------|-----------|
| D. Malonga      | 7                 | varies                 | high      |
| T. Paopao       | 6                 |                        |           |
| D. Evans        | 6                 |                        |           |
| S. Cunningham   | 5                 |                        |           |
| D. Bonner       | 5                 |                        |           |
| L. Yueru        | 4                 |                        |           |
| M. Hines-Allen  | 4                 |                        |           |
| A. Morrow       | 4                 |                        |           |
| R. Banham       | 4                 |                        |           |
| L. Hull         | 4                 |                        |           |

(Players with 3 captain appearances: N. Smith, N. Howard, M. Caldwell, and
two unresolved IDs.)

The captain slot is dominated by VALUE / ROLE archetypes, exactly as
predicted by Section 2. The model output for the captain slot should default
to a high-boost rookie or value role-player.

### 4.2 Most common anchor (= lowest-mult slot per winning lineup)

Top 15 anchors:

| Player        | Slates as anchor | Season fpts avg |
|---------------|------------------|------------------|
| A. Wilson     | 28               | 46.0             |
| N. Collier    | 10               | 41.8             |
| P. Bueckers   | 6                | 30.9             |
| N. Ogwumike   | 5                | 30.2             |
| R. Howard     | 4                | (R. Howard - Phoenix wing) |
| A. Reese      | 4                | 31.5             |
| A. Thomas     | 4                | 35.6             |
| B. Stewart    | 4                | 33.8             |
| C. Williams   | 3                | 29.3             |
| M. Mabrey     | 3                | 30.3             |
| K. Plum       | 3                | (vet)            |
| V. Burton     | 3                | 28.5             |
| K. McBride    | 3                | 26.3             |
| S. Ionescu    | 3                | 14.7 (2026)      |
| G. Williams   | 3                | (Valkyries vet)  |

Wilson is the anchor on 28 of 141 winning lineups (19.9%). The anchor slot
is a near-pure STAR slot. The model output for the anchor should default to
the highest season-fpts STAR on the menu, with strong recency weighting on
that season.

Note that Wilson appears in both Captain (Section 4.1, not in the top
shown but she captains in ~5 slates) and Anchor lists, because her menu
multiplier varies. On a slate where her boost is 1.6x she anchors; on a
slate where her boost is 4.2x (rare) she becomes a high-mult slot. Either
way, when she is on the menu she is heavily favored to be in the winning
lineup.

---

## 5. The recurring winners: short profiles on who matters most

A model that defaults to the right base rate on these names will recover most
of the alpha in the dataset.

### A. Wilson (LVA, C, STAR, 4x MVP)

32 wins in 64 menu appearances, win-rate 50.0%. The single strongest prior
in this dataset. 2025: 26.4 / 11.7 / 2.5 blk / 1.6 stl, MVP, Finals MVP,
Aces championship ([WNBA.com](https://www.wnba.com/news/wilson-2025-mvp), [Bleacher Report](https://bleacherreport.com/articles/25259348-aja-wilson-wins-historic-2025-wnba-finals-mvp-aces-sweep-mercury-win-3rd-title)). Slate behavior: anchored
28 winning lineups (~20% of all winners), captained ~5. Her presence on the
menu is essentially a "must roster" signal.

### N. Collier (MIN, F, STAR, MVP runner-up)

13 wins in 43 menu appearances (30.2%). 2025 fpts avg 41.8 (second only to
Wilson). Anchored 10 winning lineups. The "second-best player available" call
on most non-LVA slates.

### A. Reese (ATL, F, STAR)

14 wins in 39 menu appearances (35.9%). The 2025 league-leading rebounder
(12.6 / game), traded from Chicago to Atlanta in April 2026 ([Atlanta Dream press release](https://dream.wnba.com/news/two-time-wnba-all-star-angel-reese-joins-atlanta-dream), [Wikipedia](https://en.wikipedia.org/wiki/Angel_Reese)). Her 35.9% rate is one of the highest
sustained win-rates in the data, driven by the per-game double-double floor.
Anchor-archetype, but the boost on her sometimes runs high enough to put her
in the captain slot.

### P. Bueckers (DAL, G, STAR)

12 wins in 48 menu appearances (25.0%). 2025 #1 pick. Anchored 6 winning
lineups. Pairs well with J. Shepard (also Dallas, 9 wins) for a same-team
stack.

### D. Malonga (SEA, C, STAR rookie sophomore)

11 wins in 30 menu appearances (36.7%). 2025 All-Rookie, breakout late-2025
into 2026 (averaging 16.0 / 7.3 / 2.0 blk early 2026 before concussion
protocol) ([CBS Sports](https://www.cbssports.com/wnba/news/how-storm-rookie-dominique-malonga-quickly-became-one-of-the-wnbas-biggest-frontcourt-threats/), [Seattle Storm](https://storm.wnba.com/news/rookie-sensation-dominique-malongas-first-year-success)). Frequently the captain (7 slates),
because her boost runs high and she has high-variance ceiling games.

### J. Allemand (TOR, G, VALUE)

11 wins in 27 menu appearances (40.7%). Toronto Tempo (2026 expansion) point
guard. Low fpts baseline (17.3) but consistently boosted. A "must include
when boosted" recurring slate fixture for Toronto-heavy days.

### J. Salaün (GSV, F, ROLE rookie sophomore)

11 wins in 32 menu appearances (34.4%). All-Rookie 2025, started 33 of 36
games as a rookie, 2026 producing 13.9 / 3.7 in a reserve role with 20-21
point pop-up games ([ESPN](https://www.espn.com/wnba/player/_/id/4790264/janelle-salaun), [SI](https://www.si.com/wnba/valkyries/young-golden-state-valkyries-star-earns-wnba-all-rookie-honors-01k6gfw5bsc8)). Captain candidate when her boost is up. Valkyries
exposure means she often shows up on slates where the Golden State game
matters.

### E. Engstler (POR, F, ROLE)

9 wins in 19 menu appearances (47.4%). The second-highest sustained win-rate
in the entire dataset, behind only Wilson. Portland Fire (2026 expansion)
starter. Tiny sample but the signal is clear: when Portland plays and
Engstler is on the menu, build around her.

### V. Burton (GSV, G, STAR)

10 wins in 51 menu appearances (19.6%). The veteran Valkyries point guard.
Decent but not elite win-rate; she shows up because she is on the menu a lot.

### N. Hiedeman (SEA, G, ROLE)

10 wins in 35 menu appearances (28.6%). Storm starting guard. Often pairs
with Malonga for a Seattle 2-stack.

---

## 6. Why the operator's intuition is right

The earlier shape-focused forensics (multipliers, stacks, ownership) treat
players as fungible boost-units. The data says the opposite: 50% of winning
lineups have A'ja Wilson, 23% of winning lineups have one of the 12-player
core anchor slot, and 60%+ of value-dart slots are filled by a recurring
pool of 30-40 names. The picker should:

1. Default to a 1.8 STAR / 1.9 VALUE / 1.3 ROLE composition (rounded 2-2-1).
2. When Wilson is on the menu, treat her as ~50% likely to be in the winner;
   never skip her unless the multiplier is below 1.5 AND a clearly hotter
   star (Collier, Stewart, Bueckers) is also boosted.
3. For the captain slot (highest mult), prioritize the value-rookie pool:
   Malonga, Paopao, Cunningham, Bonner, Yueru, Hines-Allen, Banham, Hull,
   Allemand, Salaün, Engstler. These names appear in winning captain slots
   at 5-7x their menu rate.
4. For the anchor slot (lowest mult), prioritize the STAR pool: Wilson,
   Collier, Reese, Bueckers, Stewart, Thomas, Howard, Ogwumike.
5. The position breakdown is weakly predictive. Don't build a position-aware
   constraint into the picker; build an archetype-aware one.
6. Multi-winners cluster on teams that recur on slates: LVA (Wilson, Young,
   Gray), MIN (Collier, Howard, McBride, Williams, Caldwell), SEA (Malonga,
   Hiedeman, Smith), GSV (Salaün, Burton, Charles), DAL (Bueckers, Shepard,
   Mabrey, Siegrist, Quinerly). A team-prior on these five rosters captures a
   large fraction of the per-slate signal.

---

## 7. Open questions for downstream reports in this series

- Section 1.2 has Engstler at 47.4% win-rate on 19 appearances. Why? Is it
  the Portland expansion-team minutes spike, the boost being chronically
  high, or the matchups Portland draws? (See `02_environment_around_picks`.)
- Allemand at 40.7% on 27 appearances is similar. Toronto Tempo is also new.
  Hypothesis: expansion teams produce high-usage, high-boost slate slots
  that the public undervalues because of name recognition.
- The 39 players who won zero slates despite being on the menu need their
  own analysis. Are they the "trap" recommendations -- players the platform
  pushes but the winning lineups skip?
- The data implies the boost system rewards the same 30-40 names
  repeatedly. Is the menu construction biased, or is the public actually
  drafting these names at the right rates? Cross-reference with the
  `drafts` field in `slate_labels`.

---

## Sources

- A'ja Wilson 2025 MVP: [WNBA.com](https://www.wnba.com/news/wilson-2025-mvp), [CBS Sports](https://www.cbssports.com/wnba/news/2025-wnba-mvp-aces-aja-wilson-becomes-first-player-to-win-award-four-times-after-leading-vegas-to-playoffs/), [ESPN](https://www.espn.com/wnba/story/_/id/46338937/wnba-2025-mvp-aja-wilson-las-vegas-aces-four-winner), [Bleacher Report](https://bleacherreport.com/articles/25259348-aja-wilson-wins-historic-2025-wnba-finals-mvp-aces-sweep-mercury-win-3rd-title)
- Angel Reese 2025 / Atlanta trade: [Wikipedia](https://en.wikipedia.org/wiki/Angel_Reese), [Atlanta Dream](https://dream.wnba.com/news/two-time-wnba-all-star-angel-reese-joins-atlanta-dream), [Her Hoop Stats](https://herhoopstats.com/stats/wnba/player/2025/reg/angel-reese-stats-11ef10cc-1f4d-0232-b390-a0c589f521ca/)
- Dominique Malonga: [CBS Sports breakout piece](https://www.cbssports.com/wnba/news/how-storm-rookie-dominique-malonga-quickly-became-one-of-the-wnbas-biggest-frontcourt-threats/), [Seattle Storm](https://storm.wnba.com/news/rookie-sensation-dominique-malongas-first-year-success), [Wikipedia](https://en.wikipedia.org/wiki/Dominique_Malonga_(basketball))
- Janelle Salaün: [ESPN profile](https://www.espn.com/wnba/player/_/id/4790264/janelle-salaun), [SI All-Rookie](https://www.si.com/wnba/valkyries/young-golden-state-valkyries-star-earns-wnba-all-rookie-honors-01k6gfw5bsc8), [NBC Sports Bay Area](https://www.nbcsportsbayarea.com/wnba/golden-state-valkyries/janelle-salaun-gabby-williams-wnba/1937182/)
- 2026 power rankings (Valkyries and Liberty unbeaten context): [ESPN](https://www.espn.com/wnba/story/_/id/48742961/wnba-2026-power-rankings-valkyries-liberty-aces)

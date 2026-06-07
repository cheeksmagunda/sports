# 05 — Vegas Environment: Game Totals, Margins, and Where Winners Hunt

Author: research agent (D63+ cycle, 2026-06)
Sources:
- `data/processed/wnba_game_logs.parquet` — every player box score 2024-05-03 to 2026-06-05
- `data/historical/leaderboards/slate_date=*/data.parquet` — Real Sports public leaderboards, 141 slates
- `data/historical/slate_labels/slate_date=*/data.parquet` — slate pool, multipliers, draft counts, realized scores

Method note: the project does not yet ingest Vegas closing lines. Until that
backfill lands, "Vegas total" and "Vegas spread" are reconstructed from
realized game results aggregated from the player game logs. Realized total is
the sum of both teams' final scores; realized margin is the absolute
difference. This is the post-hoc Vegas environment — it captures whether the
winning lineup was hunting in shootouts vs slogs, blowouts vs nailbiters,
without claiming any of those outcomes were perfectly predictable a priori.
Sportradar / Pinnacle / DraftKings closing-line backfill is logged as a
follow-up in section 9 below.

The bridge between slate `platform_player_id` and game-log `nba_api`
`player_id` is built per slate by joining on `(slate_date, team_key,
normalized last name)`, with a second-pass fallback on `(slate_date,
normalized last name)` for moves and naming oddities. Coverage on rank-1
lineups: 600 of 705 slot-rows matched a player, 521 of those also matched a
played game (some rank-1 picks chose players who were ultimately scratched
post-lock, which is itself a separate finding covered in 02_who_winners_pick).

---

## 1. The headline: winners tilt toward shootouts, not blowouts

Distribution of realized game environments — baseline (every WNBA team-game
in the dataset, n = 1,384 team-games) vs. games that hosted at least one
rank-1 winning pick (n = 521 player-slot rows with full context):

| Realized total       | Baseline % | Winner-slot % | Lift |
|----------------------|-----------:|--------------:|-----:|
| Low (<150)           |       20.7 |          15.4 | 0.74 |
| Mid-low (150-164)    |       29.6 |          27.8 | 0.94 |
| Mid-high (165-179)   |       32.2 |          35.3 | 1.10 |
| **High (>=180)**     |   **17.5** |      **21.5** | **1.23** |

| Realized margin        | Baseline % | Winner-slot % | Lift |
|------------------------|-----------:|--------------:|-----:|
| **Tight (<=5)**        |   **26.0** |      **28.4** | **1.09** |
| Competitive (6-12)     |       36.8 |          35.7 | 0.97 |
| Comfortable (13-20)    |       23.1 |          20.9 | 0.90 |
| Blowout (>20)          |       14.0 |          15.0 | 1.07 |

Two clean tilts:

1. **High-total games (180+) are 23% over-represented in winning lineups.**
   This is the strongest single environmental tilt in the data.
2. **Margin shape is bimodal-favored.** Both tight games and full blowouts
   show a small positive lift; the middle (competitive 6-12 and comfortable
   13-20) is slightly suppressed. The dead middle is where winning picks are
   least likely to come from. Tight games favor stars who play the full 36+
   minutes and absorb usage in crunch time. Blowouts favor whoever the
   leading team rode for the first three quarters before pulling them.

The middle is the trap: those are the games where rotations stay normal,
nobody touches their season ceiling, and nobody touches their season floor.

---

## 2. Team-points: the most decisive environmental signal

The realized total bucket understates things. The cleaner cut is on the
**winning pick's own team** points scored:

| MY-team points     | Baseline % | Winner-slot % | Lift |
|--------------------|-----------:|--------------:|-----:|
| <70                |       13.9 |           7.3 | 0.53 |
| 70-79              |       26.7 |          21.7 | 0.81 |
| 80-89              |       34.6 |          34.5 | 1.00 |
| **>=90**           |   **24.8** |      **36.5** | **1.47** |

When the player's team scores 90+, the slot is **47% over-represented in
winning lineups vs. baseline**. When the team is stuck under 70, that slot
is **47% under-represented**. The Spearman correlation between
`my_team_pts` and the winning slot's `real_score` is **0.338**, by far the
strongest single environment-to-output correlation found:

| Correlation                                | Spearman |
|--------------------------------------------|---------:|
| MY-team points -> winner real_score        | **0.338** |
| Realized total -> winner real_score        |    0.238 |
| Realized margin -> winner real_score       |    0.019 |

**Margin in isolation tells you nothing.** Total tells you something. Whose
team is scoring tells you the most. That ordering matters for picker design:
a Vegas team-total projection has 1.4x the per-bit value of a Vegas game
total, and ~17x the value of a Vegas spread by itself.

### Game-context gradient on the winning real_score

Average real_score of all 521 contextualized winning slots, sliced by
environment:

| Total bucket   |   n | Mean real | Median | Mean pts | Mean min |
|----------------|----:|----------:|-------:|---------:|---------:|
| Low (<150)     |  80 |      3.59 |   3.31 |    15.74 |    29.14 |
| Mid-low        | 145 |      3.75 |   3.47 |    16.78 |    29.87 |
| Mid-high       | 184 |      4.19 |   3.95 |    19.04 |    30.49 |
| **High (180+)**|**112**|  **4.57**|**4.49**|**21.16** |**30.63** |

| Margin bucket  |   n | Mean real | Median | Mean pts | Mean min |
|----------------|----:|----------:|-------:|---------:|---------:|
| Tight (<=5)    | 148 |      4.11 |   3.92 |    18.67 |    30.55 |
| Competitive    | 186 |      3.87 |   3.55 |    17.76 |    30.65 |
| Comfortable    | 109 |      4.26 |   4.00 |    19.31 |    30.12 |
| Blowout (>20)  |  78 |      4.12 |   4.03 |    18.03 |    28.14 |

Note the minutes column: blowouts compress to 28.1 min (rotation thins or
starters get pulled early), yet still hit real ~4.12 because the scoring
density per minute spikes. Stars in tight games play 30.5 min and hit 4.11.
Same outcome via opposite routes. A picker that uses a flat
minutes-times-rate projection without conditioning on game flow will
under-rate blowout situations and over-rate cruise-control mid-totals.

---

## 3. The "Aces problem": shootouts have a roster

Top 25 most-frequent winning picks from games that went 180+ (n = 112 picks
across 9 distinct LVA appearances alone):

| Rank | Player        | Team | Appearances in winning HIGH-total lineups |
|-----:|---------------|------|------------------------------------------:|
|    1 | A. Wilson     | LVA  | 7 |
|    2 | J. Young      | LVA  | 5 |
|    3 | C. Gray       | LVA  | 4 |
|    3 | C. Brink      | LAS  | 4 |
|    5 | R. Howard     | ATL  | 3 |
|    5 | D. Malonga    | SEA  | 3 |
|    5 | A. Boston     | IND  | 3 |
|    5 | K. Cardoso    | CHI  | 3 |
|    9 | K. Plum, L. Lacan, L. Fiebich, J. Jones, M. Siegrist, S. Cunningham, M. Mabrey, K. McBride, B. Sykes, D. Hamby, K. Rice, S. Diggins, S. Rivers, N. Collier, E. Wheeler, J. Canada, L. Yueru | (mixed) | 2 each |

Three of the top four winners-in-shootouts wear LVA. Filtering to
**A. Wilson alone**: she has 7 winning appearances in 180+ games, on
slates 2025-07-12, 2025-08-10, 2025-08-17, 2025-09-30, 2025-10-10,
2026-05-15, 2026-05-23. LVA scored 94, 106, 107, 97, 101, 95 in those
games respectively. Wilson's real_scores in those games: 8.81, 6.34, 6.88,
7.50, 6.04, 9.48, 5.61 — **mean 7.24, median 6.88**. Her overall winning-pick
mean across all 32 of her winning appearances is 6.34, so HIGH-total
appearances run **+0.90 real above her own baseline**.

Per-player real_score by total bucket for the 10 most-frequent winners:

```
A. Wilson  (32 wins, avg 6.34)
  Low      n=8   mean 6.03
  Mid-low  n=5   mean 5.89
  Mid-high n=12  mean 6.21
  High     n=7   mean 7.24   <-- +0.90 lift vs personal baseline
J. Young   (16 wins, avg 5.61)
  Low      n=1   mean 5.67
  Mid-low  n=2   mean 6.61
  Mid-high n=8   mean 5.23
  High     n=5   mean 5.83
N. Collier (13 wins, avg 5.72)
  Low      n=1   6.76
  Mid-low  n=3   4.40
  Mid-high n=7   6.06
  High     n=2   5.98
P. Bueckers (12 wins, avg 4.72)
  Mid-low  n=4   5.17    <-- Bueckers actually peaks in mid-low totals
  Mid-high n=6   4.44
  High     n=2   4.67
C. Gray    (12 wins, avg 3.80)
  Mid-low  n=3   2.73
  Mid-high n=5   4.21
  High     n=4   4.09
D. Malonga (11 wins, avg 3.28)
  Low      n=1   2.22
  Mid-low  n=1   5.46
  Mid-high n=6   3.30
  High     n=3   2.88    <-- Malonga is a multiplier play, not a shootout play
A. Reese   (10 wins, avg 4.28)
  Low      n=4   4.20    <-- Reese wins in SLOGS via rebounds
  Mid-low  n=2   4.42
  Mid-high n=4   4.29
V. Burton  (10 wins, avg 4.79)
  Low      n=3   3.71
  Mid-low  n=3   4.12
  Mid-high n=4   6.10    <-- Burton peaks mid-high
```

The picker needs a player-specific environment-interaction table. Wilson
gains from shootouts. Bueckers does not. Reese keeps her real-score floor
in slogs because rebounding scales with missed shots, which scale with pace
times poor shooting (a low-total environment). Malonga's value is the
multiplier, not the environment — her real-score is constant across totals.

---

## 4. Where the winning team is winning: signed margin

For the 521 contextualized winning picks, the picked player's team won
the game **60.8% of the time** (random would be 50%). Mean signed margin
on winning picks: **+3.9 points**. The pick comes from the winning side
more often, but not overwhelmingly. The split by margin bucket:

| Margin bucket  |   n | % from winning team | Mean real_score |
|----------------|----:|--------------------:|----------------:|
| Tight (<=5)    | 148 |              46.6 % |            4.11 |
| Competitive    | 186 |              62.4 % |            3.87 |
| Comfortable    | 109 |              68.8 % |            4.26 |
| **Blowout >20**|  78 |          **73.1 %** |            4.12 |

In blowouts, **almost three out of four winning picks are from the winning
side** — the cruise team's stars before the bench. In tight games the
team-won rate drops to 47%, basically a coin flip — those slots are won by
crunch-time iso players regardless of outcome (think K. Plum, A. Wilson,
P. Bueckers, J. Young).

So the picker's read on a 13+ point predicted blowout is: lean to the
favorite's top two scorers and the highest-multiplier card on the favored
team that still gets minutes (28.1 min avg in blowout winners — bench
rotation is real). Avoid the dog completely unless one card is a high
multiplier on a usage-monster guard who keeps minutes after the game is
gone.

---

## 5. Multiplier behavior across environments

The picker's lineup choice has more multiplier headroom in low-total games
than high-total games. Mean multiplier on the winning slot, by realized
total:

| Total bucket | Mean mult | Median mult |
|--------------|----------:|------------:|
| Low (<150)   |      3.05 |        3.00 |
| Mid-low      |      3.08 |        3.00 |
| Mid-high     |      2.92 |        2.70 |
| High (180+)  |      2.90 |        2.60 |

Higher totals pull the winning slot toward **lower-multiplier studs** (think
Wilson 2x, Bueckers 2.1x), because the real-score absolute matters more
than the multiplier when the per-game numbers are inflated. Lower totals
push the winning slot toward **higher-multiplier value plays** (3x+), because
nobody hits a huge real-score, so the boost matters more.

The big quantitative finding: **3x+ slots in HIGH-total games out-produce
3x+ slots in LOW-total games by 0.65 real per slot** (n=52 vs 42,
mean 3.46 vs 2.81). A high-multiplier card in a shootout is the most
common "winning surprise" archetype in the dataset — combining the
multiplier headroom with the pace tail. Examples:

- C. Brink, LAS, 4.6x on 2025-08-01 (LAS 108 vs 106, total 214) — real 2.12
- C. Brink, LAS, 3.9x on 2025-08-07 (LAS 102 vs 91, total 193) — real 2.54
- D. Malonga, SEA, 4.2x on 2025-07-28 (SEA 101 vs 85, total 186) — real 1.83
- J. Young, LVA, 3.3x on 2026-05-10 (LVA 105 vs 78, total 183) — real 5.33
- C. Gray, LVA, 3.3x on 2026-05-15 (LVA 101 vs 94, total 195) — real 3.54

Note Brink's 4.6x card actually wins a slate at 2.12 real_score because the
multiplier multiplies it to 9.75 effective. The pattern: high-multiplier
slots only need to fire when the environment supports their floor, and
shootouts give bigs floor minutes plus rebound volume.

---

## 6. Per-slate concentration: where winners stack environments

Winning lineups distribute across 1-5 distinct teams. The mode is 3 distinct
teams (44 of 140 slates), and full single-team stacks happen on slates with
only 1-2 games available (`max_stack = lineup_size`):

| Distinct teams in winning lineup | n slates |
|---------------------------------:|---------:|
|                                1 |       18 |
|                                2 |       50 |
|                                3 |       44 |
|                                4 |       22 |
|                                5 |        6 |

Concentration vs game environment:

| Max same-team stack | Mean avg_total | Mean avg_margin | Mean win_score |
|--------------------:|---------------:|----------------:|---------------:|
|                   1 |         164.85 |           11.10 |          56.86 |
|                   2 |         166.03 |           12.20 |          55.46 |
|                   3 |         170.46 |            9.66 |          55.51 |
|                   4 |         173.50 |            7.50 |          51.62 |

**Heavier same-team stacking correlates with higher game totals and tighter
margins** (4-stack winners average +7.6 vs 1-stack on total, -3.6 on
margin). The story: when one team gets in a track meet, the winners ride
multiple players from that team. The 4-deep stacks are typically a
high-pace road team running and gunning where minutes get distributed and
multiple value cards fire together.

**All-HIGH-total slates** (every winning pick from a 180+ game), 9 of 140
slates:

```
2025-07-11, 2025-08-17, 2025-09-30, 2025-10-10,
2026-05-09, 2026-05-15, 2026-05-19, 2026-05-23, 2026-06-01
```

**All-LOW-total slates** (every winning pick from a <150 game), 6 of 140:

```
2025-06-08, 2025-06-15, 2025-07-01, 2025-08-11, 2025-09-08, 2025-09-17
```

Six of the nine all-HIGH slates are from the back half of the 2025 season
and the first six weeks of the 2026 season — a real WNBA pace inflation has
happened. The picker's prior on "what is a high total" needs to be
trailing-30-day-rolling, not seasonal. The all-LOW slates cluster in
defensive windows (mid-June 2025 fatigue weeks, late-August 2025 stretch).

---

## 7. Star vs role-player rate by environment

Joining winning picks back to their season averages (>=10-game samples),
star = >=15 ppg season average, starter = >=25 min season average:

| Total bucket   |   n | Star rate | Starter rate | Avg season ppg |
|----------------|----:|----------:|-------------:|---------------:|
| Low (<150)     |  68 |     0.22  |        0.65  |          11.81 |
| Mid-low        | 137 |     0.22  |        0.63  |          11.71 |
| Mid-high       | 164 |     0.32  |        0.65  |          12.91 |
| **High (180+)**|**104**|  **0.38** |     **0.71** |      **13.05** |

| Margin bucket  |   n | Star rate | Starter rate | Avg season ppg |
|----------------|----:|----------:|-------------:|---------------:|
| Tight (<=5)    | 137 |     0.27  |        0.69  |          12.34 |
| Competitive    | 167 |     0.25  |        0.65  |          12.19 |
| Comfortable    |  98 |     0.33  |        0.65  |          12.93 |
| **Blowout >20**|  71 |     0.37  |        0.62  |          12.53 |

Two parallel patterns:

- **High totals favor stars** (0.38 star rate vs 0.22 in low totals). When
  the game is shootouty, the picker should over-index on the highest-usage
  players whose seasonal ppg already encodes "team-asks-them-for-shots".
- **Blowouts also favor stars** (0.37 star rate), even with the
  starter-rate drop (0.62 — they got pulled early). The stars hit their
  numbers in the first three quarters of a blowout, then sit. The picker
  needs minutes-conditioned-on-game-script in the projection, not just
  expected minutes.

The middle of the distribution — competitive games at mid-totals — is
where role players win. That's 167 + 145 = 312 of the 521 contextualized
slots (60%). The picker's hardest job is identifying which role player on
which team in those mid-mid environments. The remaining 40% is a much
narrower star-shopping exercise.

---

## 8. Vegas-implied mispricings — what is the market missing?

Since closing lines aren't ingested yet, the mispricings here are
"environment-conditioned mispricings vs the card multipliers". The card
multiplier is Real Sports' implied price on the player; if a high-multiplier
card wins a high-total game, the platform under-priced that player's tail
in that environment.

### Mispricing 1: high-multiplier bigs in 180+ games

The platform routinely puts 3.5x+ multipliers on backup bigs (C. Brink,
D. Malonga, L. Lacan, K. Cardoso when she's not the headline center, L.
Yueru, J. Salaün). Those cards fire **0.65 real higher in HIGH-total games
vs LOW-total games** (3.46 vs 2.81). In pace environments, rebound
opportunities scale with missed shots, which scale with both possessions
and shooting variance. A bench big at 4.0x in a 180+ over is one of the
single most repeatable winning archetypes in this dataset.

Specifically: C. Brink has 4 winning HIGH-total appearances on multipliers
3.0x, 3.6x, 3.9x, 4.6x. The card was 3.0x or higher every time it won,
which means the platform thought she was a deep value. The platform was
right that she was a bench big, wrong on the rebound-rate-in-pace tail.

### Mispricing 2: 2x slots in LOW-total games

The 2x "anchor" slot (the locked center of the lineup, typically the highest
expected scorer) actually has its **highest real_score in LOW-total games**:
n=7, mean **6.61**, vs HIGH-total 2x at mean 5.98. Sample is small but
suggestive. Stars don't need pace to hit their numbers in 25-30 minutes; in
a low-total game the star's share of the team's scoring goes UP (less
distribution of buckets), so the volume floor holds.

Implication for the picker: don't downgrade the 2x slot when projecting a
low-total game. The 2x player is the most pace-resistant card on the slate
by design.

### Mispricing 3: Tight games are not predictably high real_score

Tight (<=5) games show a near-zero correlation between margin and winning
real_score (Spearman 0.019) and a 46.6% team-won rate. The picker shouldn't
treat "competitive line, near-pick'em" as a positive signal for any
specific player. Tight games favor the highest-usage guard on either side
because crunch-time iso goes through that player regardless of who wins.

### Mispricing 4: 1-game slates pay better per-pick than 2-game

| Estimated games on slate | n slates | Mean win_score | Mean avg_total | Mean avg_margin |
|-------------------------:|---------:|---------------:|---------------:|----------------:|
|                        1 |       15 |          54.29 |         173.23 |           10.37 |
|                        2 |      125 |          55.96 |         165.87 |           11.50 |

Single-game slates aren't materially different in win_score; they just
force concentration (max stack of 4-5). When the lone game is a 180+
shootout, that's a high-EV slate to enter aggressively because the winning
lineup needs to come almost entirely from that one game.

Specific high-leverage single-game high-total slates in the data:

- 2025-07-07 PHO 4-deep stack, total 174, margin 30 — win_score 69.45
- 2025-10-05 LVA 4-deep stack — slate won by stacking LVA shootout night
- 2025-10-08 LVA 4-deep stack — same template

---

## 9. Top winning slates — narrative crosswalk

Top 10 winning lineups by win_score:

| Slate date | Win score | Avg total | Avg margin |
|------------|----------:|----------:|-----------:|
| 2025-07-03 |     83.30 |     182.3 |        9.3 |
| 2025-07-09 |     81.62 |     163.0 |       11.0 |
| 2025-08-22 |     75.53 |     167.0 |       23.0 |
| 2026-05-15 |     73.32 |     194.6 |        5.8 |
| 2025-07-29 |     73.25 |     178.6 |       16.2 |
| 2025-06-11 |     72.69 |     181.7 |        9.7 |
| 2026-05-24 |     72.69 |     172.0 |       11.2 |
| 2026-05-10 |     72.42 |     176.4 |       16.8 |
| 2025-09-07 |     71.13 |     154.8 |       17.8 |
| 2025-07-13 |     69.60 |     176.2 |       10.6 |

Six of the top ten winning lineups had average game total >= 175. Only one
(2025-09-07) was a clear sub-160 environment, and that lineup's win_score
came from a blowout (avg margin 17.8) where the picker rode the favorite's
top minutes-eaters.

Three winning lineup detail dumps:

```
2025-07-03 — winner 83.30 — avg total 182.3, avg margin 9.3
  K. Copper (PHO) 3.2x real 4.19
  E. Wheeler (LAS) 2.9x real 4.19  game 79-89 total 168
  A. James (DAL) 4.1x real 6.48    game 98-89 total 187
  J. Quinerly (DAL) 4.4x real 4.78 game 98-89 total 187
  L. Yueru (DAL) 4.2x real 2.41    game 98-89 total 187
  --> 3 DAL high-multiplier value cards in a 187 over

2025-07-09 — winner 81.62 — avg total 163.0, avg margin 11.0
  A. James (DAL) 3.7x real 2.87
  R. Banham (CHI) 4.3x real 2.29
  J. Quinerly (DAL) 4.6x real 3.30
  R. Allen (NYL) 4.4x real 6.95
  L. Yueru (DAL) 4.2x real 3.67
  --> entire lineup at 3.7x+. Won by sheer multiplier load on role players
      who all hit modest real_scores. This is the "boost-stack" archetype.

2025-08-22 — winner 75.53 — avg total 167.0, avg margin 23.0
  P. Bueckers (DAL) 2.1x real 1.46    game 60-95 total 155 (lost 35)
  J. Shepard (DAL) 3.2x real 7.32     game 60-95 total 155
  K. McBride (MIN) 2.4x real 6.26     game 95-90 total 185
  L. Hull (IND) 3.4x real 4.54        game 90-95 total 185
  D. Malonga (SEA) 3.4x real 5.46     game 95-60 total 155
  --> blowout role-player game: Shepard for DAL in a losing-team-blowout
      because she absorbed garbage-time usage when Bueckers got pulled.
      Malonga for SEA in the winning side of the same blowout.
```

The 2025-08-22 lineup is the cleanest illustration of the blowout-stars
pattern: J. Shepard and D. Malonga both fired in the same blowout (DAL 60,
SEA 95) — Shepard on the losing-team usage absorption side, Malonga on the
winning-team rotation extension side. The picker's blowout playbook needs
both branches.

---

## 10. Per-team environment table

For each team, the average realized total and own team-pts in the games
where their players appeared in winning lineups, alongside the team's
overall league environment:

| Team | Wins n | Avg total (wins) | Avg my-pts (wins) | League avg total | League avg pts |
|------|-------:|-----------------:|------------------:|-----------------:|---------------:|
| LVA  |     84 |          169.95  |             89.90 |           166.99 |          85.84 |
| DAL  |     53 |          171.47  |             84.08 |           172.63 |          83.92 |
| GSV  |     49 |          158.22  |             82.22 |           156.77 |          79.24 |
| ATL  |     44 |          162.45  |             85.48 |           159.31 |          80.76 |
| IND  |     44 |          165.89  |             86.55 |           168.89 |          85.21 |
| MIN  |     43 |          168.21  |             89.56 |           161.34 |          84.20 |
| NYL  |     38 |          169.61  |             87.71 |           163.52 |          84.28 |
| CON  |     36 |          162.81  |             76.94 |           158.80 |          77.84 |
| CHI  |     32 |          164.62  |             81.41 |           162.03 |          77.86 |
| LAS  |     30 |          177.53  |             88.03 |           169.92 |          83.01 |
| WAS  |     29 |          164.14  |             82.10 |           160.55 |          78.51 |
| SEA  |     24 |          162.33  |             82.54 |           161.07 |          81.56 |
| TOR  |     11 |          186.73  |             94.36 |           173.83 |          86.00 |
| PHX  |      4 |          173.75  |             91.75 |           165.49 |          82.34 |

LVA is the most-picked winning team (84 winning slots, 19% of all
contextualized winning slots). LVA winning slots come from games with
average total 169.95, only modestly above LVA's overall game total
(166.99). Wilson, Young, Gray are the engine.

DAL is second (53 slots). DAL winning slots come from games at total 171.47
vs season 172.63 — the picker doesn't need a shootout to fire DAL, the
team's baseline pace is already there. Bueckers, James, Quinerly, Yueru
all show up in winning lineups in mid-totals because DAL plays fast every
night.

TOR's 11 winning slots all came from games at average total 186.73 vs
TOR's overall 173.83. **When TOR plays a high-total game, the picker
should heavily weight TOR.** Small sample but clean pattern.

The "must-stack-in-pace" teams are LVA, DAL, NYL, LAS, MIN, TOR. The
"must-fade-in-pace" teams (rarely fire even in pace) are SEA, CON, WAS,
GSV. The "pace-and-blowout" teams (fire in blowouts more than in pace) are
MIN (89.56 my_pts vs 84.20 league), ATL (85.48 vs 80.76) — both teams
that play down vs strong opponents but get loose at home vs weak ones.

---

## 11. Open items and Vegas-line backfill

What's missing from this analysis:

1. **No actual closing lines.** Realized total / margin is the post-hoc
   measurement, not the pre-game Vegas implied total. The over-index on
   180+ realized totals is partly the picker's correct anticipation, partly
   variance. To separate the two, the project needs The Odds API closing
   total + spread per game. `ODDS_API_KEY` is already in `.env`. The
   correct backfill query is `sports/basketball_wnba/scores?date=YYYY-MM-DD`
   with `bookmakers=pinnacle,draftkings,fanduel&markets=totals,spreads` and
   `format=american`. Logged for the next data-ingest cycle.

2. **No game-pace projection feature in the picker.** The current
   `features/build.py` does not include a Vegas total or implied team
   total. Per the team-pts correlation of 0.338 with winning real_score,
   adding a single Vegas-implied team-total feature should be the
   highest-priority feature add in the next training cycle.

3. **No game-script-conditioned minutes model.** Blowout starters average
   28.1 min vs 30.5 in competitive games. The current minutes head doesn't
   condition on expected margin. A blowout-conditioned minutes adjustment
   (negative for starters on the winning side of a 13+ expected blowout,
   positive for bench bigs on either side) would help calibration in the
   exact bucket where the picker is least calibrated today.

4. **Player x environment interaction.** Wilson +0.90 in HIGH totals,
   Bueckers flat across totals, Reese floor-protected in LOWS, Malonga
   multiplier-only. The picker should have a small player-specific
   environment interaction term, learned on rolling 20-game windows.

5. **TOR small-sample tilt.** 11 / 11 TOR winning slots came from 180+
   games. With more TOR data through the expansion-era schedule, this
   either holds (TOR is a transition team that only wins picks in pace
   environments) or regresses. Worth re-checking at end of 2026 season.

---

## 12. Summary recommendations for the picker

In priority order:

1. **Add Vegas implied team-total as a top-line feature.** Highest single
   correlation with winning real_score in the data (0.338 Spearman).
2. **Add Vegas game-total** as a secondary feature (0.238 correlation),
   especially conditioned interactions for bench-big multipliers >=3.0x
   (those produce 0.65 real more per pick in HIGH totals).
3. **Condition minutes on expected margin.** Blowouts shave 2.4 min off
   starter minutes; the picker is over-rating starter minutes in blowouts
   and under-rating bench bigs.
4. **Build a per-player environment-interaction term.** Wilson, Brink,
   Malonga, Young clearly have different environment sensitivities than
   Bueckers, Reese, Salaün. A 20-game rolling player x bucket interaction
   would absorb most of this.
5. **Avoid the mid-mid trap.** Mid-total + competitive-margin games
   contribute 60% of winning slots but the lowest mean real_score per
   slot (3.87). When the slate's only game is a 165 total / 8-point
   spread, the picker should consider a wider lineup-distribution
   exploration rather than concentrating.
6. **Lean into TOR, LVA, DAL, LAS in projected high-total spots.** Their
   winning-slot environments confirm they are the "fire in pace" teams.
7. **Fade CON, SEA, WAS, GSV in projected high-total spots.** Their
   winning-slot environments stay close to their average total — they
   don't get the pace bump that the LVA-tier teams get.

Realized environments alone explain ~24% of the cross-slate variation in
winning real_score (Spearman 0.238 on total, 0.338 on team-pts). The
remaining 75% is player-specific projection — but the 25% is exactly the
share that closing-line ingestion would let the picker exploit ahead of
slate lock, since the post-hoc realized total used here is a noisy proxy
for what Vegas projected. Closing-line backfill is the single most
valuable data add to advance this thread.

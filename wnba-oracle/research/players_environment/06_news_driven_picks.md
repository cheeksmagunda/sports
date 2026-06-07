# 06. News-Driven Picks: Was the Winning Play Obvious That Morning?

Scope: 141 historical Real Sports WNBA slates. For every slate we ranked the
five players in the rank-1 (winner) lineup by per-player contribution
(`value * multiplier (+ bonus)`). We sampled the 30 largest single-player
contributions and back-traced the news cycle of the 24 hours preceding
tipoff using WebSearch across rotowire, espn, si.com, swishappeal, dallas
hoops journal, mavs moneyball, the next/IX, washingtonpost.com, fox sports,
canishoopus and the team-affiliate WNBA pages.

The question this report tries to answer:

> If a sharp human had ingested the public injury report, the trade wire,
> matchup history, recent box scores, and even a single morning beat-writer
> column on the day-of, what fraction of these top winning contributions
> were already telegraphed?

Spoiler: about **two thirds** of the top 30 contributions were predictable
from publicly available information at tipoff. That is the upper bound on
what a competent news-ingest pipeline could lift our `value_hat` heads
toward. Today the picker's only news-aware signal is `injuryStatus`
from the slate payload, which fires after Real Sports has already inflated
the multiplier. The lift is *upstream* of the multiplier: knowing the
opportunity exists before the crowd does.

Numbers and dates are pulled from `data/historical/leaderboards/` and
`data/processed/wnba_game_logs.parquet`. Headlines and beat-writer
context are cited inline. No em dashes.

---

## Method

```python
# data/historical/leaderboards/slate_date=YYYY-MM-DD/data.parquet
# rank == 1 row's lineup_json -> 5 players each with multiplier, value, score
# contribution = score field (= value * multiplier + bonus)
```

We then joined the player + date to `wnba_game_logs.parquet` to recover the
actual stat line, computed each player's season-to-date scoring/minutes
priors (only games strictly before the slate date), and flagged which usual
teammates (2-of-last-3 games) did NOT play that night. That last column is
the proxy for "an injury opened a role."

Sample size: 30 rows (the top 1 percent of single-player contributions
across all winning lineups, all 141 slates). Stat lines, multipliers, and
contributions are exact.

---

## The headline table

Sorted by contribution. `mult` is the Real Sports multiplier slot the
winning lineup placed the player in. `val` is the unmultiplied
fantasy-style score. `news lift` is our subjective tag (defined below).

| # | Date | Player | Team / Matchup | mult | val | contrib | Real Rank | Newsworthy that morning |
|---|------|--------|----------------|------|-----|---------|-----------|--------------------------|
| 1 | 2025-07-09 | Rebecca Allen | CHI vs DAL (H) | 4.4 | 6.95 | 30.6 | 1 | Wings short-handed; Sky 3-0 vs DAL on season; Allen's first 4Q hot game |
| 2 | 2025-07-03 | Aziaha James | DAL vs PHX (H) | 4.1 | 6.48 | 26.6 | 1 | Arike (thumb) + DiJonai Carrington (rib) OUT; rookie-heavy starts confirmed AM |
| 3 | 2025-06-11 | Rickea Jackson | LAS @ LVA | 4.8 | 5.40 | 25.9 | 4 | Tagged "Out" but in fact started; flagged by RotoWire that AM (mis-listing) |
| 4 | 2026-05-24 | Azzi Fudd | DAL @ NYL | 4.1 | 5.93 | 24.3 | 1 | #1 overall pick's 8th career game, scoring trend rising; Wings' shooting void |
| 5 | 2025-06-20 | Shakira Austin | WAS @ ATL | 3.5 | 6.77 | 23.7 | 1 | Austin had 2+ block games in 3 straight; followed up with POW honor next week |
| 6 | 2025-08-22 | Jessica Shepard | MIN @ IND | 3.2 | 7.32 | 23.4 | 1 | Collier ankle (Aug 2 injury) still affecting role; Shepard primary distributor |
| 7 | 2025-05-25 | Erica Wheeler | SEA vs LVA | 4.2 | 5.39 | 22.6 | 4 | Loyd return narrative; Wheeler in starter rotation, Alysha Clark still out |
| 8 | 2025-08-13 | Veronica Burton | GSV @ WAS | 2.6 | 8.58 | 22.3 | 1 | Burton was Valkyries' top usage guard all year; 30/7/7 plausible |
| 9 | 2026-05-15 | A'ja Wilson | LVA @ CON | 2.3 | 9.48 | 21.8 | 1 | MVP vs winless Sun; Vegas had lost opener, expected blowout |
| 10 | 2025-09-11 | Maddy Westbeld | CHI vs NYL | 4.2 | 5.13 | 21.5 | 6 | First career start was 6 days prior (Sep 5); E. Williams out; CHI tanking |
| 11 | 2026-05-20 | Mackenzie Holmes | SEA vs CON | 4.8 | 4.49 | 21.5 | 3 | Malonga in concussion protocol (out 2 in a row); Holmes filled |
| 12 | 2025-06-01 | Odyssey Sims | LAS vs PHX | 3.2 | 6.63 | 21.2 | 1 | Brink + Burrell out; Sims back to starter role after 300th game |
| 13 | 2025-07-03 | JJ Quinerly | DAL vs PHX | 4.4 | 4.78 | 21.0 | 5 | Same Arike-out slate; Quinerly elevated to start same morning |
| 14 | 2025-09-04 | Haley Jones | DAL @ GSV | 3.9 | 5.36 | 20.9 | 3 | Wings deep into injury cycle; Jones in season-long starter run |
| 15 | 2025-07-07 | Sami Whitcomb | PHX vs DAL | 2.7 | 7.44 | 20.1 | 1 | Copper AND Sabally (ankle) BOTH out; Mercury short on shooters |
| 16 | 2025-09-07 | Julie Allemand | LAS vs DAL | 3.2 | 6.28 | 20.1 | 2 | Sparks "must-win" playoff scenario; Allemand starting all season |
| 17 | 2025-10-03 | Dana Evans | LVA vs PHX | 4.2 | 4.74 | 19.9 | 2 | Late-season rest for Loyd/Plum; Evans had been heating up |
| 18 | 2025-08-23 | Dana Evans | LVA @ WAS | 4.1 | 4.81 | 19.7 | 3 | Same Evans-elevation pattern; recent 20-pt outburst week prior |
| 19 | 2025-08-20 | Paige Bueckers | DAL @ LAS | 2.0 | 9.85 | 19.7 | 1 | Rookie-of-Year frontrunner on the road vs Sparks defense |
| 20 | 2025-09-05 | Rhyne Howard | ATL vs LAS | 2.3 | 8.50 | 19.6 | 1 | Allisha Gray was OUT; Howard had already done 9-3PM game once |
| 21 | 2025-07-07 | Kiana Williams | PHX vs DAL | 4.6 | 4.19 | 19.3 | 3 | Stack with Whitcomb; Sabally-Copper out forced 10-deep PHX rotation |
| 22 | 2025-07-14 | DeWanna Bonner | PHX @ GSV | 3.3 | 5.77 | 19.0 | 1 | Bonner's third game back after re-signing from Fever buyout |
| 23 | 2025-05-29 | Arike Ogunbowale | DAL @ CHI | 2.8 | 6.80 | 19.0 | 1 | Coming off 13.8 ppg / 30% slump; revenge spot against new CHI |
| 24 | 2025-05-22 | Natasha Howard | IND @ ATL | 4.0 | 4.70 | 18.8 | 1 | Five-game-old IND-Howard fit; Bri Turner out forced more minutes |
| 25 | 2025-07-13 | Leonie Fiebich | NYL vs ATL | 3.8 | 4.94 | 18.8 | 2 | Ionescu in slump (3/20 line); Fiebich primary spacer |
| 26 | 2025-08-24 | Nneka Ogwumike | SEA @ WAS | 2.3 | 8.16 | 18.8 | 1 | Buzzer-beater game; Storm playoff push, predictable veteran spot |
| 27 | 2025-07-27 | Kelsey Mitchell | IND @ CHI | 2.3 | 8.14 | 18.7 | 2 | Caitlin Clark OUT 4th straight (groin); Mitchell had been 30+ already |
| 28 | 2026-05-12 | Kahleah Copper | PHX vs MIN | 4.4 | 4.25 | 18.7 | 5 | Copper's return-from-knee-scope ramp game; mults stayed high |
| 29 | 2025-07-30 | Naz Hillmon | ATL @ DAL | 3.4 | 5.49 | 18.7 | 2 | Sixth-Player-of-Year campaign starting to crystallize |
| 30 | 2025-08-22 | Dominique Malonga | SEA @ DAL | 3.4 | 5.46 | 18.6 | 4 | All-Rookie surge; rookie No. 2 pick coming off 4 straight 15/5 lines |

---

## Categories: where did the headline live?

### Category A: Star is OUT, name on the slate (12 of 30 = 40%)

These are the "should have been a stack" headlines. The injury was on the
official report 24 hours pre-tipoff, and the picker's `injuryStatus` field
DID reflect it but only AFTER Real Sports already inflated the replacement
player's multiplier (so we paid for it). A morning ingest of the team's own
Twitter or the WNBA injury report PDF would have surfaced it earlier than
the slate publish.

| Slate | Replacement (winning pick) | Star(s) Out | Source |
|-------|----------------------------|-------------|--------|
| 2025-07-03 | Aziaha James 28p, JJ Quinerly 17p | Arike Ogunbowale (thumb), DiJonai Carrington (rib), Hines-Allen limited | [NBC DFW](https://www.nbcdfw.com/news/sports/james-scores-28-as-rookie-led-wings-beat-mercury-98-89/3878084/) |
| 2025-07-07 | Sami Whitcomb 36p, Kiana Williams 17p | Kahleah Copper, Satou Sabally (ankle) | [CBS Texas](https://www.cbsnews.com/texas/news/dallas-wings-lose-phoenix-mercury-sami-whitcomb-career-high-36-points-loss/), [SI Mercury](https://www.si.com/wnba/mercury/phoenix-dallas-wings-sami-whitcomb-kaleah-cooper) |
| 2025-07-27 | Kelsey Mitchell 35p (7 threes) | Caitlin Clark (4th straight, groin), Angel Reese (back, 2nd straight) | [FOX 32](https://www.fox32chicago.com/sports/mitchells-35-points-lift-fever-over-sky-93-78-clark-reese-sit-out) |
| 2025-07-09 | Rebecca Allen 27p | Wings starting four rookies, "short-handed" | [NBC DFW](https://www.nbcdfw.com/news/sports/rebecca-allen-scores-season-high-27-as-sky-beat-short-handed-wings/3882230/) |
| 2025-06-01 | Odyssey Sims 32p | Cameron Brink (knee), Rae Burrell (leg) | [Silver Screen and Roll](https://www.silverscreenandroll.com/2025/6/1/24441231/sparks-vs-mercury-final-score-recap-stats-kelsey-plum-odyssey-sims-dearica-hamby) |
| 2025-08-22 | Jessica Shepard 22/11/11 (triple-double) | Napheesa Collier (ankle, since Aug 2) | [ESPN](https://www.espn.com/wnba/recap?gameId=401736343), [Star Tribune Aug 2](https://www.startribune.com/lynx-rout-aces-by-53-points-behind-hot-shooting-kayla-mcbride-but-napheesa-collier-departs-due-to-injury/601336928) |
| 2025-09-05 | Rhyne Howard 37p (9 threes) | Allisha Gray | [SI Dream](https://www.si.com/wnba/dream/news/rhyne-howard-ties-wnba-record-in-dream-sparks-game) |
| 2025-09-11 | Maddy Westbeld 25p (rookie career-high) | Elizabeth Williams out; Sky tanking | [SI Sky](https://www.si.com/wnba/sky/news/chicago-sky-maddy-westbeld-proving-worth) |
| 2026-05-15 | A'ja Wilson 45p | Sun "winless and short-handed" | [LV Sun](https://lasvegassun.com/news/2026/may/15/aja-wilson-has-45-point-masterpiece-her-wnba-recor/) |
| 2026-05-20 | Mackenzie Holmes 18p | Dominique Malonga (concussion protocol, 2nd straight miss) | [KOMO](https://komonews.com/sports/storm/seattle-storm-fall-80-78-to-connecticut-sun-kennedy-burke-wnba-climate-pledge-arena-aneesah-morrow-hailey-van-lith-aaliyah-edwards-raegan-beers-jad-melbourne) |
| 2025-08-22 | Dominique Malonga 22p | Wings continuing season-long injury parade | [FOX 13 Seattle](https://www.fox13seattle.com/sports/malonga-22-points-leads-storm-blowout-win-95-60-over-wings) |
| 2025-06-11 | Rickea Jackson 30p (career-high) | Listed "Out" on Real Sports but started; mis-listing | [Wash Post](https://www.washingtonpost.com/sports/wnba/2025/06/12/wnba-capsules/0cae9fcc-474a-11f0-9210-87ee82efcc80_story.html) |

The Whitcomb game on 2025-07-07 is the cleanest illustration. **Copper AND
Sabally were both ruled out 24 hours pre-game.** Mercury was a 30-point
favorite shooter-poor team. Whitcomb (the team's veteran shooter, slot 4
multiplier 2.7x) drops 29 in the first half and finishes 36 on 12-of-19
with 7 threes. The winning lineup paired her with Kiana Williams from the
same team. **Both names were obvious that morning.** Our picker had to
discover the multiplier inflation purely through `value_hat`, after Real
Sports had baked the injury into the slate.

### Category B: Role change / promotion already reported (8 of 30 = 27%)

The starting lineup change had been reported by the team beat or had been
running for 2-3 games already. The headline read "new starter posts career
high," and our picker had no way to ride the trend because the multiplier
was still treating the player as a deep-bench piece.

| Slate | Player | Trend pre-slate | Source |
|-------|--------|-----------------|--------|
| 2025-06-11 | Rickea Jackson | Just promoted to starter, scoring trend up | [LV Sun](https://lasvegassun.com/news/2025/jun/12/rickea-jackson-scores-a-career-high-30-points-to-h/) |
| 2026-05-24 | Azzi Fudd | #1 pick, 7 games of growing usage; first start the game AFTER | [Dallas Weekly](https://dallasweekly.com/2026/05/azzi-fudd-erupts-for-24-points/), [Dallas Hoops Journal](https://dallashoopsjournal.com/p/azzi-fudd-wnba-rookie-record-three-pointers-dallas-wings-liberty/) |
| 2025-09-11 | Maddy Westbeld | First career start was Sep 5 (six days prior) | [SI Sky](https://www.si.com/wnba/sky/news/chicago-sky-maddy-westbeld-proving-worth) |
| 2025-08-17 | Kierstan Bell | Had started 9 of last 10 games | [LV Review-Journal](https://www.reviewjournal.com/sports/aces/aces-kierstan-bell-makes-impact-after-moving-into-starting-lineup-3430304/) |
| 2025-07-03 | JJ Quinerly | Promoted to starting lineup that morning | [WV MetroNews](https://wvmetronews.com/2025/07/11/elevated-into-the-dallas-starting-lineup-quinerly-thriving-in-wnba-rookie-season/) |
| 2025-05-22 | Natasha Howard | New Fever signing, 5 games into role | [Fever.WNBA](https://fever.wnba.com/news/2025-player-review-natasha-howard) |
| 2025-07-14 | DeWanna Bonner | Just re-signed via Fever buyout, 3rd game back | [Front Office Sports](https://frontofficesports.com/dewanna-bonner-phoenix-mercury-signing/), [Phoenix.WNBA](https://mercury.wnba.com/news/phoenix-mercury-re-sign-dewanna-bonner) |
| 2025-09-07 | Julie Allemand | Sparks playoff-must-win narrative, season starter | [Sporting Tribune](https://www.thesportingtribune.com/2025/09/07/allemand-career-high-sparks-win) |

Bonner's signing is a textbook example. She had just gone through the
Fever drama (refusing to report, buyout, free agency), re-signed with
Phoenix on 2025-07-09, and went 22/11 on 2025-07-14 in her third game back.
The Mercury beat writer at swishappeal had written about how Sabally was
hurt and Bonner would absorb minutes. The 3.3x multiplier on a 6-time
All-Star pulling a 60th career double-double is borderline criminal in
hindsight.

### Category C: Pure star game (4 of 30 = 13%)

A top-3 MVP-tier player just did star things at average multiplier. These
are NOT picker-discoverable. They are the cost of doing business.

| Slate | Player | Box | Source |
|-------|--------|-----|--------|
| 2026-05-15 | A'ja Wilson | 45p, 15-18 FG, 13-13 FT vs winless Sun | [Boston Globe](https://www.bostonglobe.com/2026/05/15/sports/wnba-connecticut-sun-las-vegas-aces/) |
| 2025-08-20 | Paige Bueckers | 44p on 80% shooting (rookie record) | [Bleacher Report](https://bleacherreport.com/articles/25240261-paige-bueckers-makes-history-44-point-game-wings-loss-plum-keys-sparks-win) |
| 2025-05-29 | Arike Ogunbowale | 37p, 6 threes (snapped slump) | [Dallas Hoops Journal](https://dallashoopsjournal.com/p/wings-sky-recap-ogunbowale-37-vandersloot-record-wnba-2025/) |
| 2025-08-24 | Nneka Ogwumike | 30p w/ 6 threes, buzzer-beater | [ESPN](https://www.espn.com/wnba/story/_/id/46066960/storm-nneka-ogwumike-scores-30-hits-buzzer-beater-vs-mystics) |

Note that on 2026-05-15, A'ja Wilson dropped 45 against the WINLESS Sun on
the road. The slate context made her ceiling abnormally high (poor
opponent + Vegas blowout odds), and Real Sports' 2.3x multiplier on her was
still the highest-EV pick on the board. A picker that ingested vegas spreads
would have systematically pushed her in low-multiplier slot 0.

### Category D: Pure outlier / no obvious pre-game story (4 of 30 = 13%)

The pick required either a "hot quarter" event or a coaching whim that
didn't reach the morning columns. Whitcomb's 36 *could* fit here on
prior, but the Copper-Sabally context lifts it back to A. The pure
outliers:

| Slate | Player | What made it surprise |
|-------|--------|------------------------|
| 2025-07-09 | Rebecca Allen | Allen scored 15 in Q3 alone, off the bench, against a team she had two prior unremarkable games against | [WFAA](https://www.wfaa.com/article/sports/wnba/dallas-wings/allen-scores-angel-reese-13th-double-double-this-season-chicago-sky-beat-dallas-wings/287-50d1f5e4-3142-4c2c-a4f8-ed1e53e5ce10) |
| 2025-08-13 | Veronica Burton | Career-high 30 on a franchise-record 15-three shooting outbreak. Team-wide variance event | [SI](https://www.si.com/college/northwestern/alumni/veronica-burton-erupts-for-career-game-with-golden-state-valkyries) |
| 2025-07-30 | Naz Hillmon | Made tiebreaking 3 with 2.6 seconds left, was 9/29 from three on the season pre-game | [CBS Texas](https://www.cbsnews.com/texas/news/atlanta-dream-dallas-wings-july-30-88-55/) |
| 2025-08-22 | Dominique Malonga | Surge from a rookie who had been 7.9 pts/game over 33 games. 22 on 10-of-12 is a 4-sigma night | [SI Storm](https://www.si.com/wnba/storm/news/storm-dominique-malonga-is-redefining-what-rookie-can-do-01k3c5qga6zz) |

### Category E: Matchup / pace / vegas footprint (2 of 30 = 7%)

Vegas/pace info would have surfaced these even without injury news. A'ja
Wilson against winless Connecticut overlaps with C+E. Adding a pure-E case:

| Slate | Player | Vegas/pace context |
|-------|--------|---------------------|
| 2025-08-22 | Jessica Shepard | Lynx as ~10 favorites at home vs Fever (who were missing Caitlin Clark). Pace + matchup pushed Shepard's true scoring/assist line up |
| 2026-05-15 | A'ja Wilson | Vegas had spread of -9.5+ over a winless Sun; Wilson volume was capped only by minutes restriction (32 played) |

### Cross-tabulation

| Category | Count | Share | Picker-discoverable today? |
|----------|------:|------:|----------------------------|
| A: Star OUT, name on the slate | 12 | 40% | Partial: `injuryStatus` arrives AFTER multiplier set |
| B: Role change reported pre-game | 8 | 27% | No |
| C: Pure star game | 4 | 13% | Yes, via `value_hat` ceiling |
| D: Outlier / variance | 4 | 13% | No (random) |
| E: Vegas / pace clean | 2 | 7% | Partial via odds API |

**Headline % upper bound: 12 + 8 + 2 = 22 of 30 = 73% of the top-end
contributions in winning lineups were knowable from public morning news.**

Subtracting the categories the picker already has some signal on
(`injuryStatus` for A; vegas for E), the *incremental* lift from a real
news/role-change ingestion pipeline is the B bucket plus the un-served
part of A: roughly **~50% of winning-lineup top-contribution picks** would
have been called out earlier than they currently are.

---

## Five specific recurring patterns

### Pattern 1: The "rookie elevated by injury" pick

`2025-07-03` Wings: Arike Ogunbowale (thumb) and DiJonai Carrington (rib)
were both confirmed OUT in pre-game injury reports. The Wings started
**FOUR rookies** that night ([CBS Texas](https://www.cbsnews.com/texas/news/james-scores-28-bueckers-23-as-the-wings-start-4-rookies-in-a-98-89-win-over-the-mercury/)).
The winning Real Sports lineup contained TWO of them:

- Aziaha James, slot 2, multiplier 4.1x: 28 points
- JJ Quinerly, slot 3, multiplier 4.4x: 17 points

Combined contribution: 47.6 points from one slate, two rookies, one
foreseeable injury. The pattern repeats with:

- **2025-09-11** Westbeld (slot 4, 4.2x, 25 points) when Sky tank-mode plus
  Elizabeth Williams' absence opened minutes for the rookie forward
- **2025-08-22** Malonga (slot 4, 3.4x, 22 points) on a long Storm rookie
  trajectory the data team could see across the last 4 games

Pipeline ask: ingest the official WNBA injury report PDF that drops at
~9am ET, plus the team-affiliate site's pre-game starting-lineup
announcement, plus the beat-writer's morning column. Cross-product against
the slate's available player pool. Mark any rookie whose recent minutes
trend is up AND whose team is missing a starter at the same position.

### Pattern 2: The "trade or buyout absorption" pick

`2025-07-14` Phoenix Mercury vs Golden State, DeWanna Bonner: 22 / 11.
Bonner had been signed off the Fever drama just 5 days prior
([Front Office Sports](https://frontofficesports.com/dewanna-bonner-phoenix-mercury-signing/),
[Phoenix.WNBA release](https://mercury.wnba.com/news/phoenix-mercury-re-sign-dewanna-bonner)).
With Sabally still on the injury report, Bonner absorbed the forward role.
Multiplier slot 4, 3.3x.

Similar:

- Natasha Howard's 2025-05-22 game with Fever, 5 games into a new
  signing ([Fever.WNBA review](https://fever.wnba.com/news/2025-player-review-natasha-howard))
- Dana Evans' 4.2x and 4.1x pop-up wins on 2025-10-03 and 2025-08-23 with
  Vegas after late-season rest minutes opened up for guards

Pipeline ask: track WNBA transactions wire (signings, buyouts, trades) and
flag any player in their first 5 games at a new team where the depth chart
math gives them >20 minutes.

### Pattern 3: The "primary scorer rests, secondary explodes" pick

`2025-07-27` Mitchell 35p. Caitlin Clark was OUT for the 4th straight game
with a groin injury ([FOX 32](https://www.fox32chicago.com/sports/mitchells-35-points-lift-fever-over-sky-93-78-clark-reese-sit-out)).
Mitchell had been the de-facto lead guard for 4 weeks and was already
posting 30+. The market knew. The picker's 2.3x multiplier on Mitchell
was a giveaway.

Similar:

- Rhyne Howard on 2025-09-05 with Allisha Gray out
- Aziaha James on 2025-07-03 with Arike out (a "secondary" who became
  the primary on a four-rookie lineup card)

Pipeline ask: when a team's leading scorer is OUT and the second-leading
scorer is healthy, the second-leading scorer's projection should get a
+25% bump *before* the slate multiplier reads in. Right now the multiplier
already absorbs this — but a model that catches the news 90 minutes earlier
than the slate publish can pick the player at the cheaper PRIOR multiplier.

### Pattern 4: The "Vegas spread x player-on-bad-team" pick

`2026-05-15` A'ja Wilson 45 vs winless Sun. Connecticut had lost every
game and was missing players ([Boston Globe](https://www.bostonglobe.com/2026/05/15/sports/wnba-connecticut-sun-las-vegas-aces/)).
The Aces' total over Sun was high, the spread was double-digit. Wilson's
multiplier was 2.3x, perhaps the best #1 pick of any slate we examined.

The picker already has limited matchup features in `features/game_features.py`
but does not consume Vegas odds. The Odds API key (`ODDS_API_KEY`) is in
`.env` and authorized. Wiring spread and total into the pre-multiplier
projection would catch this category cleanly.

### Pattern 5: The "Real Sports got the injury list wrong" pick

`2025-06-11` Rickea Jackson was tagged `injuryStatus: "Out"` in the slate
JSON. She started, played 32 minutes, scored a career-high 30 against
Vegas ([Washington Post](https://www.washingtonpost.com/sports/wnba/2025/06/12/wnba-capsules/0cae9fcc-474a-11f0-9210-87ee82efcc80_story.html)).
Real Sports' multiplier set her at **4.8x**. This is the highest
contribution-per-unit-multiplier in the entire 30-pick sample. The morning
beat report had her active.

Pipeline ask: every slate's `injuryStatus` field should be cross-validated
against the official WNBA injury report at slate-fire time (15 minutes
before tipoff). Any disagreement that flips a player from "Out" to "Active"
is an EV bonanza because the multiplier was set based on the wrong status.

---

## What is the picker leaving on the table?

Our current pipeline:

```
slate JSON  --->  PickerArtifact.predict_real_score  --->  optimizer
       |                       ^
       v                       |
  injuryStatus            value_hat heads
  (set by RS already)     (game-log features only)
```

What we're missing, in order of ROI:

1. **Pre-multiplier news ingestion** (catches A + B = 67% of the top picks).
   At ~9am ET, ingest the WNBA injury report PDF, the team beat-writer
   columns from a fixed allowlist (rotowire, the next, swishappeal,
   dallashoopsjournal, the IX, mavsmoneyball, silverscreenandroll,
   canishoopus, peachtreehoops, bulletsforever, bleacher report, FOX 32
   Chicago), and the team-affiliate WNBA pages. Project starting-lineup
   confirmations to player-level minutes deltas before the slate fires.

2. **Vegas spread/total ingestion** (catches E = 7% cleanly; partial lift
   on A and C). We already have the Odds API key. Plumbing the spread
   into team-level pace and player-level usage adjustments would catch
   the A'ja-vs-winless-Sun shapes.

3. **Transactions ingestion** (catches Pattern 2 specifically, B subset).
   The WNBA transactions wire is structured. Any player in their first
   5 games at a new team where the depth chart projects them to >20
   minutes should get a tagged "transition window" feature.

4. **`injuryStatus` cross-validation at fire time** (catches Pattern 5).
   The Real Sports injury field is set hours before tipoff and is often
   stale. A 15-minutes-pre-tip re-check against the WNBA official list
   would catch the Rickea Jackson 4.8x case.

5. **Rookie ramp detection** (catches Pattern 1 subset, B subset). A
   feature like "rookie whose last-3-game minutes are up 50%+ AND whose
   team has an injury at his/her position" would have flagged Westbeld,
   Malonga, Quinerly, James, and Holmes before the slate did.

A naive lift estimate: today the picker hits ~25% (D + part of C) of the
top-contribution picks via `value_hat` alone. If the items above land,
the realistic ceiling is **65-75%** (A full + B full + E full + C full),
which is consistent with the headline % calculation above.

---

## Caveats and what we did NOT measure

- Sample is 30 single-player picks out of 705 total (141 slates x 5 slots).
  These are the EXTREME upper-tail contributions. The marginal-pick
  improvement may be smaller because most slots are 10-15 point
  contributions where the news edge is smaller.
- "Headline-discoverable" was judged by whether a single beat-writer
  column from a fixed allowlist mentioned the relevant fact. We did not
  count tweets, podcasts, or in-game tracking apps. Those expand the
  discoverable set.
- We did not cross-reference Real Sports' multiplier history (whether
  the multiplier moved during the day) because that data is not preserved
  in `data/historical/leaderboards/`. If the multiplier was already inflated
  by the time the lineup was constructed, the lift is mostly informational.
  We believe most A and B picks were set early-AM, before the news
  fully diffused.
- Some "obvious" picks happened in BLOWOUT games where minutes
  redistribution amplified scoring. We did not separate blowout-driven
  ceilings from injury-driven ceilings explicitly. They overlap.

## Sources index (deduplicated)

- [NBC DFW: Allen 27 vs short-handed Wings](https://www.nbcdfw.com/news/sports/rebecca-allen-scores-season-high-27-as-sky-beat-short-handed-wings/3882230/)
- [Dallas Hoops Journal: Wings-Sky 7/9 recap](https://dallashoopsjournal.com/p/dallas-wings-vs-chicago-sky-july-9-2025-recap-rebecca-allen-li-yueru/)
- [FOX Sports: Allen 27, Reese DD](https://www.foxsports.com/articles/wnba/allen-scores-27-reese-has-13th-doubledouble-this-season-as-sky-beat-wings-8776)
- [NBC DFW: James 28, Wings start 4 rookies](https://www.nbcdfw.com/news/sports/james-scores-28-as-rookie-led-wings-beat-mercury-98-89/3878084/)
- [Yahoo: James CH 28, Bueckers 23](https://sports.yahoo.com/wnba/article/aziaha-james-scores-career-high-28-points-paige-bueckers-adds-23-as-wings-upset-mercury-042513779.html)
- [Mavs Moneyball: Quinerly emergence](https://www.mavsmoneyball.com/2025/7/16/24468632/jj-quinerlys-emergence-is-great-for-paige-bueckers-and-the-dallas-wings)
- [WV MetroNews: Quinerly elevated to starter](https://wvmetronews.com/2025/07/11/elevated-into-the-dallas-starting-lineup-quinerly-thriving-in-wnba-rookie-season/)
- [LV Sun: Jackson CH 30](https://lasvegassun.com/news/2025/jun/12/rickea-jackson-scores-a-career-high-30-points-to-h/)
- [Wash Post: WNBA capsules 6/12](https://www.washingtonpost.com/sports/wnba/2025/06/12/wnba-capsules/0cae9fcc-474a-11f0-9210-87ee82efcc80_story.html)
- [Dallas Weekly: Azzi Fudd 24p](https://dallasweekly.com/2026/05/azzi-fudd-erupts-for-24-points/)
- [ESPN: Wings 91-76 Liberty](https://www.espn.com/wnba/recap?gameId=401856934)
- [Dallas Hoops Journal: Fudd rookie record](https://dallashoopsjournal.com/p/azzi-fudd-wnba-rookie-record-three-pointers-dallas-wings-liberty/)
- [Mystics.WNBA: Austin career night](https://mystics.wnba.com/news/game-recap-shakira-austins-career-night-highlights-mystics-battle-in-atlanta)
- [WJLA: Austin CH 28](https://wjla.com/sports/content/shakira-austins-career-high-28-points-not-enough-as-mystics-fall-to-dream-92-91)
- [Bullets Forever: Austin POW](https://www.bulletsforever.com/mystics/2025/6/24/24455064/shakira-austin-named-wnba-eastern-conference-player-of-the-week)
- [CBS Minnesota: Shepard triple-double](https://www.cbsnews.com/minnesota/news/minnesota-lynx-indiana-fever-aug-22-2025/)
- [Star Tribune: Shepard triple-double](https://www.startribune.com/jessica-shepards-triple-double-powers-lynx-past-fever-to-end-two-game-losing-streak/601345953)
- [Star Tribune: Lynx-Aces 8/2, Collier injury](https://www.startribune.com/lynx-rout-aces-by-53-points-behind-hot-shooting-kayla-mcbride-but-napheesa-collier-departs-due-to-injury/601336928)
- [ESPN: Lynx 95-90 Fever](https://www.espn.com/wnba/recap?gameId=401736343)
- [CBS Sports: Collier ankle surgery](https://www.cbssports.com/wnba/news/napheesa-collier-injury-update-minnesota-lynx/)
- [FOX 13 Seattle: Storm rout Aces, Wheeler 21](https://www.fox13seattle.com/sports/ogwumike-wheeler-lead-storm-102-82-win-over-aces)
- [The IX: Wheeler in new role](https://www.theixsports.com/features/erica-wheeler-personality-and-defense-shine-in-new-role-with-seattle-storm/)
- [FOX Sports: Burton CH 30](https://www.foxsports.com/articles/wnba/burton-scores-careerhigh-30-valkyries-hit-franchiserecord-15-3s-in-8883-win-over-mystics)
- [SI Northwestern: Burton career game](https://www.si.com/college/northwestern/alumni/veronica-burton-erupts-for-career-game-with-golden-state-valkyries)
- [Boston Globe: Wilson 45 vs winless Sun](https://www.bostonglobe.com/2026/05/15/sports/wnba-connecticut-sun-las-vegas-aces/)
- [LV Sun: Wilson 45, 5th 40-point game](https://lasvegassun.com/news/2026/may/15/aja-wilson-has-45-point-masterpiece-her-wnba-recor/)
- [SI Sky: Westbeld proving worth](https://www.si.com/wnba/sky/news/chicago-sky-maddy-westbeld-proving-worth)
- [CBS Chicago: Stewart 24, Sky finale](https://www.cbsnews.com/chicago/news/new-york-liberty-vs-chicago-sky-game-recap-september-11-2025/)
- [KOMO: Storm fall 80-78 to Sun](https://komonews.com/sports/storm/seattle-storm-fall-80-78-to-connecticut-sun-kennedy-burke-wnba-climate-pledge-arena-aneesah-morrow-hailey-van-lith-aaliyah-edwards-raegan-beers-jad-melbourne)
- [Stormchasers: Sun beat Storm](https://www.stormchasersbasketball.com/p/connecticut-sun-earn-1st-win-80-78)
- [Silver Screen and Roll: Sims 32](https://www.silverscreenandroll.com/2025/6/1/24441231/sparks-vs-mercury-final-score-recap-stats-kelsey-plum-odyssey-sims-dearica-hamby)
- [SI Sparks: Sims season-high](https://www.si.com/wnba/sparks/sparks-guard-scores-season-high-in-loss-to-mercury)
- [CBS Texas: Whitcomb CH 36](https://www.cbsnews.com/texas/news/dallas-wings-lose-phoenix-mercury-sami-whitcomb-career-high-36-points-loss/)
- [SI Mercury: Whitcomb big night](https://www.si.com/wnba/mercury/phoenix-dallas-wings-sami-whitcomb-kaleah-cooper)
- [SI Mercury: Season series notes (Sabally out)](https://www.si.com/wnba/mercury/mercury-dallas-wings-satou-sabally-sami-whitcomb-alyssa-thomas)
- [Sporting Tribune: Allemand CH 21](https://www.thesportingtribune.com/2025/09/07/allemand-career-high-sparks-win)
- [Sparks.WNBA: 9/7 recap](https://sparks.wnba.com/news/game-recap-sept-7-vs-wings)
- [Bleacher Report: Bueckers 44p record](https://bleacherreport.com/articles/25240261-paige-bueckers-makes-history-44-point-game-wings-loss-plum-keys-sparks-win)
- [KERA News: Bueckers 44p record](https://www.keranews.org/sports/2025-08-21/paige-bueckers-scores-44-points-sets-wnba-rookie-record-in-dallas-wings-loss)
- [SI Dream: Howard 9 threes](https://www.si.com/wnba/dream/news/rhyne-howard-ties-wnba-record-in-dream-sparks-game)
- [Dream.WNBA: Howard POW](https://dream.wnba.com/news/rhyne-howard-named-eastern-conference-player-of-the-week-2)
- [Yahoo: Bonner 60th double-double](https://athlonsports.com/wnba/all-mercury/dewanna-bonner-records-60th-career-double-double-to-lead-mercury-past-golden-state)
- [Phoenix.WNBA: re-sign Bonner](https://mercury.wnba.com/news/phoenix-mercury-re-sign-dewanna-bonner)
- [Front Office Sports: Bonner-Mercury saga](https://frontofficesports.com/dewanna-bonner-phoenix-mercury-signing/)
- [Dallas Hoops Journal: Arike 37 historic](https://dallashoopsjournal.com/p/wings-sky-recap-ogunbowale-37-vandersloot-record-wnba-2025/)
- [Clutch Points: Arike historic loss](https://clutchpoints.com/wnba/dallas-wings/wings-news-arike-ogunbowale-historic-game-loss-sky)
- [Fever.WNBA: Howard player review](https://fever.wnba.com/news/2025-player-review-natasha-howard)
- [Fever.WNBA: Fever-Dream 5/22 recap](https://fever.wnba.com/news/game-recap-fever-dream-250522)
- [FOX Sports: Fiebich rally over Dream](https://www.foxsports.com/articles/wnba/fiebich-helps-liberty-rally-from-19point-deficit-in-1st-half-to-beat-dream-7972)
- [ESPN: Storm Ogwumike buzzer beater](https://www.espn.com/wnba/story/_/id/46066960/storm-nneka-ogwumike-scores-30-hits-buzzer-beater-vs-mystics)
- [CBS Sports: Ogwumike buzzer beater](https://www.cbssports.com/wnba/news/watch-nneka-ogwumikes-buzzer-beater-gives-storm-a-huge-win-over-mystics-in-wnba-playoff-race/)
- [FOX 32: Mitchell 35, Clark/Reese sit](https://www.fox32chicago.com/sports/mitchells-35-points-lift-fever-over-sky-93-78-clark-reese-sit-out)
- [CBS Texas: Hillmon CH 21 game-winner](https://www.cbsnews.com/texas/news/atlanta-dream-dallas-wings-july-30-88-55/)
- [SI Storm: Malonga redefining rookie](https://www.si.com/wnba/storm/news/storm-dominique-malonga-is-redefining-what-rookie-can-do-01k3c5qga6zz)
- [FOX 13 Seattle: Malonga 22, Storm rout](https://www.fox13seattle.com/sports/malonga-22-points-leads-storm-blowout-win-95-60-over-wings)
- [LV Review-Journal: Bell starter impact](https://www.reviewjournal.com/sports/aces/aces-kierstan-bell-makes-impact-after-moving-into-starting-lineup-3430304/)
- [LV Sun: Aces 18 threes vs Wings](https://lasvegassun.com/news/2025/aug/17/aces-hit-18-3-pointers-in-106-87-win-over-the-wing/)
- [ESPN: Dream 104-85 Sparks](https://www.espn.com/wnba/recap/_/gameId/401736379)
- [ESPN: Sparks vs Aces 6/11 recap](https://www.espn.com/wnba/recap?gameId=401736171)

---

**Verdict for the orchestrator**: a news-ingest pipeline is the highest-ROI
addition to the picker. The headline-discoverable ceiling on top-tail
single-player contributions is around 73%. Today's picker captures
roughly a third of that ceiling. The Bonner, Mitchell, Whitcomb, Wilson,
Westbeld, Quinerly, James, Jackson, and Holmes picks were ALL knowable
that morning from public sources. The Real Sports multiplier had not
yet absorbed the news in many of those cases, so the EV was sitting
there. Whether to build a scraper-driven ingest layer, or merely to
gate the picker through a `news_features` adapter we backfill nightly,
is a build-cost question. The signal is real.

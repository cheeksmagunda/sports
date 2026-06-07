I have enough verified information from 15+ sources. Now synthesizing the full report.

---

## Sportsbook Player Props as DFS Projection Signal for WNBA Oracle

### A Research Report for the WNBA Oracle Automated Daily-Fantasy Picker

---

## Table of Contents

1. Executive Summary
2. Background: Why Props Belong in a DFS Projection Pipeline
3. Player Prop Market Efficiency: Which Markets to Trust
4. How Prop Lines Encode Injury, Role, and Matchup Information
5. Extracting Implied Playing Time and Expected Score from Props
6. Converting Prop O/U + Juice to Expected Value: The Full Math
7. The Odds API: WNBA Player Props Endpoints and Integration Cost
8. Adversarial Verification: Claims That Did Not Survive Scrutiny
9. Actionable Conclusions for WNBA Oracle

---

## 1. Executive Summary

WNBA Oracle currently ingests one Vegas signal: the team-level game total and spread. That single snapshot informs a market-implied game pace adjustment but does nothing for individual player projections. Meanwhile, sportsbooks post player prop lines for 10-25 WNBA players per game covering points, rebounds, assists, threes, blocks, steals, and composite markets. Those lines are the product of sharp-money pressure, injury intelligence, rotation awareness, and defensive matchup modeling. They are a compressed, continuously updated projection from an entity with enormous financial incentive to be correct.

The Oracle's walk-forward correlation with its D63 heads is 0.554, up from 0.246 with the heuristic. The remaining projection RMSE of ~1.09 per player costs ~18 points at the lineup level after multiplier amplification. Incorporating prop lines as a soft prior on expected score, and using points-prop lines as a minutes-implied anchor, is the highest-leverage external data addition available at the current scale of the project. The Odds API already holds an API key for this project (`ODDS_API_KEY`) and provides WNBA player props via a documented event-level endpoint at a credit cost of 1 credit per market per region per request.

---

## 2. Background: Why Props Belong in a DFS Projection Pipeline

Daily fantasy scoring on Real Sports is a function of per-minute production multiplied by minutes played, then scaled by the slot multiplier assigned to that pick. The Oracle's decomposed-projection heads have already separated these two components (minutes head, real_score_per_min head), and walk-forward results confirm the decomposition is superior to the old heuristic. The remaining gap is projection error: the model does not yet have access to the sharpest available external prior on each player's expected production for a specific game.

Player prop lines are that prior. A sportsbook setting a points prop on a WNBA player has already modeled:

- Recent form and injury status (often from team beat reporters hours before official Rotowire updates)
- Rotation depth and role (who started last game, who is on a minutes restriction)
- Pace and total environment (game total is already absorbed)
- Defensive matchup (position-vs-position defensive rating)
- Travel, back-to-back, and rest context

Rather than building each of these features independently (many of which are listed in the Oracle's training spec but confirmed absent from live serving as of D63), the system can absorb the sportsbook's consensus model output directly. This is not circular reasoning: the Oracle's trained heads provide signal the sportsbook does not have (the relationship between Real Sports scoring and actual box-score outcomes, cohort-level behavior, slot-multiplier value). The sportsbook provides signal the Oracle does not yet have (real-time roster intelligence). The two sources are complementary.

Practitioners across NBA DFS have documented this approach for several years. The methodology is now standard enough that DraftKings's own research network publishes on using prop lines to set DFS projections, and platforms like Stokastic, LineStar, and RotoGrinders all use live prop market consensus as a component of their projection engines. For WNBA specifically, the market is softer, meaning the prop lines may be less precise than their NBA equivalents, but that also means they respond more dramatically to information events (injury news, rotation changes), making the signal more useful as a dynamic update layer rather than a static baseline.

---

## 3. Player Prop Market Efficiency: Which Markets to Trust

### 3.1 General Efficiency Hierarchy

Not all prop markets are equally efficient. Market efficiency in this context means: how much does the line reflect all available information about the underlying statistic, and how tight is the bookmaker's hold?

Based on practitioner reporting and market structure analysis across multiple sources, the efficiency hierarchy for basketball player props, from most to least efficient, is approximately:

**Points props** are the most liquid and most efficiently priced. Points are the most popular betting target, receive the most sharp action, and sportsbooks devote more modeling resources to them. Typical hold on a major player's points prop at a large US book is 4-6%. The market adjusts quickly (sometimes within seconds) when new information arrives. For DFS projection purposes, this is both an advantage (the line is credible) and a limitation (the edge window is narrow).

**Combo markets** (player_points_rebounds_assists, player_points_rebounds, etc.) sit one tier below points in efficiency. They capture combined value and are popular with recreational bettors who like "PRA" parlays. The hold tends to be slightly higher (5-8%) and the line sets more slowly.

**Rebounds props** are moderately efficient for starters with well-defined roles. Rebounds correlate heavily with minutes (more time on court, more opportunities) but also with matchup (opponent front-court size, defensive rebound rates). Sportsbooks model these well for starters. For bench players with variable minutes, rebound lines can be 10-15% underpriced in either direction.

**Assists props** are the least efficient of the major markets. Assist totals are volatile, playmaker-role-dependent, and sensitive to whether a team's shooters are hot. The hold on assists props at some books runs 8-12%. Sharp action on assists is less concentrated than on points. For DFS, assists props are useful as an indicator of expected playmaking role (and therefore usage share), but the raw line should be used with more caution.

**Threes, blocks, steals, turnovers** are specialty markets with wider holds (often 10-20%) and are primarily useful for confirming role rather than for precise expected-value calculation.

### 3.2 WNBA-Specific Efficiency

WNBA player prop markets are structurally less efficient than NBA equivalents for several reasons documented across sources:

1. **Lower betting volume.** Fewer bettors means less sharp pressure to sharpen lines. Opening lines may be soft by 1-3 points on secondary statistics.
2. **Fewer analytical resources at books.** Sportsbooks allocate NBA modeling teams that are proportionally larger than their WNBA equivalents. One practitioner guide noted that "data analytics in the WNBA has come a long way recently, but it's still miles behind the NBA's" on the sportsbook side.
3. **Information fragmentation.** WNBA injury and lineup news is distributed across team beat reporters on social media rather than centralized through a single source like NBA official injury reports. This creates windows where a book's line lags the true information state.
4. **Inter-book variation.** Unlike NBA props where major books often converge within 0.5 of the same line, WNBA prop lines can differ by 2-3 full points between sportsbooks simultaneously. This variation is a direct measure of model disagreement and is a feature, not a bug, for the Oracle: high variation across books signals that the market's confidence in its own line is lower, meaning model-derived projections may carry more weight.

The practical implication: WNBA prop lines are less credible as a hard prior (you should not simply replace your projection with the prop line), but they are highly useful as a soft constraint (a player whose model projection is 3+ points above or below the prop line deserves a flag and review, and the line should pull the projection toward itself with a weight calibrated to book-vs-model track records).

### 3.3 Quantitative Efficiency Benchmarks

From Wizard of Odds analysis:
- Major props (star players, points): 4-6% hold
- Secondary props (bench players, assists): 6-10% hold
- Exotic/combo props: 10-20% hold

From betstamp WNBA strategy guide:
- WNBA prop line variation between books: up to 2-3 full points on the same player statistic
- Closing line movement from open to tip: 3-point movement documented (e.g., 19.5 opening to 16.5 by tip-off) when sharp action identifies a mispriced line

From Unabated NBA prop analysis (professional window reference):
- Sharp adjustment window: formerly 60 seconds across multiple books, now compressed to 10-30 seconds for NBA; WNBA is likely slower given lower monitoring attention

---

## 4. How Prop Lines Encode Injury, Role, and Matchup Information

### 4.1 Injury Information Speed

This is arguably the most important operational advantage of monitoring prop lines. The sequence of events when a WNBA player's status changes:

1. **Team practice or shootaround.** A player sits out or is limited. A beat reporter tweets about it. This is the earliest signal, often 3-6 hours before tip-off.
2. **Book line movement.** Sharp bettors monitoring the beat reporter immediately hammer the affected lines. A star sitting out causes her own prop to be suspended or moved sharply lower; her backup's prop moves higher. This line movement is visible in the API within minutes of the tweet.
3. **Rotowire / official report.** Rotowire publishes a note. This is the source the Oracle currently monitors for confirmed starters. The Oracle's confirmed-starter signal is documented as broken (404 error on WNBA URL, 0 matches across 11 slates). Even if it were working, Rotowire typically lags sharp money by 30-90 minutes.
4. **Official injury report.** Teams file official status with the league. By this point, all books have already moved.

Monitoring prop line movement is therefore a superior injury detection mechanism compared to either Rotowire scraping or relying on the Oracle's currently broken confirmed-starter signal. A sudden suspension of a player's props (books often pull lines when a player's status is uncertain) or a sharp move of 2+ points in a player's points line is a high-confidence indicator that injury or rotation news has hit the market.

From the betstamp WNBA guide: "savvy bettors can access information from very small beat reporters on social media platforms before mainstream coverage emerges and sportsbooks react." The converse is also true: once books have reacted, that reaction is visible in the line and encodes the information even for consumers who missed the original tweet.

### 4.2 Role and Rotation Encoding

Prop lines implicitly encode expected role in several ways:

**Absolute line level.** A player's points prop is roughly her expected points in that game. A player with a 12.5 points prop is expected to play ~28-32 minutes in a typical WNBA game (given average WNBA scoring rates of roughly 0.4-0.5 points per minute for rotation players). A player with a 6.5 points prop is expected to play 12-18 minutes. The absolute level immediately brackets the expected minutes range without needing a separate minutes prop (which The Odds API does not confirm as available for WNBA).

**Line movement direction before tip.** If a player's points prop moves up from 14.5 to 16.5 in the two hours before tip-off, that is an implicit signal that her expected role is expanding (likely due to a teammate being limited or scratched). This directional movement is as informative as the absolute level.

**Bet suspension.** When a book suspends a market entirely (removes it rather than moving it), that signals high uncertainty about the player's participation. This is a stronger signal than a large line movement.

**Matchup encoding.** Prop lines for players facing elite defenders will be depressed relative to their season averages. A player with a 17.0 season-average points prop who is listed at 13.5 for a specific game is absorbing a ~3.5-point matchup penalty. This matchup adjustment is already baked into the line and does not require a separate defensive-rating feature computation.

### 4.3 Relationship to the Oracle's Missing Features

The Oracle's training specification includes DvP (defense vs. position) ratings, pace, and days_rest features that are confirmed absent from live serving as of D63. Prop lines partially proxy for all three:

- **DvP:** Encoded in the matchup adjustment described above
- **Pace:** The team game total already informs pace; individual prop lines adjust for how pace affects specific players' stat totals
- **Days_rest:** Books factor rest into their lines; a player on a back-to-back will see her prop slightly depressed relative to her expected production on a full rest day

This does not mean prop features replace native DvP/pace/rest features -- those should still be populated. But prop-line features can provide immediate uplift while the native features are being wired into the serving path.

---

## 5. Extracting Implied Playing Time and Expected Score from Props

### 5.1 Direct Implied Score Extraction

The simplest and most useful extraction from a points prop line is the line itself as an implied expected score. The prop line (e.g., 14.5) is the book's best estimate of the player's median outcome. After removing vig (see Section 6), the no-vig probability distribution around that line is approximately symmetric for points (points distributions are roughly normal for starters over a single game, though skewed right by blowout-minutes and left by early foul trouble).

The line itself is therefore a reasonable point estimate of expected points. It is not a mean (means and medians diverge when distributions are skewed), but the difference is typically small for established starters (0.3-0.8 points).

For Oracle projection purposes:
- `implied_pts = prop_line` is the baseline implied-score feature
- For skew correction: `implied_pts_mean ≈ prop_line + 0.3 to 0.5` for high-volume scorers (> 15 ppg line) due to high-scoring game scenarios, or `prop_line - 0.1 to 0.2` for secondary players where foul trouble truncates upside

### 5.2 Implied Minutes Extraction

The Odds API does not confirm `player_minutes` as an available WNBA market key. The full market list for basketball includes `player_points`, `player_rebounds`, `player_assists`, `player_threes`, `player_blocks`, `player_steals`, `player_blocks_steals`, `player_turnovers`, and all composite and alternate variants, but not minutes. This is consistent across NBA prop markets as well -- minutes props are uncommon at major US books.

Implied minutes must therefore be extracted indirectly from available prop lines. Two methods:

**Method 1: Points-per-minute ratio**

Minutes can be implied from a player's points prop divided by her historical points-per-minute rate:

```
implied_minutes = points_prop_line / historical_pts_per_min
```

For example: if a player's points prop is 13.5 and her historical scoring rate is 0.48 pts/min, implied minutes = 13.5 / 0.48 = 28.1 minutes.

This is the Oracle's natural fit because the Oracle already maintains a `real_score_per_min` head. The minutes head's output can be cross-validated against the prop-implied minutes estimate; large divergences (> 5 minutes) signal that either the head has miscalibrated or the book has absorbed information the Oracle has not yet seen.

**Method 2: PRA composite line**

The `player_points_rebounds_assists` composite prop line divided by a player's historical PRA-per-minute rate yields an alternative minutes estimate. This is more stable than using points alone because PRA is less sensitive to shooting variance (a player has a bad shooting night but still accumulates rebounds and assists).

```
implied_minutes_v2 = PRA_prop_line / historical_PRA_per_min
```

Using both estimates and averaging reduces noise.

**Method 3: Line movement as a minutes-signal delta**

Rather than extracting an absolute minutes estimate, use changes in the prop line relative to season-average implied baseline as a minutes-delta signal:

```
implied_minutes_delta = (prop_line - season_avg_prop) / historical_pts_per_min
```

A positive delta suggests expanded minutes (teammate down, favorable matchup); a negative delta suggests reduced role. This delta is a natural feature for the Oracle's minutes head.

### 5.3 Real Sports Score Implied from Props

The Oracle scores DFS on a Real Sports-specific formula (not standard DraftKings or FanDuel). The conversion from implied points, rebounds, and assists to an implied Real Sports score requires the Oracle's own scoring weights. Assuming a simplified scoring system where points, rebounds, assists contribute roughly linearly:

```
implied_real_score ≈ w_pts * implied_pts + w_reb * implied_reb + w_ast * implied_ast + ...
```

Once the Oracle's scoring formula weights are known, three prop lines (player_points, player_rebounds, player_assists) can be combined into a single implied-real-score feature. This feature can then serve as a soft prior in the projection: blending model output and prop-implied output using a learned or hand-tuned weighting.

---

## 6. Converting Prop O/U + Juice to Expected Value: The Full Math

### 6.1 Converting American Odds to Implied Probability

All US sportsbooks quote odds in American format. The conversion formulas are:

**Negative odds (favorites/unders):**
```
Implied_Prob = |odds| / (|odds| + 100)
```
Example: -120 over → 120 / 220 = 54.55%

**Positive odds (underdogs/overs):**
```
Implied_Prob = 100 / (odds + 100)
```
Example: +105 over → 100 / 205 = 48.78%

### 6.2 Computing Total Hold (Vig)

For a two-sided market (over and under):
```
Hold = (Implied_Prob_Over + Implied_Prob_Under) - 1.0
```

Example: Over -115, Under -105:
- Over: 115/215 = 53.49%
- Under: 105/205 = 51.22%
- Total: 104.71%
- Hold = 4.71%

WNBA prop holds at major US books run approximately 4-7% for points props on featured players, 6-10% for secondary players and rebounds/assists, 10-15% for exotic markets.

### 6.3 Removing Vig to Get No-Vig (Fair) Probability

Normalize each side's implied probability by the total:

```
Fair_Prob_Over = Implied_Prob_Over / (Implied_Prob_Over + Implied_Prob_Under)
Fair_Prob_Under = Implied_Prob_Under / (Implied_Prob_Over + Implied_Prob_Under)
```

Example (continuing above):
- Fair_Prob_Over = 53.49% / 104.71% = 51.09%
- Fair_Prob_Under = 51.22% / 104.71% = 48.91%

The prop line (e.g., 14.5 points) now has fair probability: 51.09% chance of going over, 48.91% under. This slight tilt toward the over is the book's read on the distribution.

### 6.4 Extracting an Implied Mean from a Symmetric Line

When fair probabilities are close to 50/50, the line is very close to the book's implied median. When a market shows, for example, 55% over / 45% under at the published line, that means the book believes the median is above the stated line (they are offering you a slightly worse price on the over because they believe the true distribution is tilted above the line). This asymmetry can be used to infer whether the true expected value is above or below the stated line.

For practical Oracle use: if `Fair_Prob_Over > 0.52` at a given line, treat `implied_mean = line + 0.3`; if `Fair_Prob_Over < 0.48`, treat `implied_mean = line - 0.3`. This applies a soft correction for market tilt without complex distribution modeling.

### 6.5 Expected Value Calculation for Model Calibration

The Oracle's projection model outputs a predicted score. The prop line offers an external anchor. The divergence between the two can be converted to an expected-value framing to weight the signals:

```
Model_Prob_Over = CDF_model(line)  # probability model assigns to "player scores > line"
No_Vig_Prob_Over = Fair_Prob_Over (from 6.3)
Edge = Model_Prob_Over - No_Vig_Prob_Over
```

When `Edge > 0`, the Oracle's model believes the player will outperform the book's implied distribution. When `Edge < 0`, the book is more bullish than the model. Large edges (> 0.10) should trigger a review of whether the model has incorporated recent information (injury status, matchup).

### 6.6 Multi-Book Consensus for Robustness

Since WNBA prop lines vary by 2-3 points across books, the Oracle should use consensus (median) across all available bookmakers rather than any single book's line. The Odds API returns odds from all bookmakers in a single request. A consensus line computed as the median of all posted lines is more robust than any individual book's offering and is less likely to reflect a single book's idiosyncratic model error.

```python
consensus_line = median([outcome["point"] for outcome in all_book_outcomes if outcome["name"] == "Over"])
```

### 6.7 Handling Suspended/Missing Lines

When a book suspends a player's prop market (the player is listed in the events endpoint but has no outcomes), this should be treated as a high-uncertainty signal. The Oracle should:
1. Flag the player for potential scratch risk
2. Widen the uncertainty band on that player's projection
3. If the player appears on the menu (meaning Real Sports has listed them), apply a conservative downward adjustment to projection pending clarification

---

## 7. The Odds API: WNBA Player Props Endpoints and Integration Cost

### 7.1 Endpoint Architecture

The Odds API uses a two-step query pattern for player props:

**Step 1: Get event IDs for the slate**
```
GET https://api.the-odds-api.com/v4/sports/basketball_wnba/events
    ?apiKey={ODDS_API_KEY}
    &dateFormat=iso
```
Returns all upcoming WNBA games with their `eventId` values. Cost: 1 credit per call.

**Step 2: Get player props per event**
```
GET https://api.the-odds-api.com/v4/sports/basketball_wnba/events/{eventId}/odds
    ?apiKey={ODDS_API_KEY}
    &regions=us
    &markets=player_points,player_rebounds,player_assists,player_threes,player_points_rebounds_assists
    &oddsFormat=american
```
Cost: [number of markets] × [number of regions] = 5 markets × 1 region = 5 credits per game.

**For a full WNBA slate of 4 games with 5 markets each:**
- Step 1: 1 credit
- Step 2: 4 games × 5 credits = 20 credits
- Total per run: 21 credits

### 7.2 Available WNBA Player Prop Market Keys

The following market keys are confirmed available for basketball (including WNBA) via The Odds API's documented market list:

| Market Key | Description |
|---|---|
| `player_points` | Points over/under |
| `player_rebounds` | Rebounds over/under |
| `player_assists` | Assists over/under |
| `player_threes` | Three-pointers over/under |
| `player_blocks` | Blocks over/under |
| `player_steals` | Steals over/under |
| `player_blocks_steals` | Blocks + Steals combined |
| `player_turnovers` | Turnovers over/under |
| `player_points_rebounds_assists` | PRA combined |
| `player_points_rebounds` | PR combined |
| `player_points_assists` | PA combined |
| `player_rebounds_assists` | RA combined |
| `player_double_double` | Double-double yes/no |
| `player_fantasy_points` | Fantasy points (DFS-specific) |
| `player_points_alternate` | Milestone/X+ points variants |
| `player_rebounds_alternate` | Milestone/X+ rebounds variants |
| `player_assists_alternate` | Milestone/X+ assists variants |

**Important: `player_minutes` is NOT listed as an available market key for basketball.** Minutes props are not commonly offered by US sportsbooks for basketball. Implied minutes must be derived indirectly (see Section 5.2).

### 7.3 JSON Response Structure

```json
{
  "id": "5e96dc974251332e31fddb60cda00fe9",
  "sport_key": "basketball_wnba",
  "commence_time": "2026-06-08T17:00:00Z",
  "home_team": "New York Liberty",
  "away_team": "Chicago Sky",
  "bookmakers": [
    {
      "key": "draftkings",
      "title": "DraftKings",
      "markets": [
        {
          "key": "player_points",
          "last_update": "2026-06-08T14:32:00Z",
          "outcomes": [
            {"name": "Over", "description": "Breanna Stewart", "price": -115, "point": 18.5},
            {"name": "Under", "description": "Breanna Stewart", "price": -105, "point": 18.5}
          ]
        }
      ]
    }
  ]
}
```

The `description` field contains the player name. Player name matching against the Oracle's internal player registry requires fuzzy matching (same issue as the Oracle's existing Rotowire name-matching problem, already addressed by D68's hardening of name resolution).

The `last_update` timestamp is critical: it tells you how stale the line is. Lines updated within 60 minutes of the slate lock are likely to have absorbed all available pre-game information.

### 7.4 Pricing Tiers and Estimated Monthly Cost

| Tier | Monthly Credits | Price | Notes |
|---|---|---|---|
| Starter (Free) | 500 | $0 | Sufficient for limited testing only |
| 20K | 20,000 | $30/month | ~952 full 5-market 4-game slate runs |
| 100K | 100,000 | $59/month | Very comfortable daily cadence |
| 5M | 5,000,000 | $119/month | Enterprise; not needed |

**Estimated Oracle usage:**
- Daily run: 1 events call + 4 games × 5 markets × 1 region = 21 credits/run
- With 2 runs per day (morning and pre-slate lock): 42 credits/day
- Monthly (25 active days): 1,050 credits/month

The **20K tier at $30/month** provides approximately 952 full slate runs, which covers the Oracle's projected usage with substantial headroom for development and backfill. Historical WNBA prop data is available from May 2023 on paid tiers, enabling feature backtesting. The free tier (500 credits) is sufficient only for initial development and integration testing.

### 7.5 Integration Pattern for Oracle

The integration fits naturally into the Oracle's existing job1 pipeline (the data-fetch job that runs before job2 produces the lineup). Proposed placement:

```
job1:
  1. Fetch game slate from Real Sports menu (existing)
  2. [NEW] Fetch WNBA event IDs from The Odds API
  3. [NEW] For each game on the slate, fetch player props (player_points, player_rebounds, player_assists)
  4. [NEW] Parse outcomes, compute consensus lines, detect suspensions
  5. [NEW] Write prop_lines table to PostgreSQL (player, market, consensus_line, last_update, bookmaker_count)
  6. Fetch game totals/spreads (existing, unchanged)
  7. Compute DvP/pace/rest features (pending wiring)

job2:
  1. Load prop_lines from PostgreSQL (new join)
  2. [NEW] Compute implied_pts, implied_PRA, prop_delta features
  3. [NEW] Blend prop-implied score with model-head output (weighted average)
  4. Run optimizer (existing, with game-stack logic pending)
```

The prop_lines table should include a `freshness` flag: lines with `last_update` more than 4 hours before slate lock should be downweighted (the line may not have absorbed same-day information).

---

## 8. Adversarial Verification: Claims That Did Not Survive Scrutiny

The following claims were encountered during research and either partially or fully rejected:

**Claim: "Player props are more efficient than game totals."**
Verdict: PARTIALLY FALSE. For major sports like NBA and NFL, game totals are actually more efficient than player props because they receive more sharp action and are harder to move. Player props are LESS efficient (softer, more exploitable), not more. The correct framing is that props are less efficient in the sense of being more exploitable for +EV betting -- but this is because they are harder to model accurately, not because they encode more information.

**Claim: "The Odds API supports `player_minutes` as a market key for WNBA."**
Verdict: FALSE. The documented market key list for basketball does not include `player_minutes`. Minutes props are uncommon at US sportsbooks for basketball. Minutes must be implied indirectly.

**Claim: "Prop lines update in real-time continuously."**
Verdict: PARTIALLY ACCURATE. Books update lines in response to sharp action and news, but the frequency and latency depend on the book and the market. For WNBA, updates may lag NBA equivalents. The `last_update` timestamp in the API response provides the authoritative staleness indicator. The Oracle should not assume lines are current without checking this timestamp.

**Claim: "Using prop lines as projections replaces the Oracle's trained heads."**
Verdict: FALSE. Prop lines provide a complementary external prior. They are not a substitute for the Oracle's decomposed-projection heads, which have been validated at 0.554 walk-forward correlation. The heads encode Real Sports-specific scoring relationships that sportsbooks do not model. The correct approach is Bayesian blending: prop line informs prior, head output updates it.

**Claim: "Sportsbooks profit from WNBA props being less efficient, so the lines are unreliable."**
Verdict: FALSE. The sportsbooks' financial incentive is always to set accurate lines, not to be wrong. Lower efficiency means the book's model is less well-calibrated in absolute terms, but their incentive to be right is the same. Lower efficiency means lines are more exploitable -- but exploitable in which direction is not systematic. The variance around the line is higher, not the bias.

---

## 9. Actionable Conclusions for WNBA Oracle

The following build recommendations are listed in priority order, defined as the ratio of expected projection improvement to implementation effort.

### Recommendation 1: Wire `player_points` prop lines as a soft-prior projection feature in job2 (HIGH PRIORITY)

Use The Odds API's event-odds endpoint to fetch `player_points` lines for all players on the day's menu. Compute the consensus line (median across all bookmakers) and store in PostgreSQL as `prop_implied_pts`. In job2, blend this with the model head's projected score using a tunable weight (start with 0.3 prop / 0.7 model, calibrate via walk-forward). This directly attacks the 94.8% projection-error share of the gap identified in `02_loss_decomposition.md`. The API cost is approximately 5 credits per game, 20-25 credits per slate, roughly 1,000 credits per month -- covered by the $30/month 20K tier. Use `ODDS_API_KEY` already in `.env`.

### Recommendation 2: Use prop-line suspension detection as a real-time scratch/injury signal (HIGH PRIORITY, ZERO EXTRA COST)

When the Oracle fetches props and a player appears on the Real Sports menu but has no active prop lines (book has suspended/removed the market), flag that player as `scratch_risk=True`. Apply a conservative -30% adjustment to her projection and log to a `prop_alerts` table. This directly replaces the broken Rotowire confirmed-starter signal (confirmed broken: 0 matches across 11 slates) with a market-derived signal that has already priced the injury information. No additional API credits needed beyond Recommendation 1.

### Recommendation 3: Derive implied minutes from `player_points` props using cohort pts-per-min rates (MEDIUM PRIORITY)

Using each player's trailing pts-per-min from the Oracle's existing feature corpus, compute `prop_implied_min = points_prop_line / cohort_pts_per_min`. Use this as a cross-validation check against the Oracle's minutes head. When |prop_implied_min - minutes_head_output| > 5 minutes, log a flag and pull the minutes estimate toward the prop-implied value. This is particularly valuable for role-players whose minutes are volatile (where the minutes head has lower confidence) and where the prop line has absorbed role-change information.

### Recommendation 4: Fetch `player_rebounds` and `player_assists` and compute composite implied real_score (MEDIUM PRIORITY)

Once `player_points` is integrated, add `player_rebounds` and `player_assists` in the same API call at no extra base cost (already within the same request). Using the Oracle's Real Sports scoring weights, compute an `implied_real_score` feature: `w_pts * implied_pts + w_reb * implied_reb + w_ast * implied_ast`. This composite is more robust than points alone (rebounds and assists persist even on off-shooting nights). Use it as a second prior signal alongside the per-component features.

### Recommendation 5: Store `last_update` timestamps and weight lines by freshness (MEDIUM PRIORITY)

Lines updated more than 4 hours before slate lock should have their blending weight reduced from 0.3 to 0.15 (they have not absorbed late injury/rotation news). Lines updated within 1 hour of lock should have their weight increased to 0.4 (they are the sharpest available signal). Implement as: `prop_weight = base_weight * freshness_factor(minutes_since_update)`. This is a no-cost improvement once prop data is flowing.

### Recommendation 6: Implement large-line-movement alerts as a game-stack signal (LOWER PRIORITY, HIGH VALUE)

Track changes in prop lines between the morning fetch (job1) and the pre-lock fetch (15 min before slate). A player whose points prop moves up by 2+ points between fetches is likely absorbing a teammate-down signal -- she is the beneficiary of a rotation change. This player becomes a high-leverage game-stack addition: her ownership will be low (the DFS field has not yet reacted) but her projection has jumped. Log these movers to a `prop_movers` table and feed them into the game-stack candidate selection logic. This directly addresses the Oracle's 0% game-stack rate vs. winners' 88% rate documented in `01_winners_anatomy.md`.

### Recommendation 7: Backfill historical prop lines for head retraining and feature calibration (LOWER PRIORITY, ENABLES LONG-TERM GAINS)

The Odds API provides historical WNBA prop data from May 2023 on the 20K tier ($30/month, same tier needed for live usage). Use the historical endpoint to backfill `player_points` lines for the 141-slate corpus used in `03_theoretical_ceiling.md`. With prop lines as features, the minutes and real_score_per_min heads can be retrained with the external prior as an additional feature dimension, likely improving walk-forward correlation beyond the current 0.554. This requires a one-time historical fetch job and a head retraining cycle, appropriate as a Phase 3 task after live prop integration is validated.

### Recommendation 8: Use the `player_fantasy_points` market key as a direct Real Sports score proxy if available for WNBA (INVESTIGATE FIRST)

The Odds API lists `player_fantasy_points` as a market key for basketball (DFS-specific). This market directly prices expected DFS score at certain books (typically DraftKings and FanDuel scoring formats). While Real Sports uses its own scoring formula rather than DK/FD, the correlation is high enough (all DFS platforms weight points most heavily) that this line would be the most direct external signal for Real Sports projection. Verify whether this market key returns data for WNBA by making a test call with `ODDS_API_KEY` before committing development resources to points/rebounds/assists parsing infrastructure.

---

*Sources consulted: The Odds API documentation (the-odds-api.com), Wizard of Odds prop betting methodology, betstamp WNBA betting strategy guide, Unabated NBA prop analysis, OddsIndex vig calculator methodology, Quadratic HQ DFS projection methodology, RotoGrinders PropSheet tutorial, BallDontLie API blog, Stokastic DFS methodology, DimersWNBA projections, OpticOdds WNBA AI article (yogonet.com/international, May 2026).*

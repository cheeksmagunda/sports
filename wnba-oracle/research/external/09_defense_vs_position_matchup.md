Now I have a complete picture of the current system state and all research findings. I can write the comprehensive report.

---

## Defense-vs-Position (DvP) Methods and Matchup Edge Quantification for WNBA DFS

### A Research Report for WNBA Oracle

---

## 1. What DvP Is and Why It Matters

Defense-vs-position (DvP) is a summary statistic measuring how many fantasy points per game a given team allows to opponents grouped by position -- guard, forward, or center. It transforms the question "is this a good matchup?" from qualitative scouting into a single ranked number: a team at the bottom of the DvP table for a position is a soft matchup to attack; a team at the top is a hard matchup to fade or at least not lean on.

The metric's popularity in DFS comes from a structural reality of basketball scheduling: unlike the NFL, players are not priced game-to-game for matchup difficulty. When a guard faces the league's worst guard defense, the market price on that guard is unchanged. DvP attempts to capture the premium that the pricing market does not.

The metric exists in two forms that must not be confused:

**Raw DvP**: mean fantasy points allowed per game to opposing positional players. Simple to compute. Sensitive to pace (a fast team's opponent naturally racks up more possessions and thus more counting stats), sensitive to injury luck (if a team faced weaker opposing guards early in the year, their guard DvP looks soft when it is not).

**Adjusted DvP / Opponent Plus-Minus**: measures each player's actual performance against a defense relative to that player's rolling average. If a guard who averages 28 DraftKings points scores 35 against the Dallas Wings, the Wings allowed +7 above expectation for that guard. Summing and averaging these deltas per team, per position, per rolling window gives a cleaner signal that isolates true defensive weakness rather than positional talent mismatch or schedule noise. This is the LineStar "net defense" figure and the FantasyLabs "True DvP" construct.

---

## 2. How DvP Is Computed: Step-by-Step

### 2.1 Data Collection

The raw material is a game-by-game log of player performance tagged with:
- The defensive team faced
- The player's primary position (G / F / C)
- The DFS scoring outcome (DraftKings or FanDuel fantasy points)

For WNBA Oracle this is exactly what the game-log corpus provides, minus the opponent tag at the player level. The current schema in `serving_features.py::build_opp_dvp_lookup` does compute mean real_score allowed per opponent team using the locked Real Sports formula -- that is already a first-order DvP signal, just not broken out by position because the current game-log schema does not carry a position column per row.

### 2.2 Raw Computation

For each (defending team, position) pair across N games:

```
raw_DvP(team, pos) = mean(fantasy_pts_scored | defender == team, player_pos == pos)
```

The result is ranked 1-to-N (1 = fewest allowed, hardest matchup; N = most allowed, softest matchup). The NBAstuffer method subtracts league average:

```
adjusted_raw_DvP(team, pos) = mean_allowed(team, pos) - league_mean_allowed(pos)
```

Positive means soft (allows above average). Negative means hard (allows below average). This is the formulation in the spec comments at `features/spec.py` line 113.

### 2.3 Pace Adjustment

The standard per-game DvP number confounds pace with defensive quality. A team playing at 85 possessions/game in WNBA terms will allow fewer raw fantasy points to any position than a team playing at 95 possessions/game, even with identical defensive efficiency per possession.

The correct pace-adjusted computation converts to a per-100-possessions basis:

```
pace_adj_DvP(team, pos) = (raw_DvP(team, pos) / team_possessions_per_game) x 100
```

Then the per-100 figure is compared to league average to get the edge in possessions-normalized terms. When translating back to a per-game projection for a specific matchup, you multiply by the expected possessions in that specific game:

```
expected_possessions_game = (team_pace + opp_pace) / 2
game_adj_DvP = pace_adj_DvP(team, pos) x (expected_possessions_game / 100)
```

This is exactly the logic behind `game_pace_implied` in the WNBA Oracle spec: `(team_pace + opp_pace) / 2` already exists in `build.py` line 202. The gap is that `opp_dvp_guard/forward/center` are still hardcoded to `pl.lit(0.0)` at line 205-207 rather than being populated from a position-split computation.

### 2.4 Weighted Rolling Window

Season-long DvP is too slow to update and too subject to opponent quality noise in the early schedule. Most DFS analysts weight recent games more heavily:

- FanDuel/DraftKings-facing tools typically use an 8-15 game rolling window.
- LineStar's "net defense" methodology uses a 7-game rolling average of player output to compute the delta, then averages those deltas per opposing team.
- A decay-weighted scheme (exponential with half-life ~5 games) is more statistically principled but the performance gain over a simple 10-game window is marginal given WNBA sample sizes.

For the WNBA, where a full season runs 40 games and teams play only 2-4 games per week, a 10-game rolling window captures approximately 3-4 weeks of matchups -- a reasonable trade-off between recency and stability.

---

## 3. Hard vs. Soft Matchups: Definitions and Persistence

### 3.1 Defining Hard and Soft

A common threshold in NBA/WNBA DFS practice:
- **Hard matchup**: team ranks in the top 5 (of 12-15 WNBA teams) for fewest fantasy points allowed to a position -- allowing below-average production.
- **Soft matchup**: team ranks in the bottom 5, allowing above-average production to that position.
- **Neutral**: middle tier, where DvP provides minimal edge.

The 1.3-fantasy-point gap between the top-20th-percentile defense and the bottom-20th-percentile defense (sourced from RotoGrinders' NBA analysis) is the best published quantitative bound. Translated to WNBA scoring where total fantasy points are lower, this gap probably compresses to 0.8-1.1 points per player per game -- modest but real across a five-player lineup. In a five-player pick with a 2.0x multiplier on position 1, a 1.0-point edge per player becomes 1.0 x 2.0 + 1.0 x 1.8 + ... = roughly 7-8 fantasy points at the lineup level across the full slate, which is close to the 4.9-point spread between rank-1 and rank-20 in WNBA Oracle's contest data. So the feature is not trivial.

### 3.2 Persistence Across a Season

This is where DvP research lands a surprising result: **raw DvP is largely noise, especially early in the season**. The NBA literature (FantasyLabs, RotoGrinders, SaberSim) consistently finds that DvP backtests as mostly uninformative, for several reasons:

1. **Small sample size**: With 40 games in a WNBA season, each team faces each position grouping (say, opposing guards) approximately 10-15 times. The variance on those 10-15 games dominates the signal. A team that allowed above-average guard production in games 1-10 may simply have faced above-average guard talent.

2. **Defensive switching**: Modern basketball (and increasingly WNBA) uses scheme-based switching where the primary defender on a star wing changes possession by possession. The "guard defense" or "forward defense" bucket is an abstraction that misses who actually guarded whom.

3. **Opponent-quality confounding**: Teams that play weak divisions early have flattering DvP numbers; teams that played against strong positional talent look worse. Without adjustment for opposing player quality (the Opponent Plus-Minus approach), raw DvP misleads.

4. **Year-to-year correlation**: Opponent 3-point percentage allowed, for example, has near-zero year-to-year correlation in the NBA -- illustrating how defensive outcome metrics, as opposed to process metrics, do not stabilize reliably. Team defensive rating as a whole is more stable (r-squared of adjusted vs unadjusted ratings in NBA SOS research was 0.986), but position-specific DvP at the fantasy-points level is noisier than team-level defensive rating.

**What does persist:**
- True team defensive quality (overall defensive rating) is year-to-year stable. A bad defensive team at game 10 is likely still bad at game 40.
- When a team has a genuine structural weakness at a position (e.g., lack of size at center, or poor perimeter rotations), it tends to persist across the season.
- The correlation between True DvP (Opponent Plus-Minus style) and player performance was 0.41-0.57 for guards and shooting guards in the FantasyLabs analysis -- meaningful but far from deterministic.

**Sample size threshold for reliability**: The NBA stabilization rate research (Medvedovsky 2020) and the general DFS practitioner consensus point to needing at least 15-20 games of data before a team's positional DvP becomes more signal than noise. In a 40-game WNBA season, this means DvP data is not meaningfully usable until Week 5-6 (mid-June for a May-September season). Before that threshold, regressing heavily to league average is appropriate.

---

## 4. Regression to Mean in WNBA Defensive Ratings

### 4.1 Why Regression Is Necessary

Early-season defensive ratings in WNBA are severely distorted:
- Schedule imbalance (teams play within-division clusters early)
- Sample sizes of 5-12 games
- Injury-driven roster volatility early in the year
- Expansion teams (Portland Fire, Toronto Tempo in 2026) with no prior baseline

The correct approach is Bayesian shrinkage: blend each team's observed DvP toward the league average, with the weight on the prior decreasing as games accumulate. The padding approach from Medvedovsky is one implementation: it adds a fixed number of "league-average game equivalents" to each team's observed sample before computing the rate. For a WNBA DvP feature, a reasonable prior weight equivalent to 10 games of league-average performance is sensible given 40-game seasons, meaning that even at game 40, the prior still contributes 20% of the signal.

### 4.2 Recommended Shrinkage Formula

```
shrunk_DvP(team, pos) = (
    observed_sum_delta(team, pos) + prior_games x 0.0
) / (observed_games + prior_games)
```

Where:
- `observed_sum_delta` = sum of (actual fantasy pts - player rolling average) across all games
- `prior_games` = 10 (shrinks strongly early, weakly late)
- Result is an Opponent Plus-Minus style adjusted metric centered at zero

At game 5: 33% weight on observed data, 67% on prior. At game 20: 67% weight on observed, 33% on prior. At game 40: 80% observed. This is appropriate for the WNBA's 40-game season.

### 4.3 WNBA-Specific Considerations

The WNBA has structural features that accelerate regression to mean:

- **Small rosters** (11-12 players vs NBA's 15): one or two player injuries can dramatically change a team's defensive profile, making past DvP data stale.
- **Fewer specialists**: WNBA lineups contain more multi-positional players who cover guard and forward duties interchangeably. This makes the position bucketing less clean than NBA.
- **15 teams in 2026**: The league mean has fewer data points than the NBA's 30-team sample. Outlier DvP values (like Connecticut Sun's 105.8 defensive rating vs Minnesota's 93.8 -- a 12-point gap in the 2026 season per Her Hoop Stats) are more likely to be real given the magnitude, but mid-table teams should be strongly regressed.

---

## 5. WNBA-Specific Data Sources

### 5.1 stats.wnba.com via nba_api

The primary programmatic source for WNBA defensive data is `stats.wnba.com` accessed with `league_id='10'`. The WNBA Oracle codebase already uses this via `nba_api` in `ingest/stats_wnba.py`.

Key endpoints for DvP construction:

**`LeagueDashTeamStats` with `MeasureType='Defense'`**:
- Already called in `fetch_team_pace_stats` but with `MeasureType='Advanced'`
- Switching to `MeasureType='Defense'` returns opponent stats columns: points allowed, FG%, opponent field goals by zone
- Use `league_id_nullable='10'` and `per_mode_detailed='PerGame'`

**`LeagueDashPlayerStats` with `MeasureType='Base'` filtered by opponent**:
- This is the correct endpoint for building position-level DvP
- Call with `opponent_team_id=<team_id>` to pull all games against a specific defending team
- Join to player position from the static WNBA player catalog
- Group by (defending team, player position) and compute mean fantasy points

**`leaguedashptdefend` / `leaguedashptteamdefend`**:
- Documented in the py_ball LeagueDash wiki: `DefenseCategory` parameter accepts "Overall", "3 Pointers", "2 Pointers", etc.
- These return closest-defender type data -- more granular but harder to map to fantasy DvP
- Less useful for the current WNBA Oracle feature gap; skip for now

The `wnba_leaguedashteamstats` function in the `wehoop` R package (which mirrors the Python nba_api structure) confirms `measure_type`, `per_mode`, `pace_adjust`, and `last_n_games` parameters are all available. The `last_n_games` parameter is critical for rolling-window DvP: setting `last_n_games=10` gives the 10-game recency window without requiring manual game-log aggregation.

**Rate limiting**: The WNBA Oracle `stats_wnba.py` already implements `sleep_between_calls(0.6)`. For DvP computation requiring team-level endpoints (12-15 teams in a season), total call time is under 15 seconds at 0.6s/call -- acceptable in the nightly Job 1 window.

### 5.2 basketball-reference.com

Basketball-Reference carries WNBA season data at `basketball-reference.com/wnba/` with team opponent stats pages. The 2025 and 2026 season summary pages include per-game team defense figures. However, basketball-reference does not expose position-specific DvP breakdowns (guard/forward/center fantasy points allowed), only team-aggregate opponent stats (points, FG%, rebounds allowed per game). It is useful as a validation source for overall defensive rating and pace, not as a primary DvP position-split source.

### 5.3 RotoWire Opponent Averages

RotoWire's `rotowire.com/wnba/opp-avg.php` is the most directly usable WNBA DvP source for the current build gap. It presents fantasy points allowed by team, filterable by position (Guard / Forward / Center), updated daily. The limitation is that it is a UI tool without a documented API -- it must be scraped. The page loads stats dynamically (the WebFetch confirmed a JS-loaded table), so a Playwright-based scrape or a direct XHR intercept against the underlying JSON endpoint is required.

### 5.4 LineStar Team Defense Report

`linestarapp.com/TeamDefenseReport/Sport/WNBA/Site/DraftKings` provides an adjusted DvP metric (net defense vs rolling player average) with both per-game and per-minute breakdowns. This is algorithmically the cleanest public source. It also has a starter/bench filter, which is valuable because allowing a lot of fantasy points to bench-level guards (who play against other benches) is not the same as allowing them to starters. The data is not available programmatically -- it requires scraping -- and has intermittent "data not yet available" gaps early in the season.

### 5.5 Her Hoop Stats

`herhoopstats.com` provides comprehensive WNBA team-level defensive ratings and opponent stats for both the 2025 and 2026 seasons. The 2026 page confirmed defensive rating figures (Minnesota 93.8, Connecticut 105.8). It does not provide position-level DvP breakdowns but is an excellent cross-validation source for overall team defensive quality.

### 5.6 The Ground-Truth Computation Approach

For WNBA Oracle, the cleanest path that avoids scraping third-party sites is to compute DvP directly from the game-log corpus that already lives in the database:

```python
# Pseudocode for position-split DvP from existing game logs
# game_logs already has: player_id, opponent, real_score (computable), date
# Need to add: position column from static player catalog

from nba_api.stats.static import players
catalog = {p['id']: p for p in players.get_wnba_players()}
# position field exists in the catalog as 'position'

# Join position to game_logs, then:
dvp_by_pos = (
    game_logs
    .filter(pl.col("min") >= 5.0)
    .with_columns(pl.col("player_id").map_elements(
        lambda pid: catalog.get(int(pid), {}).get("position", "F")
    ).alias("position"))
    .with_columns(pl.col("position").map_elements(cohort_for_position).alias("cohort"))
    .group_by(["opponent", "cohort"])
    .agg(pl.col("_real_score").mean().alias("dvp"))
)
```

This is a direct extension of the existing `build_opp_dvp_lookup` function in `serving_features.py`, which already computes position-agnostic mean allowed. Adding the position join and splitting by cohort (G/F/C) produces `opp_dvp_guard`, `opp_dvp_forward`, `opp_dvp_center` as position-specific features rather than the current single value applied to all three.

---

## 6. Correlation Data: Pace vs. DvP for Guards vs. Forwards

The most important quantitative finding for WNBA Oracle lineup construction comes from the FantasyLabs positional correlation analysis (NBA data, which directionally applies to WNBA):

| Position | DvP (DRtg) Correlation | Pace Correlation |
|----------|----------------------|-----------------|
| PG | 0.41 | 0.57 |
| SG | 0.49 | 0.43 |
| SF | 0.16 | -0.04 |
| PF | 0.41 | 0.34 |
| C | 0.20 | 0.12 |

**The key takeaway**: Pace is more predictive than matchup for point guards. Defensive quality matters more for shooting guards. For wings (SF) and centers, neither factor has strong predictive power -- player-specific form and usage dominate. This has direct implications for how much weight to assign `opp_dvp_forward` vs `game_pace_implied` in the LightGBM heads.

In the WNBA three-cohort model (G/F/C), this translates to:
- Guard cohort: `game_pace_implied` and `opp_dvp_guard` are roughly equally informative, with pace slightly leading.
- Forward cohort: `opp_dvp_forward` marginally more useful than pace, but both are weak signals; form features dominate.
- Center cohort: both matchup and pace features are low-signal; minutes and per-minute production features dominate.

This does not mean DvP is useless for forwards and centers -- it means its signal is in a different range (0.16-0.20 correlation) than guard pace (0.57). A model that includes all three will still benefit from DvP at the margin, especially in GPP settings where a 0.5-point edge in projection accuracy compounds across lineup slots.

---

## 7. Translating DvP to a Projection Multiplier

### 7.1 The Percentage-Above-Average Method

The most widely cited translation formula in DFS analytics is a percentage adjustment:

```
projected_fantasy_pts = base_projection x (1 + dvp_edge_pct)
```

Where `dvp_edge_pct` is the team's DvP at that position expressed as percentage above/below league average:

```
dvp_edge_pct = (team_allowed_avg_pos - league_avg_allowed_pos) / league_avg_allowed_pos
```

If the league average allows 28 DraftKings points per game to guards, and a team allows 31.5, the edge is +12.5%. A guard projecting at 32 base becomes 32 x 1.125 = 36 for this matchup. A hard matchup (25 allowed vs 28 average) applies -10.7%, reducing a 32-point projection to 28.6.

**Practical range in WNBA**: Given the 1.3-point spread across the top/bottom 20th percentile found in the NBA research, and WNBA's lower absolute scoring levels, the realistic edge multiplier range is roughly -8% to +8% for most matchups, with extreme outliers reaching -12% to +15% (e.g., Minnesota's 93.8 vs Connecticut's 105.8 defensive ratings represent a 12-point gap, which relative to a ~96-point league average is a ~12.5% swing in either direction).

### 7.2 Direct Feature Injection (WNBA Oracle Approach)

For LightGBM-based models, the percentage-multiplier framing is less relevant than the direct feature value. LightGBM discovers the nonlinear relationship between `opp_dvp_forward` and `real_score_per_min` during training. The feature should be:

- Expressed in **fantasy points above/below league average** (units = real_score delta per game) rather than as a raw mean-allowed value, so the model's split thresholds are interpretable and centered near zero.
- Applied **after** pace normalization, so the feature captures true defensive weakness not pace-inflated volume.
- **Clipped** to a reasonable range (e.g., -5 to +5 real_score delta) to prevent outlier matches from dominating.

The current implementation in `build.py` assigns `pl.lit(0.0)` to all three DvP features. Any non-zero value -- even the position-agnostic mean from `build_opp_dvp_lookup` -- would be better than zero, because zero flattens the model's attention on these features entirely. However, the model was also trained with these features always zero in the training corpus (the spec notes they are "zero-filled in the live path"), which means the training signal on these columns may itself be zero or near-zero. If the training corpus also zero-filled DvP during feature construction, then the model has effectively been trained to ignore those columns. This needs to be verified before assuming the trained heads will respond correctly to non-zero DvP values at serve time.

### 7.3 Re-Training Implication

If the corpus DvP features were also zero during training (which is the likely state given the same build code populates both training and serving features), then correctly populating DvP requires a retrain, not just a serving fix. The correct sequence is:

1. Build the position-split DvP lookup for every game in the training corpus, using game dates as the cutoff (to avoid look-ahead: for game on date D, DvP is computed from all games before D against that opponent).
2. Populate `opp_dvp_guard/forward/center` in the training feature matrix.
3. Retrain heads. Verify that DvP features appear in LightGBM feature importance at a meaningful rank.
4. Update the serving path to populate these features at job1 time, before job2 runs.

---

## 8. Hard vs. Soft Matchup Persistence: Practical Guidance

### 8.1 What Persists

Based on the research synthesis:

**Persists reliably (use at full weight after 15+ games)**:
- Overall team defensive rating (Her Hoop Stats 2026: 12-point gap between best and worst)
- Teams with structural defensive weaknesses (undersized frontcourt, poor help rotation)
- High-pace vs low-pace team identity (WNBA pace is relatively stable: winning teams like Minnesota, New York, Atlanta show the highest pace consistency per the bellottibasketball.substack analysis)

**Partially persists (use with 50% weight)**:
- Position-specific DvP with 15-25 games of data
- Tendency to allow high guard or center production based on defensive scheme
- Back-to-back game effects on defensive effort

**Does not persist (do not use, or regress heavily)**:
- DvP in first 10 games of season
- 3-point percentage allowed (near-zero year-to-year correlation)
- Single-game defensive outperformance ("hot defense" one game means nothing)
- DvP built on games against weaker opponents not adjusted for quality

### 8.2 The "Hard Matchup Fade" Risk

A common DFS mistake is reflexively fading players in hard matchups. The research suggests this is often unprofitable because:

1. Hard matchups are widely known and already reflected in ownership. Fading them is not contrarian -- it is mainstream.
2. A star player's individual skill frequently overrides team-level DvP. A'ja Wilson's per-game production is driven primarily by her usage rate and minutes, not by whether the opponent has a good center DvP.
3. In GPP, the value of a hard-matchup player who outperforms their rating (contrarian relative to ownership expectations) is higher than the cost of the downside.

The practical rule: use DvP as a **tiebreaker among comparable projections**, not as a veto. If two forwards have similar form-based projections, prefer the one with the softer positional matchup. Do not drop a high-projection player two tiers solely because of a hard matchup.

---

## 9. Positional Assignment Challenges in WNBA

### 9.1 The Three-Cohort Problem

The WNBA Oracle uses G/F/C cohorts (defined in `spec.py::cohort_for_position`). Real Sports position strings can be hyphenated (G-F, F-C). The current `cohort_for_position` function takes the first character, which is reasonable but means a G-F player's DvP is computed from the guard bucket even though she may spend 40% of minutes at forward.

For DvP construction, the correct approach is to use the same cohort assignment the model uses -- so the DvP feature and the model head are consistent. A G-F player facing a soft guard matchup but a hard forward matchup gets `opp_dvp_guard` set to the soft value, and she is predicted by the Guard head. This is internally consistent even if imperfect.

### 9.2 Small Roster Effects

With 11-12 players per roster, the "opposing guard" bucket for a WNBA team in a given game contains 3-4 players rather than the NBA's 5-6. This increases variance on the DvP calculation for a single game. The mitigation is the 10-game rolling window, which aggregates 30-40 guard-matchup games per position before stabilizing.

### 9.3 DraftKings Roster Slots

DraftKings WNBA classic contests use G/F/C with FLEX slots. A G/F-eligible player can fill either slot. This means the DvP signal for a flex-eligible forward who appears in the Guard slot should ideally use the guard DvP, not the forward DvP -- but in practice the position assignment at lineup construction time is the DraftKings eligibility tag, not always the Real Sports position. The WNBA Oracle cohort assignment from `spec.py` maps Real Sports positions, which closely but not perfectly mirrors DraftKings eligibility.

---

## 10. Current System State and the Live-Path Gap

The gap is precisely documented in the codebase:

In `build.py` lines 205-207:
```python
pl.lit(0.0).alias("opp_dvp_guard"),
pl.lit(0.0).alias("opp_dvp_forward"),
pl.lit(0.0).alias("opp_dvp_center"),
```

In `job1.py` lines 324-327:
```python
dvp = opp_dvp_map.get(opp_abbr, 0.0)
hf["opp_dvp_guard"] = dvp
hf["opp_dvp_forward"] = dvp
hf["opp_dvp_center"] = dvp
```

Job1 currently applies the same non-position-specific DvP value to all three cohort features, sourced from `build_opp_dvp_lookup` in `serving_features.py`. This is better than zero but still conflates guard, forward, and center defensive quality into one mean value.

The training corpus situation needs investigation: if `build.py` (which populates both training and serving features) also wrote zeros for DvP during corpus construction, then the LightGBM heads were trained on zeroed DvP features and will not respond meaningfully to non-zero values -- the model has learned to ignore those columns. If, on the other hand, the corpus was built from historical game logs with the `build_opp_dvp_lookup` already called (as the current job1 code does), then the heads have seen non-zero DvP values and will respond to them at serve time.

This is the critical verification step before investing in a full position-split DvP pipeline.

---

## 11. Adversarial Verification of Key Claims

The following claims from the research were tested against multiple sources:

**Claim: "DvP is mostly noise"** -- CONFIRMED by multiple independent sources (RotoGrinders, FantasyLabs, SaberSim). The 1.3-point spread between top-20th and bottom-20th percentile defense is the consensus quantitative bound. Not refuted by any source.

**Claim: "Pace is more predictive than DvP for guards"** -- CONFIRMED by FantasyLabs correlation data (0.57 pace vs 0.41 DRtg for PG). Directionally consistent with RotoGrinders analysis.

**Claim: "Position-specific DvP is available from stats.wnba.com"** -- PARTIALLY CONFIRMED. The API endpoints exist (leaguedashplayerstats, leaguedashteamstats with MeasureType='Defense'). Position-by-position opponent stats require joining player position data from the static catalog to game logs -- the endpoint itself does not return "fantasy points allowed to guards." This is a computation the Oracle must perform, not a pre-built field from the API.

**Claim: "RotoWire opp-avg.php breaks out WNBA DvP by Guard/Forward/Center"** -- CONFIRMED by search results. The page exists and has position filters. The data is JS-rendered (confirmed by WebFetch returning loading state).

**Claim: "Her Hoop Stats provides position-specific DvP"** -- NOT CONFIRMED. Her Hoop Stats provides overall defensive ratings and opponent totals but not fantasy-points-per-game-allowed by position bucket. Useful for team-level defensive quality validation only.

**Claim: "The 2026 WNBA defensive rating gap is ~12 points between best and worst team"** -- CONFIRMED by Her Hoop Stats fetch: Minnesota 93.8 vs Connecticut 105.8.

---

## Actionable Conclusions for WNBA Oracle

### 1. Verify Training Corpus DvP State Before Any Serving Fix

Before building position-split DvP, run a diagnostic on the training corpus to check whether `opp_dvp_guard/forward/center` were zero throughout training. If they were, the current heads will not respond to non-zero values -- and populating DvP at serve time will have no projection effect until a retrain occurs with populated DvP columns. Verification: compute feature importance from the pickled LightGBM artifact and check if any DvP column ranks above near-zero. Path: `scripts/` or directly via the artifact's `feature_importance()` method.

### 2. Extend `build_opp_dvp_lookup` to Position-Split Computation

The existing function in `serving_features.py` already computes per-opponent mean real_score allowed. Extend it by:
- Joining player position from the `nba_api` static WNBA catalog (via `get_wnba_players()`, which already exists in `stats_wnba.py`)
- Running `cohort_for_position` on each player's position tag (same function in `spec.py`)
- Grouping by `(opponent, cohort)` and computing mean real_score allowed per cohort
- Returning a `dict[(opponent_abbr, cohort), float]` instead of the current `dict[opponent_abbr, float]`

Then in `job1.py`, split the single `dvp` lookup into three cohort-specific lookups. This is a 30-40 line change across two files.

### 3. Apply Bayesian Shrinkage to DvP Features

Do not use raw means. Apply 10-game-equivalent prior weighting:

```python
prior_games = 10
dvp_shrunk = observed_delta_sum / (observed_games + prior_games)
```

This prevents early-season flukes from distorting the feature. The prior is zero (league average DvP delta) -- which is exactly the current behavior -- so the transition from the existing zero-fill to shrunk DvP is smooth. At game 1, the shrunk value is near zero. At game 40, it is 80% data-driven.

### 4. Pace Features Are Already Populated -- Use Them as Primary Context

The WNBA Oracle spec already carries `team_pace`, `opp_pace`, and `game_pace_implied`. Per the FantasyLabs correlation data, `game_pace_implied` is the highest-signal matchup feature for guards (correlation 0.57 vs pace, 0.41 vs DvP). Since pace features are already non-zero in the live path (populated from `fetch_team_pace_stats` via the `LeagueDashTeamStats Advanced` endpoint), the immediate marginal gain from fixing DvP will be larger for the Forward cohort (where DvP is marginally more useful than pace) than for the Guard cohort (where pace already does most of the work).

### 5. Use a 10-Game Rolling Window via `last_n_games` API Parameter

When fetching team-level defensive data from `leaguedashteamstats`, pass `last_n_games=10` to get recency-weighted defensive figures directly from the API rather than computing rolling windows manually. This is available in both `nba_api` and `wehoop`, and eliminates the need to maintain a separate rolling aggregation pipeline. Cache the result with a 6-hour TTL consistent with `fetch_team_pace_stats`.

### 6. Hard Matchups Should Be Tiebreakers, Not Vetoes

Given the 1.3-point DvP ceiling from the NBA research (likely 0.8-1.1 points in WNBA), the correct role of DvP in the optimizer is as a soft adjustment to projections, not a hard filter. Do not penalize or exclude players solely for hard matchup ratings. The LightGBM model will naturally weight DvP at its true predictive strength once the feature is populated correctly -- which may be modest for forwards and centers. Preserve the projection as the primary signal; DvP adjusts it at the margin.

### 7. Build a Validation Harness After DvP Activation

Once position-split DvP is populated and the model is retrained, validate by computing the walk-forward correlation improvement relative to the current 0.554 figure. The expected gain is modest (DvP is a weak signal) but measurable. Run a separate test checking whether DvP feature importance in the retrained LightGBM artifact exceeds 2% (if below 1%, it is contributing noise, not signal, and should be dropped or the window parameter adjusted).

### 8. Consider RotoWire `opp-avg.php` as a Short-Term Bootstrap

While building the internal position-split DvP pipeline, RotoWire's `opp-avg.php` can be scraped for near-term bootstrap values. It requires a JavaScript-capable scraper (Playwright is available in the WNBA Oracle toolchain already). The scrape would run once per night in Job 1 and inject guard/forward/center DvP values into `features_json` immediately, without waiting for the full pipeline retrain. This is a faster path to non-zero DvP in production, though internal computation from game logs is the correct long-term solution for corpora consistency.

---

## Sources

- [NBA DvP Rankings 2025-26 | Fantasy Team Advice](https://fantasyteamadvice.com/nba/dvp)
- [Defense vs Position (DvP) - NBAstuffer](https://www.nbastuffer.com/analytics101/defense-vs-position/)
- [NBA Defense vs Position | Hashtag Basketball](https://hashtagbasketball.com/nba-defense-vs-position)
- [WNBA Advanced Team Defense Versus Position Matchup Report | LineStar](https://www.linestarapp.com/TeamDefenseReport/Sport/WNBA/Site/DraftKings)
- [WNBA DFS Daily Matchup | LineStar](https://www.linestarapp.com/FantasyDefense/Sport/WNBA/Site/DraftKings)
- [WNBA Stats | Teams Defense](https://stats.wnba.com/teams/defense/)
- [WNBA Stats | Teams Advanced (Pace)](https://stats.wnba.com/teams/advanced/?dir=-1&sort=PACE)
- [2026 WNBA Opponent Averages | RotoWire](https://www.rotowire.com/wnba/opp-avg.php)
- [2026 WNBA Season Summary | Her Hoop Stats](https://herhoopstats.com/stats/wnba/league/2026/)
- [WNBA Statistics and History | Basketball-Reference.com](https://www.basketball-reference.com/wnba/)
- [What's More Important in NBA DFS: Matchup or Pace? | FantasyLabs](https://www.fantasylabs.com/articles/whats-more-important-in-nba-dfs-matchup-or-pace/)
- [The Myth of Matchups and the Prominence of Pace | FantasyLabs](https://www.fantasylabs.com/articles/myth-matchups-prominence-pace-nba/)
- [NBA DFS: How Much Does the Opponent Matter? | RotoGrinders](https://rotogrinders.com/articles/nba-dfs-how-much-does-the-opponent-matter-939677)
- [Defense versus Position (DvP) | RotoGrinders](https://rotogrinders.com/lessons/defense-versus-position-dvp-1165907)
- [NBA DvP Projection Methodology | Quadratic HQ](https://www.quadratichq.com/use-cases/nba-dfs-projections-crafting-accurate-player-values)
- [NBA Stabilization Rates and the Padding Approach | Kostya Medvedovsky](https://kmedved.com/2020/08/06/nba-stabilization-rates-and-the-padding-approach/)
- [How Pace Influences Wins in the WNBA | Bellotti Basketball](https://bellottibasketball.substack.com/p/how-pace-influences-wins-in-the-wnba)
- [Is Defensive Rating a Good Measure of Actual Defensive Ability? | Bruin Sports Analytics](https://www.bruinsportsanalytics.com/post/defensive_rating)
- [NBA Team Ratings: A Bayesian Approach | Matt Fay](https://www.mattefay.com/nba-team-ratings-a-bayesian-approach)
- [LeagueDash Endpoint Documentation | py_ball Wiki](https://github.com/basketballrelativity/py_ball/wiki/LeagueDash)
- [wehoop wnba_leaguedashteamstats | rdocumentation](https://www.rdocumentation.org/packages/wehoop/versions/2.1.0/topics/wnba_leaguedashteamstats)
- [wehoop WNBA Stats Team Functions | GitHub](https://github.com/sportsdataverse/wehoop/blob/main/R/wnba_stats_team.R)
- [nba_api LeagueDashTeamStats | GitHub](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/leaguedashteamstats.md)
- [Per 100 Possessions Calculator | AthletePath](https://www.athletepath.com/per-100-possessions-calculator/)
- [Adjusting NBA Ratings for SOS | Sravan's Blog](https://blog.sradjoker.cc/posts/nba-sosadj/)
- [WNBA Defensive Stats | OddsShark](https://www.oddsshark.com/wnba/defensive-stats)
- [WNBA Team Possessions Per Game | TeamRankings](https://www.teamrankings.com/wnba/stat/possessions-per-game)

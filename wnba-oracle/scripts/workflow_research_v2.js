// Workflow v2: schemaless. Agents write reports to disk and return short
// status strings; the workflow lists expected paths up-front. Re-runnable
// because each agent first checks for an existing report and skips.

export const meta = {
  name: 'win-drafts-gap-analysis-v2',
  description: 'Schemaless rebuild. Why we cant win Real Sports WNBA daily drafts. Internal forensics + players/environment + external best-practice + data science + computer engineering. Adversarial verify on all. Completeness fill. Build-ready synthesis. Research only.',
  phases: [
    { title: 'Internal forensics' },
    { title: 'Players + environment forensics' },
    { title: 'External best-practice' },
    { title: 'Data science methodology' },
    { title: 'Computer engineering' },
    { title: 'Adversarial verify' },
    { title: 'Completeness fill' },
    { title: 'Synthesize build roadmap' }
  ]
}

const REPO = '/Users/hanslarson/Desktop/wnba-oracle'

const SKIP_IF_EXISTS = (path) => `FIRST STEP — check if report already exists. Run: \`wc -l ${path} 2>/dev/null\`. If it prints a line count of 50 or more, the report is already complete; output ONLY the string "SKIP: report already complete at ${path}" and stop. Otherwise proceed to the task below.`

const PROJECT_CONTEXT = `
PROJECT: WNBA Oracle. Automated daily-fantasy picker for the Real Sports app's WNBA contest. Format: pick 5 players, each card has a card_boost (the line they must clear); fantasy real_score is a fixed box formula; slot multipliers are [2.0, 1.8, 1.6, 1.4, 1.2]; large-field GPP (8-13k entries), top-20 paid.
REPO: ${REPO}
PERFORMANCE TO DATE: 1 logged slate at Top 10% / 517th of 8,700 (2026-05-28, partial). 2026-06-04 bust at ~6000th/8317 (cause: D63 heads trained but not wired to job2).
KNOWN FROM PRIOR INTERNAL FORENSICS (already written, do not re-derive — read them if useful):
  - research/internal/01_winners_anatomy.md: winners run median total boost 7.5 (ours 12-15); 60% chalk slot-0; 87% of top-20 game-stack 2+ from one game.
  - research/internal/02_loss_decomposition.md: projection error dominates current loss; ownership/construction secondary.
  - research/internal/03_theoretical_ceiling.md: wiring D63 heads (no new modeling) lifts top-500 rate 33% -> 61%.
  - research/internal/04_boost_economics.md: 2.5-3.0 boost bucket has worst EV; mid-boost 1.5-2.0 sweet spot.
  - research/internal/05_live_input_audit.md: live signal catalog.
  - research/internal/06_field_timing.md: freeze-vs-info timing gap.
DATA AVAILABLE LOCALLY:
  - data/historical/leaderboards/slate_date=YYYY-MM-DD/data.parquet — 141 slates, top-20 lineups. Cols: contest_id, slate_date, entry_id, rank, paged_rank, user_id, score, lineup_json, num_brawlers.
  - data/historical/slate_labels/slate_date=YYYY-MM-DD/data.parquet — card menu. Cols: contest_id, slate_date, section, platform_player_id, display_name, team_key, card_boost, drafts, real_score.
  - data/processed/wnba_game_logs.parquet — 13,456 player-games (2024-05-03 to 2026-06-06). Cols: game_date, player_id, player_name, team, opponent, home_away, game_id, min, pts, reb, oreb, dreb, ast, stl, blk, tov, fgm, fga, fg3m, ftm, fta, season.
  - data/processed/training_corpus.parquet — 4002 rows.
TOOLING: \`uv run python\`. pandas available. WebSearch / WebFetch available.
OUTPUT RULES: markdown file at the path specified. Cite specific players/dates/numbers. Tables encouraged. No em dashes. Distinguish [verified] from [reasoned]. Be concrete and surprising over comprehensive and bland.
`

const EXTERNAL_CONTEXT = `
CONTEXT: Researching daily-fantasy strategy for the Real Sports WNBA contest. Format: pick 5 players, each with a multiplier card (0.5x-5x), large-field GPP (8-13k entries), top-20 paid. Closest analog: PrizePicks, Underdog Pick'em, Sleeper pick-em. Less analog: DraftKings/FanDuel salary cap.
OUR GOAL: find what 2024-2026 best-practice DFS strategy says. Cite URLs. Distinguish well-established vs experimental. Call out pick-em vs salary-cap differences. Flag sources older than 2023 as potentially stale. Cite concrete numbers / formulas where sources give them. No em dashes.
`

const DS_CONTEXT = `
CONTEXT: Researching MODERN DATA-SCIENCE / STATISTICAL-MODELING METHODOLOGY for improving our WNBA daily-fantasy projection model. Our current model decomposes E[real_score] = E[minutes] x E[per-min rate] using multi-task gradient-boosted heads (D63). Walk-forward corr 0.554. P10-P90 coverage 0.81.
FACTS: Target real_score (fantasy points). Features: minutes, per-min rates, opponent, home/away, season, vegas total, vegas spread, recent form. 13,456 training rows 2024-2026. Output: point estimate then post-hoc sigma. Issues: low tail-event calibration, no formal uncertainty intervals, no regime-change handling, no causal handling of minutes-capped games.
OUTPUT RULES: markdown. Cite arxiv/github URLs. Concrete formulas/equations. Quote specific results. Note implementation difficulty. No em dashes.
`

const CE_CONTEXT = `
CONTEXT: Researching MODERN INFRASTRUCTURE PATTERNS for the production WNBA Oracle picker. Architecture: Railway-hosted cron jobs (job1 daily 13:00 UTC, job2 every 15min 21:00-04:00 UTC), Postgres + Redis, Python uv. Brute-force C(top-30, 5) optimizer under Monte Carlo sampling (D56 capped sample/field counts to finish in 15-min cron window).
PAIN POINTS: 15-min cron window forces optimizer compromises. Freeze not idempotent (NEEDS_HUMAN #8). Watchdog stub (NEEDS_HUMAN #9). RotoWire fetched but not persisted (NEEDS_HUMAN #7). Late info (confirmed starters, late inactives) arrives AFTER our 21:00 UTC freeze.
OUTPUT RULES: markdown. Cite docs/repos. Concrete patterns + code sketches. Compare options on prod-readiness, cost, latency, complexity. No em dashes.
`

const PE_CONTEXT = `
CONTEXT: Same WNBA Oracle project. The OPERATOR specifically called out that our prior forensics over-focused on lineup SHAPE (multipliers, stacks, ownership) and under-focused on WHO winners pick and the ENVIRONMENT around those picks. A winning lineup is a story about specific players in specific situations. Mine the 141 historical slates and external context (news, vegas) to surface patterns: which players keep winning, what's happening AROUND those picks (teammate injuries, matchups, schedule spots, vegas footprint, news that day, narrative spots, recent form).
DATA: Same as PROJECT_CONTEXT (game logs, leaderboards, slate_labels). WebSearch/WebFetch for historical news.
OUTPUT RULES: markdown. Cite players, dates, numbers. Tables. URLs for external context. No em dashes.
`

// =====================================================================
// STREAM DEFINITIONS
// =====================================================================

const INTERNAL_STREAMS = [
  { label: 'in-winners-anatomy', path: `${REPO}/research/internal/01_winners_anatomy.md`, ctx: PROJECT_CONTEXT, task: `WINNERS ANATOMY. Across 141 slates rank-1 lineups: score distribution by rank (1, 3, 10, 20), per-pick multiplier distribution, per-pick ownership (drafts/num_brawlers) at rank 1 vs field average, team-stacking %, game-stacking %, slot-1 chalk vs contrarian, position composition. Extrapolate to top-500 from top-20. Headline "to win we need to do X."` },
  { label: 'in-loss-decomposition', path: `${REPO}/research/internal/02_loss_decomposition.md`, ctx: PROJECT_CONTEXT, task: `LOSS DECOMPOSITION. For our frozen lineups (try Postgres frozen_lineups via DATABASE_PUBLIC_URL; else use known slates 2026-05-28, 2026-06-04 + simulate current picker code on a sample of 30 historical slates), decompose loss into (a) projection error, (b) construction error given perfect knowledge, (c) ownership/leverage error, (d) irreducible variance (rank-1 to rank-100 gap). Per-slate table + "% of loss from each bucket."` },
  { label: 'in-theoretical-ceiling', path: `${REPO}/research/internal/03_theoretical_ceiling.md`, ctx: PROJECT_CONTEXT, task: `THEORETICAL CEILING. Brute-force perfect-projection lineup per slate. Compare vs rank-1, rank-20, rank-100. Sweep projection noise (sigma) and simulate 1000 lineup builds per sigma; plot expected finish rank curve. Place our model RMSE on the curve. Compute "perfect projections + perfect ownership-leverage" ceiling.` },
  { label: 'in-boost-economics', path: `${REPO}/research/internal/04_boost_economics.md`, ctx: PROJECT_CONTEXT, task: `BOOST ECONOMICS. Across all 141 slates: card_boost histogram, per-boost-bucket mean real_score, P(real_score >= boost), mean contest contribution (real_score * boost), variance/CoV, position x boost x ownership crosstabs. Sweet spot ranges + traps.` },
  { label: 'in-live-input-audit', path: `${REPO}/research/internal/05_live_input_audit.md`, ctx: PROJECT_CONTEXT, task: `LIVE INPUT AUDIT. Read src/wnba_oracle/{scraper,features,picker,scheduler}. Catalog every input signal the live freeze uses: source, latency, coverage, whether actually consumed. List signals NOT yet captured. Rank by EV impact.` },
  { label: 'in-field-timing', path: `${REPO}/research/internal/06_field_timing.md`, ctx: PROJECT_CONTEXT, task: `FIELD TIMING. Timeline of a typical slate day UTC: card menu published, field draft% fills, confirmed starters land, job1 fires, job2 fires, tipoffs. Gap between best-info-available and what-we-used-at-freeze. Is freeze too early? Could late-freeze strictly dominate?` }
]

const PE_STREAMS = [
  { label: 'pe-winner-player-frequency', path: `${REPO}/research/players_environment/01_winner_player_frequency.md`, ctx: PE_CONTEXT, task: `WINNER PLAYER FREQUENCY + ARCHETYPE. Top 30 most-rostered players in winning lineups (normalized by menu appearances). Archetype classification (star / role / value / rookie). Per-archetype mean real_score in winning vs losing lineups vs season avg. Typical boost in winning lineups per archetype. Players who appear in multiple winning lineups (consistency). Position breakdown.` },
  { label: 'pe-teammate-out-leverage', path: `${REPO}/research/players_environment/02_teammate_out_leverage.md`, ctx: PE_CONTEXT, task: `TEAMMATE-OUT LEVERAGE. For each winning pick, identify which typical starters were ABSENT on that slate's game (compare game log to 10-game-prior starter list). Quantify: % of winning lineups with at-least-one teammate-out pick. Per-min rate boost when teammate absent. Did Real Sports adjust boost to reflect the situation or stay stale?` },
  { label: 'pe-matchup-edge', path: `${REPO}/research/players_environment/03_matchup_edge.md`, ctx: PE_CONTEXT, task: `MATCHUP EDGE. For each winning pick: opponent's 10-game rolling defensive rating allowed to that player's position, opponent pace, days rest, home/away. Do winning picks over-index on weak-defense games? Identify "soft" opponents. Pace exploitation.` },
  { label: 'pe-schedule-spot-edges', path: `${REPO}/research/players_environment/04_schedule_spot_edges.md`, ctx: PE_CONTEXT, task: `SCHEDULE SPOT EDGES. Back-to-back, long rest 3+ days, first home after road trip, last road game, national TV, game time of day, season-phase (first/last 5 games, post-trade-deadline, playoff-push). Correlate each spot with appearing in winning lineup AND over-performance vs season avg. Highest-EV spot archetypes.` },
  { label: 'pe-vegas-environment', path: `${REPO}/research/players_environment/05_vegas_environment.md`, ctx: PE_CONTEXT, task: `VEGAS ENVIRONMENT. Bucket winning picks by Vegas total tier (low/mid/high) and spread (blowout vs competitive). For each game compute realized total = sum of team points, realized margin = spread. Test if winning picks over-index on high-total / competitive games. Identify systematic Vegas mispricings.` },
  { label: 'pe-news-driven-picks', path: `${REPO}/research/players_environment/06_news_driven_picks.md`, ctx: PE_CONTEXT, task: `NEWS-DRIVEN PICKS. Sample 20-30 highest single-player contributions in winning lineups. For each: use WebSearch to find historical news from THAT DAY or prior 24h (sites: rotowire, winsidr, swishappeal, theathletic, espn). Categorize "obvious if you knew the news that morning." Headline % is the upper bound of a better news-ingest pipeline.` },
  { label: 'pe-narrative-spots', path: `${REPO}/research/players_environment/07_narrative_spots.md`, ctx: PE_CONTEXT, task: `NARRATIVE SPOTS. Revenge games, return from injury, contract year, playoff push, Olympic context, coach/system changes, hometown games. For a sample of winning picks, use web search to identify narrative context. Do winning lineups over-index on narrative spots? Detectable from public data?` },
  { label: 'pe-recent-form-momentum', path: `${REPO}/research/players_environment/08_recent_form_momentum.md`, ctx: PE_CONTEXT, task: `RECENT FORM + MOMENTUM. For each winning pick: 3-game, 5-game, 10-game rolling real_score before the slate. Hot/cold/normal bucket. Is winning-pick distribution skewed toward hot streaks, cold (sell-low value), or random? Does Real Sports under- or over-react to recent form in pricing?` }
]

const EXTERNAL_STREAMS = [
  { label: 'ex-gpp-tournament-strategy', path: `${REPO}/research/external/01_gpp_tournament_strategy.md`, ctx: EXTERNAL_CONTEXT, task: `GPP TOURNAMENT STRATEGY 2024-2026. Current best-practice theory for large-field GPP. Ceiling vs floor, correlation, late-swap, contest selection, why expected-points-maximization underperforms in GPPs. Find recent articles, podcasts, papers from RotoGrinders, FantasyPros, Establish The Run, Stokastic, SaberSim blog, Awesemo, DFS subreddits, Twitter DFS analysts.` },
  { label: 'ex-ownership-leverage-math', path: `${REPO}/research/external/02_ownership_leverage_math.md`, ctx: EXTERNAL_CONTEXT, task: `OWNERSHIP / LEVERAGE MATH. How DFS pros quantify and exploit ownership. Leverage scoring, ownership projection, ceiling-weighted leverage, duplicate risk, math of fading chalk in large fields. Concrete formulas. Pick-em vs salary-cap differences.` },
  { label: 'ex-correlation-stacking', path: `${REPO}/research/external/03_correlation_stacking.md`, ctx: EXTERNAL_CONTEXT, task: `CORRELATION + STACKING. Same-team stacks, game stacks, bring-backs. WNBA-specific correlation studies if any. High-total game stacks. Pace-up vs pace-down. Negative correlation patterns.` },
  { label: 'ex-simulation-optimizers', path: `${REPO}/research/external/04_simulation_optimizers.md`, ctx: EXTERNAL_CONTEXT, task: `SIMULATION OPTIMIZERS. SaberSim, Stokastic SIMS, RotoGrinders LineupHQ, Awesemo OWS, FantasyCruncher methodology. How they Monte Carlo + pick lineups that win simulated tournaments. Parameters. Open-source equivalents (pulp, ortools, pydfs-lineup-optimizer, draftfast).` },
  { label: 'ex-ai-ml-projection', path: `${REPO}/research/external/05_ai_ml_projection.md`, ctx: EXTERNAL_CONTEXT, task: `AI/ML PLAYER PROJECTION 2024-2026 SOTA. Feature engineering, ensemble methods, neural approaches, minutes-x-rate decomposition. Papers, repos, blog posts. Anyone publishing serious WNBA model? PrizePicks/Underdog projection methodology?` },
  { label: 'ex-pickem-multiplier-strategy', path: `${REPO}/research/external/06_pickem_multiplier_strategy.md`, ctx: EXTERNAL_CONTEXT, task: `PICK-EM / MULTIPLIER-CARD STRATEGY. PrizePicks, Underdog Pick'em, Sleeper, Real Sports. Multiplier tiers most exploitable, mis-line patterns, operator vig, sharp strategy, correlation across legs. Closest analog to our format.` },
  { label: 'ex-wnba-dfs-specific', path: `${REPO}/research/external/07_wnba_dfs_specific.md`, ctx: EXTERNAL_CONTEXT, task: `WNBA-SPECIFIC DFS. 12-team league, fewer games/night, 40-min games, variable rotations, role-player volatility. Podcasts/articles/blogs on WNBA DFS, known edges, bust patterns (load mgmt, blowouts, rookies). Any backtest results published?` },
  { label: 'ex-late-info-edges', path: `${REPO}/research/external/08_late_info_edges.md`, ctx: EXTERNAL_CONTEXT, task: `LATE INFO EDGES. Where DFS pros get late news, how late you can submit on PrizePicks/Underdog/Real Sports, late-swap strategy. Official APIs for late news. Latency floor for confirmed starters.` },
  { label: 'ex-bankroll-variance', path: `${REPO}/research/external/09_bankroll_variance.md`, ctx: EXTERNAL_CONTEXT, task: `BANKROLL + VARIANCE MATH. Kelly criterion for DFS, optimal % of bankroll per entry, multi-entry vs single-entry, realistic ROI for skilled GPP players, variance over N slates, expected-vs-realized rank distributions.` },
  { label: 'ex-real-sports-community', path: `${REPO}/research/external/10_real_sports_community.md`, ctx: EXTERNAL_CONTEXT, task: `REAL SPORTS COMMUNITY. Search Reddit, Discord, Twitter, YouTube, app reviews for strategy posts, multiplier-setting patterns, contest softness vs sharpness, prize structure analysis, community-reported edges. Verify the actual app name and parent company.` },
  { label: 'ex-vegas-lines', path: `${REPO}/research/external/11_vegas_lines.md`, ctx: EXTERNAL_CONTEXT, task: `VEGAS LINES AS PROJECTION. How DFS pros use team totals, spreads, totals, player props. Converting team total to per-player projection. Spread -> blowout -> minutes redistribution. Player props integration. WNBA prop coverage (DK, FD, Pinnacle, Bovada).` },
  { label: 'ex-submission-timing', path: `${REPO}/research/external/12_submission_timing.md`, ctx: EXTERNAL_CONTEXT, task: `SUBMISSION TIMING + LATE SWAP. Optimal lock time. DK/FD late-swap. Pick-em platforms' late submission rules. Real Sports specifically: when does the lineup lock? Per-player or whole-lineup? Are we burning hours of info?` },
  { label: 'ex-ownership-projection', path: `${REPO}/research/external/13_ownership_projection.md`, ctx: EXTERNAL_CONTEXT, task: `OWNERSHIP PROJECTION METHODOLOGY. How pros project field ownership. Features (chalk, narrative, prime-time, big game). Released ownership data sources. For pick-em formats: does ownership data exist publicly? Can we mine the Real Sports drafts count?` },
  { label: 'ex-prop-arbitrage', path: `${REPO}/research/external/14_prop_arbitrage.md`, ctx: EXTERNAL_CONTEXT, task: `PROP ARBITRAGE. PrizePicks/Underdog set multipliers based on a line. Sharp players arb vs sportsbook lines. Prop-vs-pickem arb, mispriced cards, Crystal Ball tools, scrapers (PropOdds, Outlier, Pikkit). Can we cross-reference Real Sports boosts to sportsbook prop lines?` },
  { label: 'ex-minutes-projection', path: `${REPO}/research/external/15_minutes_projection.md`, ctx: EXTERNAL_CONTEXT, task: `MINUTES PROJECTION SOTA. Best public methodology for projecting minutes (rotation, injury-cascade, game-script, blowout-risk, foul-trouble). Rotowire/Lineups.com models. Academic papers. WNBA-specific (W rotations more volatile).` }
]

const DS_STREAMS = [
  { label: 'ds-quantile-crps', path: `${REPO}/research/data_science/01_quantile_crps_loss.md`, ctx: DS_CONTEXT, task: `QUANTILE REGRESSION + CRPS / PINBALL LOSS. Theory + frameworks (catboost MultiQuantile, lightgbm quantile alpha, ngboost, xgboost-distribution). Monotonicity constraints. CRPS vs RMSE for lineup-construction tournaments.` },
  { label: 'ds-hierarchical-bayes', path: `${REPO}/research/data_science/02_hierarchical_bayes.md`, ctx: DS_CONTEXT, task: `HIERARCHICAL BAYESIAN / MIXED-EFFECTS for player skill. Partial pooling, Stan/PyMC, Empirical Bayes shrinkage. WNBA player-projection case studies. Variance components.` },
  { label: 'ds-embeddings', path: `${REPO}/research/data_science/03_embeddings_latent_factor.md`, ctx: DS_CONTEXT, task: `PLAYER + MATCHUP EMBEDDINGS. Matrix factorization (Bayesian PMF, ALS, NMF), neural CF, tabular transformers (FT-Transformer, SAINT, TabNet), GNNs. Papers, libraries.` },
  { label: 'ds-conformal-prediction', path: `${REPO}/research/data_science/04_conformal_prediction.md`, ctx: DS_CONTEXT, task: `CONFORMAL PREDICTION. Distribution-free coverage. Split conformal, jackknife+, adaptive conformal for time-series, CQR. Libraries (mapie, crepes). Romano/Patel/Tibshirani/Foygel-Barber papers.` },
  { label: 'ds-multitask-architectures', path: `${REPO}/research/data_science/05_multitask_architectures.md`, ctx: DS_CONTEXT, task: `MULTI-TASK LEARNING ARCHITECTURES. Hard vs soft sharing, gradient surgery (GradNorm, PCGrad, CAGrad), uncertainty weighting. Negative transfer. Predict K targets vs single target.` },
  { label: 'ds-online-learning-drift', path: `${REPO}/research/data_science/06_online_learning_drift.md`, ctx: DS_CONTEXT, task: `ONLINE LEARNING + DRIFT DETECTION. River, Mondrian forests, online lightgbm. KSWIN, ADWIN, Page-Hinkley, DDM. Continual learning, replay buffers, JIT retraining. Player role-change detection.` },
  { label: 'ds-causal-counterfactual', path: `${REPO}/research/data_science/07_causal_counterfactuals.md`, ctx: DS_CONTEXT, task: `CAUSAL INFERENCE / COUNTERFACTUAL PROJECTION. Counterfactual minutes for capped games. Matching, propensity scores, IV, CATE via causal forests (econML, DoWhy). Inverse propensity weighting.` },
  { label: 'ds-time-series-state-space', path: `${REPO}/research/data_science/08_time_series_state_space.md`, ctx: DS_CONTEXT, task: `MODERN TIME-SERIES for per-min rate. State-space (Kalman, particle filters), GPs for irregular spacing, LSTM/GRU, transformer-based (PatchTST, TimesNet, Chronos, Lag-Llama, TimesFM). Best fit for 100-game-history-per-player.` },
  { label: 'ds-bayesian-optimization', path: `${REPO}/research/data_science/09_bayesian_optimization_lineup.md`, ctx: DS_CONTEXT, task: `BAYESIAN OPTIMIZATION / THOMPSON SAMPLING for lineup construction. Combinatorial bandits, MCTS, BO over discrete spaces (optuna, hyperopt, BoTorch), portfolio theory (mean-variance, CVaR for GPP).` },
  { label: 'ds-feature-engineering-sota', path: `${REPO}/research/data_science/10_feature_engineering_sota.md`, ctx: DS_CONTEXT, task: `FEATURE ENGINEERING SOTA. Rolling-window (EWMA, rolling quantiles), opponent-adjusted (RAPM, BPM, EPM), play-by-play features (synergy, on/off), tracking-data (Second Spectrum, Stats Perform), schedule-adjusted, Vegas-derived. WNBA tracking data sources. Feature stores.` }
]

const CE_STREAMS = [
  { label: 'ce-event-driven-pipelines', path: `${REPO}/research/computer_engineering/01_event_driven_pipelines.md`, ctx: CE_CONTEXT, task: `EVENT-DRIVEN PIPELINES alternatives to cron. Temporal, Inngest, Trigger.dev, Restate, Hatchet. AWS EventBridge+Lambda, Cloudflare Workers+Queues, GCP Pub/Sub+Cloud Run. React to "slate posted" / "starters confirmed" within seconds. Hybrid cron+event patterns.` },
  { label: 'ce-low-latency-scraping', path: `${REPO}/research/computer_engineering/02_low_latency_scraping.md`, ctx: CE_CONTEXT, task: `LOW-LATENCY SCRAPING. HTTP/2 pooling, async batching (aiohttp, httpx), proxy rotation, headless-browser pools (playwright, browserless), CDN bypass, exponential backoff w/ jitter, dynamic concurrency, ETag/If-Modified-Since polling.` },
  { label: 'ce-model-serving-feature-store', path: `${REPO}/research/computer_engineering/03_model_serving_feature_store.md`, ctx: CE_CONTEXT, task: `MODEL SERVING + FEATURE STORE. BentoML, MLflow, Modal, Ray Serve, Triton. Online feature stores (Feast, Tecton, Hopsworks, Chalk). Point-in-time correctness, online/offline parity. Right scale for ~500 players / ~50 features.` },
  { label: 'ce-gpu-monte-carlo', path: `${REPO}/research/computer_engineering/04_gpu_monte_carlo.md`, ctx: CE_CONTEXT, task: `GPU MONTE CARLO. cupy, JAX, numba.cuda, taichi. Batched sampling, vectorized lineup scoring. Cloud GPU (Modal, Replicate, Lambda Labs, Vast.ai). Cost vs latency for 1M samples x C(60,5).` },
  { label: 'ce-combinatorial-optimization', path: `${REPO}/research/computer_engineering/05_combinatorial_optimization.md`, ctx: CE_CONTEXT, task: `COMBINATORIAL OPTIMIZATION beyond brute-force. MILP (PuLP, OR-Tools, Gurobi, CPLEX), beam search, evolutionary (DEAP), simulated annealing, Lagrangian relaxation, column generation. Ownership-aware, correlation-aware, portfolio-of-lineups.` },
  { label: 'ce-observability-drift', path: `${REPO}/research/computer_engineering/06_observability_drift.md`, ctx: CE_CONTEXT, task: `ML OBSERVABILITY + DRIFT MONITORING. Evidently AI, Arize, WhyLabs, Fiddler, Aporia. Great Expectations, Soda, Monte Carlo Data. Calibration-drift alerts. Detect real_score MAE regression within hours.` },
  { label: 'ce-scheduling-cron', path: `${REPO}/research/computer_engineering/07_scheduling_cron.md`, ctx: CE_CONTEXT, task: `ROBUST SCHEDULING + CRON ALTERNATIVES. Temporal cron, GitHub Actions schedule, AWS EventBridge Scheduler, Prefect, Airflow, Dagster, Mage. Idempotent task patterns (dedup keys, SETNX). Heartbeat (Dead Man's Snitch, Cronitor, healthchecks.io).` },
  { label: 'ce-realtime-frontend-push', path: `${REPO}/research/computer_engineering/08_realtime_frontend_push.md`, ctx: CE_CONTEXT, task: `REAL-TIME FRONTEND PUSH. WebSockets, SSE, Ably/Pusher/Supabase Realtime/Liveblocks. Push lineup-froze event in 100ms, push live in-game scoring without re-polling. Behind Cloudflare/Railway.` }
]

const ALL_STREAMS = [...INTERNAL_STREAMS, ...PE_STREAMS, ...EXTERNAL_STREAMS, ...DS_STREAMS, ...CE_STREAMS]

// =====================================================================
// PHASE FAN-OUT
// =====================================================================

function runStreamPhase(streams, phaseTitle) {
  return parallel(streams.map(s => () => agent(
    `${s.ctx}\n\n=== YOUR TASK ===\n\n${SKIP_IF_EXISTS(s.path)}\n\n${s.task}\n\nWrite your full report to exactly this path: ${s.path}\nUse the Write tool. The report must be detailed (target 200-500 lines of dense, cited markdown). When done, return only the literal string "DONE: ${s.path}". The orchestrator does not need any other content from you in chat — the file IS the deliverable.`,
    { label: s.label, phase: phaseTitle }
  )))
}

phase('Internal forensics')
const internalReturns = await runStreamPhase(INTERNAL_STREAMS, 'Internal forensics')
log(`Internal forensics: ${internalReturns.filter(Boolean).length}/${INTERNAL_STREAMS.length} agent runs returned`)

phase('Players + environment forensics')
const peReturns = await runStreamPhase(PE_STREAMS, 'Players + environment forensics')
log(`Players+environment: ${peReturns.filter(Boolean).length}/${PE_STREAMS.length}`)

phase('External best-practice')
const exReturns = await runStreamPhase(EXTERNAL_STREAMS, 'External best-practice')
log(`External: ${exReturns.filter(Boolean).length}/${EXTERNAL_STREAMS.length}`)

phase('Data science methodology')
const dsReturns = await runStreamPhase(DS_STREAMS, 'Data science methodology')
log(`Data science: ${dsReturns.filter(Boolean).length}/${DS_STREAMS.length}`)

phase('Computer engineering')
const ceReturns = await runStreamPhase(CE_STREAMS, 'Computer engineering')
log(`Computer engineering: ${ceReturns.filter(Boolean).length}/${CE_STREAMS.length}`)

// =====================================================================
// PHASE 6 — ADVERSARIAL VERIFY
// =====================================================================
phase('Adversarial verify')

const verifyDir = `${REPO}/research/verify`

const verifyReturns = await parallel(ALL_STREAMS.map(s => () => agent(
  `You are an ADVERSARIAL REVIEWER. Read the research report at: ${s.path}

Then write a verdict file to: ${verifyDir}/${s.label}.verdict.md

Your job: try to REFUTE the claims in the report. Default to "refuted" if uncertain. Look for:
  - Cherry-picked numbers (re-run any computation you can with the data at ${REPO}/data/)
  - Sources that don't say what's claimed (fetch URLs and verify the quote matches)
  - Logic errors (selection bias, survivorship bias, in/out-of-sample confusion)
  - Claims that contradict basic DFS theory or statistics
  - Outdated sources (pre-2023)
  - Salary-cap logic misapplied to pick-em format
  - Numbers that are dimensionally wrong (e.g. real_score values implausible)

Structure of your verdict file:
  # Verdict on ${s.label}
  ## Overall: HOLDS | MOSTLY HOLDS | PARTIALLY HOLDS | DOES NOT HOLD
  ## Findings (one section per claim in the original report)
    - claim: <copy from report>
    - verdict: confirmed | partially confirmed | refuted | unverifiable
    - reasoning: <evidence, with re-computed numbers / quoted source URLs if you fetched>
  ## Additional concerns (anything the original missed)

Skip-if-exists: if ${verifyDir}/${s.label}.verdict.md exists with >20 lines, output only "SKIP: verdict already exists" and stop.

When done, return only the literal string "DONE: ${verifyDir}/${s.label}.verdict.md".`,
  { label: `verify-${s.label}`, phase: 'Adversarial verify' }
)))

log(`Verify: ${verifyReturns.filter(Boolean).length}/${ALL_STREAMS.length}`)

// =====================================================================
// PHASE 7 — COMPLETENESS FILL
// =====================================================================
phase('Completeness fill')

// Single critic agent identifies gaps and writes deep-dive fill reports directly to disk.
const completenessReturn = await agent(
  `You are the COMPLETENESS CRITIC + FILL writer. The goal: explain why we cant win Real Sports WNBA daily drafts and what to do about it.

So far ${ALL_STREAMS.length} research reports + ${ALL_STREAMS.length} adversarial verdicts have been written across:
  ${REPO}/research/internal/
  ${REPO}/research/players_environment/
  ${REPO}/research/external/
  ${REPO}/research/data_science/
  ${REPO}/research/computer_engineering/
  ${REPO}/research/verify/

Step 1: read every report (use \`ls\` then \`Read\` for each).

Step 2: identify the top 5-8 CRITICAL GAPS — topics that should have been researched in depth to fully answer "why can't we win" but were not, OR claims that were refuted by verifiers and need a re-derivation, OR cross-cutting analyses (e.g. correlation between internal findings and external best-practice).

Step 3: write a deep-dive fill report for EACH gap. Each fill report goes to ${REPO}/research/fill/{kebab-case-label}.md and should be 100-300 lines of dense markdown, citing specific reports and adding new analysis.

Step 4: write a meta-index at ${REPO}/research/fill/00_completeness_index.md listing every fill report and why it was written.

When done, return "DONE: completeness fill written to ${REPO}/research/fill/" with a count.`,
  { label: 'completeness-critic-and-fill', phase: 'Completeness fill' }
)

log(`Completeness fill: ${completenessReturn ? 'done' : 'failed'}`)

// =====================================================================
// PHASE 8 — SYNTHESIZE BUILD ROADMAP
// =====================================================================
phase('Synthesize build roadmap')

const synthesisReturn = await agent(
  `You are the FINAL SYNTHESIST. ${ALL_STREAMS.length}+ research reports have been produced across:
  ${REPO}/research/internal/ (forensics on our 141 slates + frozen lineups)
  ${REPO}/research/players_environment/ (WHO winners pick + ENVIRONMENT around the pick)
  ${REPO}/research/external/ (2026 DFS best-practice sweep)
  ${REPO}/research/data_science/ (statistical / ML methodology)
  ${REPO}/research/computer_engineering/ (infra patterns)
  ${REPO}/research/verify/ (adversarial verdicts on every report)
  ${REPO}/research/fill/ (completeness fills)

CRITICAL: This synthesis is the input to an AUTONOMOUS BUILD AGENT that will execute on the top recommendations WITHOUT human intervention. Your synthesis must be specific enough that a competent engineer reading it can start building the #1 recommendation immediately without re-reading the source reports.

Step 1: \`ls\` every research subdirectory and \`Read\` every report (including verdicts).

Step 2: write your synthesis to ${REPO}/research/00_GAP_ANALYSIS.md with this structure:

  1. EXECUTIVE SUMMARY (1 paragraph + 5 bullet headlines)
  2. THE GAP, DECOMPOSED — projection error vs construction error vs ownership/leverage error vs late-info gap vs player-environment-information gap vs irreducible variance. Cite the loss decomposition + theoretical ceiling numbers.
  3. WHAT WINNERS ACTUALLY DO — synthesized from winners' anatomy + players_environment + external best-practice. Concrete patterns: WHO they pick, WHAT environment those picks come from, HOW they build the lineup around them.
  4. WHERE WE ARE BLEEDING EV — ranked list of specific failure modes (each with: estimated EV cost per slate, source report citations, confidence, the specific observable we'd see if we fixed it).
  5. PRIORITIZED BUILD ROADMAP — top 8-12 things to BUILD next, ranked by EV/effort. For EACH item:
     a. Title (one line, action verb).
     b. EV estimate (per slate, with confidence band).
     c. Effort estimate (S/M/L).
     d. Concrete implementation outline (files in src/wnba_oracle/ to touch, data sources to wire, new features/models/infra).
     e. Acceptance test (backtest gate, unit test, metric to move).
     f. Dependencies.
     g. Risk.
     First 3 items MUST be ship-in-a-day scope. The rest can be larger.
  6. PLAYER + ENVIRONMENT PLAYBOOK — distilled from players_environment phase. Per-slate cheat sheet: who keeps winning, what environment, what to fade.
  7. OPEN QUESTIONS — what we still don't know.
  8. WEAK LINKS — refuted findings + why we included or excluded them.

Be specific, empirical, cite numbers + report paths. Reconcile disagreements between reports in text. Mark [verified] vs [reasoned].

When done, return "DONE: ${REPO}/research/00_GAP_ANALYSIS.md".`,
  { label: 'synthesis-build-roadmap', phase: 'Synthesize build roadmap' }
)

log(`Synthesis: ${synthesisReturn ? 'done' : 'failed'}`)

return {
  ok: true,
  report_count: ALL_STREAMS.length,
  synthesis_path: `${REPO}/research/00_GAP_ANALYSIS.md`,
  verify_dir: verifyDir,
  fill_dir: `${REPO}/research/fill`
}

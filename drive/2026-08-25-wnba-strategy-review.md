# WNBA Oracle Strategy Review
Created: 2026-08-25
Session: cheeksmagunda-wnba-oracle-2026-08-25-skills-strategy

---

## Phase 2: Data-Store and Data-Flow Audit

### 2.1 GitHub (`cheeksmagunda/sports`, `main`)

What lives here:
- Source for all packages (`packages/oracle-core`, `wnba-oracle`)
- GitHub Actions workflows: backend CI, provider contracts, corpus backup,
  watchdog monitor, pre-freeze checks, day-close verification
- Model artifact identity: SHA pinned in `STATUS.md`
  (`picker_e2ced9ec_1780873338.pkl`, SHA `94f8e860...`)
- `migrations/versions/` -- the migration set that defines the Postgres schema
- `drive/` -- operator briefs and working reviews (non-canonical, informational)

Must never be committed:
- `storage_state` (browser session files, require mode 0600, atomic writes)
- Secrets, tokens, credential files
- Local parquet, `data/`, `runs/`, `models/` (gitignored)
- `.env` / `.envrc`

### 2.2 Railway App Services

| Service | Reads | Writes |
|---------|-------|--------|
| `api` | Postgres (slate_meta, frozen_lineups, slate_labels) | None |
| `frontend` | API HTTP | None |
| `job1` | Real Sports (WNBA pool + contest), Odds API, RotoWire | Postgres (player_pool, slate_meta, player_features) |
| `job1-late` | Real Sports (late starters), RotoWire | Postgres (player_features update -- starter flags) |
| `job2` | Postgres (player_pool, player_features, slate_meta), Redis (lease), model artifact | Postgres (frozen_lineups, model_shadow_runs), Redis (release) |
| `day-close` | Postgres (frozen_lineups, player_pool), Real Sports (final scores) | Postgres (slate_labels, wnba_game_logs, contest_placements) |
| `backfill` | Real Sports historical, nba_api | Postgres (wnba_game_logs, player_pool history) |

Source verified against: `scheduler/job1.py`, `scheduler/job2.py`,
`scheduler/job_dayclose.py`, `scheduler/job_backfill.py`, `db/reads.py`,
`db/engine.py`.

### 2.3 Railway Postgres -- Tables and Grains

| Table | Grain | Append-only | Owner |
|-------|-------|-------------|-------|
| `player_pool` | player x slate_date | No (enriched by job1) | job1 |
| `player_features` | player x slate_date | No (updated by job1-late) | job1/job1-late |
| `slate_meta` | slate_date | No (updated by job1) | job1 |
| `frozen_lineups` | slate_date x sequence | YES | job2 |
| `slate_labels` | player x slate_date | No (written by dayclose) | dayclose |
| `wnba_game_logs` | player x game_date | No (backfilled) | dayclose/backfill |
| `contest_leaderboards` | slate_date x place | No | dayclose |
| `contest_placements` | slate_date | No | dayclose |
| `model_shadow_runs` | slate_date x challenger_sha | Upsert, realized_delta backfilled | job2/dayclose |
| `job_runs` | job x run_id | Append | job runtime hook |

`frozen_lineups`: append-only invariant enforced in migration `20260610_0006`
and documented in `AGENTS.md`. Re-freeze appends a new sequence; never
rewrites.

### 2.4 Railway Redis

Verified from `scheduler/job2_timing.py` and `scheduler/job2.py`:
- Distributed lease to prevent double-freeze on concurrent job2 invocations
- Released after freeze write; never read by the API
- Not serving state; confirmed Postgres-only serving confirmed in `api/slate.py`
  and `api/lineup.py`

Redis is NOT the source of truth for any player, lineup, or label data.

### 2.5 GitHub Actions as Data Path

| Workflow | Data path |
|---------|-----------|
| Backend CI | Runs tests; no durable data written |
| Corpus backup | Exports Postgres to JSON on `backups` branch (read-only corpus, not runtime) |
| Watchdog monitor | Reads API `/watchdog/today`; writes GitHub check or issue |
| Pre-freeze check | Reads Postgres / API; writes GitHub check |
| Day-close verify | Reads Postgres; writes GitHub check |
| Provider contracts | Calls provider adapters; validates response shape |

The `backups` branch holds historical corpus JSON exports. It is not runtime
state, not canonical production state. STATUS.md pins the artifact SHA and
commit SHA. Those are canonical identity; the backup JSON is for offline
analysis and retraining.

### 2.6 Local and Ignored Paths

| Path | Status |
|------|--------|
| `data/` | Non-canonical. Local parquet, interim exports. gitignored. |
| `runs/` | Non-canonical. Script outputs, sweep results. gitignored. |
| `models/` | Non-canonical. Local artifact copies. gitignored. Pin only the SHA in STATUS. |
| `wnba-oracle/.secrets/` | Optional SOPS encrypted env. gitignored, mode 0700. |

### 2.7 Corrected Data Flow

```
providers (Real Sports, Odds API, RotoWire)
    -> job1/job1late -> Postgres (player_pool, player_features, slate_meta)
    -> job2 -> Redis (lease coordination)
            -> Postgres (frozen_lineups, model_shadow_runs)
    -> api reads Postgres only (frozen_lineups, slate_meta)
    -> dayclose -> Postgres (slate_labels, wnba_game_logs, contest_placements)
                -> model_shadow_runs.realized_value_delta backfill
    -> GitHub backups branch (corpus JSON export, non-runtime)
    -> STATUS.md (artifact SHA pin, commit SHA pin)
```

No fourth store. Local paths are non-canonical.

---

## Phase 3: Strategy Review

### Source Inventory and Classification

**Sources fetched:**

| # | URL | Outcome | Classification |
|---|-----|---------|----------------|
| 1 | mcpmarket.com/tools/skills/sports-data-agent | 404/paywall | Rejected: no content |
| 2 | github.com/machina-sports/sports-skills | Fetched | Kind 1 workflow skill raw material (wnba-data skill, ESPN-based) |
| 3 | sports-skills.sh | Fetched | Confirms machina-sports skills structure; no additional content |
| 4 | mcpmarket.com/tools/skills/api-sports-data-statistics | Not fetched | Skip: MCP market index, no raw skill content reachable |
| 5 | skillsllm.com/skill/claude-sports-analytics | Fetched | Legal disclaimer only; no actual skill content |
| 6 | skillsllm.com/compare/claude-sports-analytics-vs-sports-skills | Fetched | Tag list only; no content |
| 7 | skillsllm.com/compare/claude-sports-analytics-vs-ui-ux-pro-max-skill | Not fetched | Skip: tag comparison, no sports substance |
| 8 | sinankprn.com/posts/enhancing-sporting-organisation-efficiency | Fetched | Kind 2 strategy: AI workflow design, prompt quality, RAG for org decisions |
| 9 | sportscienceai.com/en/posts/top-5-tools-for-sports-scientists-in-2025 | Fetched (title only) | Skip: landing page, no substance |
| 10 | ijfmr.com/papers/2023/4/5657.pdf | Not fetched (PDF) | Skip: performance analysis theory, not actionable for daily draft |
| 11 | isspf.com/articles/beginners-guide-to-performance-analysis | 403 | Miss: domain blocked |
| 12 | uksportsinstitute.co.uk/service/performance-analysis | Not fetched | Skip: general org; no daily draft substance |
| 13 | longomatch.com/en/top-5-skills-every-aspiring-sports-analyst | Fetched | Kind 2: confirms stat interpretation, tactical context, communication as key skills |
| 14 | wnba.com/stats/inside-the-game | 403 | Miss: domain blocked |
| 15 | wnba.com/news/category/analysis | Not fetched | Skip: news feed, no structural content |
| 16 | databallr.com/wnba | Fetched (title only) | Skip: analytics/impact metrics tool, no reachable content |
| 17 | herhoopstats.com | Fetched | Confirms AI/ML-powered WNBA query interface; no skill content |

**Key extractable substance:**

From machina-sports/sports-skills (source 2 / wnba-data SKILL.md):
- ESPN public endpoints for scoreboard, standings, rosters, schedules, box scores,
  play-by-play, injuries, transactions, futures, leaders, stats
- Season logic: May-Oct = current year; Nov-Apr = previous year
- 16 commands structured as reusable workflow steps
- Source data: ESPN only (not canonical for our product; Real Sports is)
- Verdict: Rewrite as a WNBA Oracle operator workflow for slate review using
  the Postgres store, not ESPN. ESPN data is diagnostic, not production.

From sinankprn.com (source 8):
- Workflow automation (n8n, Make, Zapier pattern) = our job pipeline is already
  this; confirmed correct architecture
- "Prompt quality" principle maps to: our skills should be explicit about which
  store holds each data type (no "fetch live scores" when Postgres has them)
- RAG / retrieval pattern: relevant for slate review skill (query Postgres,
  interpret, recommend)

From longomatch.com (source 13):
- Statistical analysis + tactical context + communication: our archetypes,
  stat_leverage, streak_quality modules already implement this; gap is
  operator-facing workflow to surface them clearly

### 3.1 Hierarchy Review

**Current hierarchy:**
```
api/ assurance/ ingest/ features/ train/ predict/ picker/ scheduler/ db/ modeling/
```

`source: machina-sports/sports-skills (wnba-data structure)`
`code: wnba_oracle package tree`
`store: Postgres (canonical), Redis (coordination)`

**Finding:** The seam between `modeling/` (kernel) and `scheduler/` (orchestration)
is correct and clean. `modeling/scoring.py` has no DB/Redis/HTTP imports; the seam
is enforced.

**Finding:** `predict/archetypes.py`, `predict/stat_leverage.py`,
`predict/streak_quality.py` exist and are well-factored but are NOT surfaced in
any operator-callable workflow or API endpoint. The archetype labels are written to
freeze metadata per the docstring, but there is no skill for the operator to review
what archetypes look like for an upcoming slate.

`gap: archetype/streak data is computed but not operator-accessible as a workflow`
`action: add-workflow-skill`
`implement-now: yes -- the code exists; the skill is a wrapper on Postgres reads`

**Finding:** No `skills/` directory exists in `wnba-oracle`. All operator/agent
procedures (how to review a slate, how to shadow a knob, how to read the backup
branch, how to run the research scripts) exist only in `AGENTS.md` and code
comments, not as structured callable workflows.

`gap: no SKILL.md files for operator workflow automation`
`action: add-workflow-skill`
`implement-now: yes`

**Finding:** Hierarchy is otherwise sound. `oracle-core` is correctly limited to
provider-neutral infrastructure. No cross-league imports. Dependency direction
is clean.

`action: configure-existing (no restructure needed)`

### 3.2 Feature Review

**starter_unknown_fade (calibrated 2026-07-04):**
`source: scripts/calibrate_starter_and_boost.py results in policy.py docstring`
`code: modeling/scoring.py:_starter_multiplier, policy.py:starter_unknown_fade`
`store: player_features.features_json (rotowire_confirmed, is_starter)`
`gap: default is 1.0 (neutral) but calibration shows 0.75 matches empirical`
`action: change-default`
`implement-now: yes -- STARTER_UNKNOWN_FADE default should be 0.75 in settings.py`

**game_script_minutes_enabled (currently False):**
`source: policy.py, features/game_script_minutes.py`
`code: policy.py:game_script_minutes_enabled = False`
`store: player_features.features_json (vegas_total, vegas_spread)`
`gap: feature exists but is disabled; no evidence it was calibrated against prod`
`action: configure-existing -- leave disabled, add operator note`
`implement-now: no -- needs calibration evidence first`

**availability_model_enabled (currently False):**
`source: predict/availability.py, policy.py`
`code: policy.py:availability_model_enabled = False`
`gap: same as above -- feature exists, no prod calibration evidence`
`action: configure-existing -- leave disabled`
`implement-now: no`

**stat_leverage_score / streak_quality / archetypes:**
`source: predict/stat_leverage.py, predict/streak_quality.py, predict/archetypes.py`
`code: all three modules exist and are imported by job2_model.py (inferred from imports)`
`store: frozen_lineups.payload_json (archetype labels written at freeze per docstring)`
`gap: no workflow skill to surface these for operator review pre-freeze`
`action: add-workflow-skill`
`implement-now: yes`

**prop_signal_scale (currently 0.0):**
`source: policy.py:prop_signal_scale = 0.0`
`code: modeling/scoring.py:_prop_signal_multiplier`
`store: player_features.features_json (prop lines from Odds API)`
`gap: disabled; no calibration evidence present`
`action: configure-existing -- leave at 0.0`
`implement-now: no`

**ceiling_sigma_blowout_boost / ceiling_sigma_low_history_boost (both 0.0):**
`source: policy.py`
`code: optimizer uses these for ceiling tilt`
`store: player_features (sigma estimates)`
`gap: disabled pending calibration`
`action: configure-existing -- leave at 0.0`
`implement-now: no`

### 3.3 Knob Review

**STARTER_UNKNOWN_FADE:**
`source: scripts/calibrate_starter_and_boost.py -- unknowns realize 0.685x mean, DNP 5.8% vs 0.6%`
`code: settings.py -- starter_unknown_fade field present; default in Settings not found (defaults via ModelPolicy = 1.0)`
`gap: ModelPolicy.starter_unknown_fade defaults to 1.0 but calibration says 0.75`
`action: change-default -- change Settings default for STARTER_UNKNOWN_FADE to 0.75`
`implement-now: yes`
`rollback: set STARTER_UNKNOWN_FADE=1.0 in Railway env; no redeploy needed`
`shadow-path: PICKER_KNOB_CHALLENGER_JSON={"starter_unknown_fade": 1.0} to A/B against new default`

**PICKER_FLOOR_TILT_WEIGHT / PICKER_FLOOR_TILT_MAX_BOOST:**
`source: policy.py defaults (0.0 / 2.0)`
`code: modeling/scoring.py:_floor_tilt_multiplier; shadow_knobs.py:floor_tilt_weight`
`gap: shadow infrastructure exists but no workflow skill documents how to activate`
`action: add-workflow-skill (document the shadow path)`
`implement-now: yes (as skill, no code change)`

**New knob: STARTER_UNKNOWN_FADE via Settings:**
Already exists as `starter_unknown_fade` in `ModelPolicy`. Need to verify it
flows from `Settings` into `ModelPolicy`. If the settings field is missing,
add it.

**OPTIMIZER_LEVERAGE_WEIGHT / OPTIMIZER_CEILING_WEIGHT:**
`source: .env.example (both present)`
`code: picker/optimize.py (need to verify they are read from Settings -> ModelPolicy)`
`action: configure-existing -- verify wiring; document in skill`

### 3.4 Implement-Now Set (summary)

| Item | Type | Location |
|------|------|----------|
| Change `starter_unknown_fade` default to 0.75 in Settings | change-default | `common/settings.py` |
| Create `skills/` directory with 5 workflow SKILL.md files | add-workflow-skill | `wnba-oracle/skills/` |
| Skill: `slate-review` | add-workflow-skill | `wnba-oracle/skills/slate-review/SKILL.md` |
| Skill: `knob-shadow` | add-workflow-skill | `wnba-oracle/skills/knob-shadow/SKILL.md` |
| Skill: `strategy-gap` | add-workflow-skill | `wnba-oracle/skills/strategy-gap/SKILL.md` |
| Skill: `corpus-status` | add-workflow-skill | `wnba-oracle/skills/corpus-status/SKILL.md` |
| Skill: `ops-runbook` | add-workflow-skill | `wnba-oracle/skills/ops-runbook/SKILL.md` |
| Add `STARTER_UNKNOWN_FADE` to `.env.example` description | configure-existing | `wnba-oracle/.env.example` |

**Rejected items:**
- ESPN live-score MCP wrapper: reject. Real Sports is authoritative for this product.
- Video analysis / video tagging: reject. Not a daily-draft feature.
- Generic sport-agent "fetch live scores and answer": reject. Rewritten onto Postgres store.
- machina-sports SKILL.md verbatim copy: reject per brief.
- game_script_minutes_enabled default change: reject pending calibration.
- availability_model_enabled default change: reject pending calibration.

---

## Checkpoint: 2026-08-25 Phase 2+3 complete

Next: Phase 4 implementation (settings default change + 5 SKILL.md files).

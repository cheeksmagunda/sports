# File manifest (generated, do not hand-edit)

Generated from `git ls-files`. 800 tracked files. Regenerate with `scripts/generate_file_manifest.py`.

## (repo root)
- .agent.md -- Sports Oracle Portfolio Instructions
- .dockerignore
- .env.example
- .gitignore
- .gitleaks.toml -- Package/tool configuration
- .gitleaksignore
- .sops.yaml
- AGENTS.md -- Sports Oracle Portfolio Instructions
- APPLICATION_GUIDE.md -- Adding a sport application
- BENCHMARK_TASK.md -- Model Research Benchmark Workflow - Continuation Task
- CLAUDE.md -- Sports Oracle Portfolio Instructions
- CONTRIBUTING.md -- Contributing to Sports Oracle
- ENTRY_POINTS.md -- Entry Points Reference
- FILES.md -- File manifest (generated, do not hand-edit)
- Makefile -- Build/test/lint entrypoints
- OVERVIEW.md -- Sports Oracle: Portfolio Overview
- README.md -- Sports Oracle
- pyproject.toml -- Package/tool configuration
- uv.lock -- Locked dependency graph

## .devcontainer/
- .devcontainer/Dockerfile
- .devcontainer/devcontainer-lock.json
- .devcontainer/devcontainer.json
- .devcontainer/docker-compose.yml

## .github/
- .github/PULL_REQUEST_TEMPLATE.md
- .github/dependabot.yml

## .github/ISSUE_TEMPLATE/
- .github/ISSUE_TEMPLATE/config.yml
- .github/ISSUE_TEMPLATE/work.yml

## .github/actions/dayclose-ledger/
- .github/actions/dayclose-ledger/action.yml

## .github/actions/setup-python-uv/
- .github/actions/setup-python-uv/action.yml

## .github/workflows/
- .github/workflows/backend-ci.yml -- GitHub Actions workflow
- .github/workflows/backend-contracts.yml -- GitHub Actions workflow
- .github/workflows/claude.yml -- GitHub Actions workflow
- .github/workflows/context-freshness.yml -- GitHub Actions workflow
- .github/workflows/corpus-backup.yml -- GitHub Actions workflow
- .github/workflows/frontend.yml -- GitHub Actions workflow
- .github/workflows/issue-link-enforcement.yml -- GitHub Actions workflow
- .github/workflows/model-research-benchmark.yml -- GitHub Actions workflow
- .github/workflows/nfl-corpus-backup.yml -- GitHub Actions workflow
- .github/workflows/nfl-dayclose.yml -- GitHub Actions workflow
- .github/workflows/nfl-weekclose.yml -- GitHub Actions workflow
- .github/workflows/watchdog-monitor.yml -- GitHub Actions workflow
- .github/workflows/wnba-backfill-enrichment.yml -- GitHub Actions workflow
- .github/workflows/wnba-dayclose-verify.yml -- GitHub Actions workflow
- .github/workflows/wnba-model-train.yml -- GitHub Actions workflow
- .github/workflows/wnba-pre-freeze-guard.yml -- GitHub Actions workflow

## drive/
- drive/2026-08-25-wnba-contextual-stacking.md -- Contextual Stacking and Lineup Balance
- drive/2026-08-25-wnba-skills-and-strategy.md -- Task: Harvest sports AI skills and improve WNBA Oracle
- drive/2026-08-25-wnba-strategy-review.md -- WNBA Oracle Strategy Review
- drive/2026-08-29-issue-38-field-intelligence-verification.md -- Issue 38: Field Intelligence Verification
- drive/2026-08-30-canonical-player-identity-design.md -- Design: canonical player identity persistence (#30)
- drive/2026-08-30-immutable-decision-snapshot-design.md -- Design: immutable decision-input snapshot (#35 Phase 2)
- drive/2026-09-02-nfl-endpoint-archaeology.md
- drive/2026-09-06-nfl-overnight-morning-brief.md -- Morning brief — nfl-oracle overnight (2026-09-06)
- drive/2026-09-08-nfl-91-verification-handoff.md -- NFL #91 live contract verification - handoff to new session
- drive/2026-09-08-nfl-closeout-handoff.md -- NFL close-out handoff (Parts A-E)
- drive/2026-09-14-nfl-v2-overnight-handoff.md -- NFL Oracle v2: overnight build handoff (for ChatGPT)
- drive/2026-09-14-week-close-task-and-w2-boosts-handoff.md -- NFL week-close task design + week-2 boost handling
- drive/2026-09-14-week1-operator-retro.md -- Week 1 retro: operator observations
- drive/NFL-ORACLE Data Science Resources, Strategy, Research, and more.txt
- drive/README.md -- Document Drive
- drive/discover_nfl_contest.py -- Ad-hoc headless Playwright sniff for the active NFL playerratingcontest id.
- drive/probe_nfl.py -- Ad-hoc NFL endpoint probe, reusing WNBA Oracle's Real Sports auth machinery.
- drive/scan_contests.py

## drive/nfl_fixtures/
- drive/nfl_fixtures/boostcontrol.json -- (test fixture data)
- drive/nfl_fixtures/contest_2124_draftinfo.json -- (test fixture data)
- drive/nfl_fixtures/contest_2124_meta.json -- (test fixture data)
- drive/nfl_fixtures/contest_2124_payoutinfo.json -- (test fixture data)
- drive/nfl_fixtures/contest_2124_stats.json -- (test fixture data)
- drive/nfl_fixtures/game_19457_feed.json -- (test fixture data)
- drive/nfl_fixtures/game_19457_stats.json -- (test fixture data)
- drive/nfl_fixtures/home_next.json -- (test fixture data)
- drive/nfl_fixtures/search_a.json -- (test fixture data)
- drive/nfl_fixtures/squads.json -- (test fixture data)

## drive/nfl_probe_out/
- drive/nfl_probe_out/merged_summary.json
- drive/nfl_probe_out/nfl_history_probe2_results.json
- drive/nfl_probe_out/nfl_history_probe3_games.json
- drive/nfl_probe_out/nfl_history_probe_results.json

## nba-oracle/
- nba-oracle/.agent.md -- NBA Oracle agent instructions
- nba-oracle/.env.example
- nba-oracle/AGENTS.md -- NBA Oracle agent instructions
- nba-oracle/CLAUDE.md -- NBA Oracle agent instructions
- nba-oracle/Makefile -- Build/test/lint entrypoints
- nba-oracle/README.md -- nba-oracle
- nba-oracle/STATUS.md -- Status
- nba-oracle/pyproject.toml -- Package/tool configuration

## nba-oracle/src/nba_oracle/
- nba-oracle/src/nba_oracle/__init__.py -- NBA Oracle application package.

## nba-oracle/tests/
- nba-oracle/tests/test_import.py

## nfl-oracle/
- nfl-oracle/.agent.md -- NFL Oracle agent instructions
- nfl-oracle/.env.example
- nfl-oracle/.gitignore
- nfl-oracle/AGENTS.md -- NFL Oracle agent instructions
- nfl-oracle/BUILD_HANDOFF.md -- NFL Oracle build handoff
- nfl-oracle/CLAUDE.md -- NFL Oracle agent instructions
- nfl-oracle/DATA_ATTRIBUTION.md -- Data attribution (nfl-oracle)
- nfl-oracle/Dockerfile
- nfl-oracle/Dockerfile.production
- nfl-oracle/Makefile -- Build/test/lint entrypoints
- nfl-oracle/README.md -- nfl-oracle
- nfl-oracle/STATUS.md -- Status
- nfl-oracle/docker-compose.yml
- nfl-oracle/pyproject.toml -- Package/tool configuration
- nfl-oracle/railway.toml -- Package/tool configuration

## nfl-oracle/artifacts/
- nfl-oracle/artifacts/.gitkeep
- nfl-oracle/artifacts/README.md -- Walk-forward evaluation artifacts
- nfl-oracle/artifacts/walk_forward_fixture_sample.json
- nfl-oracle/artifacts/walk_forward_fixture_sample.md -- Walk-forward evaluation report

## nfl-oracle/config/
- nfl-oracle/config/NFLconfigvenues.json

## nfl-oracle/data/cache/
- nfl-oracle/data/cache/.gitkeep
- nfl-oracle/data/cache/README.md -- Schedule cache

## nfl-oracle/data/catalog/
- nfl-oracle/data/catalog/.gitkeep
- nfl-oracle/data/catalog/season_game_ids.json

## nfl-oracle/data/raw/
- nfl-oracle/data/raw/.gitkeep

## nfl-oracle/data/schedule/
- nfl-oracle/data/schedule/README.md -- Offline schedules (continuous slate)
- nfl-oracle/data/schedule/schedules.csv -- (data file)

## nfl-oracle/frontend/
- nfl-oracle/frontend/app.js
- nfl-oracle/frontend/index.html -- Static frontend page
- nfl-oracle/frontend/style.css

## nfl-oracle/scripts/
- nfl-oracle/scripts/auth_presence_check.py -- Print presence-only Real Sports auth surface status (never values).
- nfl-oracle/scripts/backup_corpus.py -- Off-platform logical backup of the irreplaceable NFL decision corpus.
- nfl-oracle/scripts/cache_nflverse_schedules.py -- Download public nflverse/nfldata games.csv and slim into offline schedule cache.
- nfl-oracle/scripts/capture_storage_state.py -- Capture a private Playwright session for operator-authorized Real Sports calls.
- nfl-oracle/scripts/daily_shadow.py -- Minimal daily-shadow scaffold (observation only; no contest entry).
- nfl-oracle/scripts/full_pool_draft.py -- Rank the complete eligible pool for the remaining games of a slate, and
- nfl-oracle/scripts/hydrate_identity_fixtures.py -- Offline: build an IdentityMap summary from Corpus G / value_labels fixtures.
- nfl-oracle/scripts/nfl_corpus_backup_common.py -- Integrity helpers shared by the NFL corpus backup and restore entry points.
- nfl-oracle/scripts/nfl_dayclose_gate.py -- Session-free gate: is there an NFL slate inside the day-close sweep window?
- nfl-oracle/scripts/nfl_weekclose_gate.py -- Session-free gate: should the NFL week-close job run now?
- nfl-oracle/scripts/postgres_store_smoke.py -- Exercise NFL recommendation storage against a temporary local PostgreSQL.
- nfl-oracle/scripts/production_container_smoke.py -- Build and smoke-test the NFL production image without secrets or a database.
- nfl-oracle/scripts/research_client_smoke.py -- Offline research FastAPI client smoke (observation only; no contest entry).
- nfl-oracle/scripts/restore_corpus.py -- Validate a verified NFL corpus backup snapshot.
- nfl-oracle/scripts/seed_storage_state.py -- Materialize scraper/storage_state.json from REALSPORTS_STORAGE_STATE_B64GZ.

## nfl-oracle/src/nfl_oracle/
- nfl-oracle/src/nfl_oracle/__init__.py -- NFL Oracle application package.

## nfl-oracle/src/nfl_oracle/baselines/
- nfl-oracle/src/nfl_oracle/baselines/__init__.py -- Walk-forward Real value baselines (offline / observation only).
- nfl-oracle/src/nfl_oracle/baselines/cli.py -- Offline CLI for Real value label schema + walk-forward baselines.
- nfl-oracle/src/nfl_oracle/baselines/eval_cli.py -- CLI: offline walk-forward eval report (baselines vs feature_ridge).
- nfl-oracle/src/nfl_oracle/baselines/eval_report.py -- Offline walk-forward evaluation report (baselines vs feature_ridge).
- nfl-oracle/src/nfl_oracle/baselines/metrics.py -- Honest scalar metrics for Real value baselines (stdlib only).
- nfl-oracle/src/nfl_oracle/baselines/player_priors.py -- Player-level recent-value prior scaffold (walk-forward safe).
- nfl-oracle/src/nfl_oracle/baselines/priors.py -- Transparent historical priors for Real ``value`` (no fancy models).
- nfl-oracle/src/nfl_oracle/baselines/ridge.py -- Tiny L2-regularized linear regression (stdlib only; no numpy/sklearn).
- nfl-oracle/src/nfl_oracle/baselines/value_model.py -- Leakage-safe feature-driven Real value model (optional walk-forward method).
- nfl-oracle/src/nfl_oracle/baselines/walk_forward.py -- Season walk-forward evaluation of Real value baselines (OOS by season).

## nfl-oracle/src/nfl_oracle/calendar/
- nfl-oracle/src/nfl_oracle/calendar/__init__.py -- Calendar helpers for NFL season/week labeling and offline schedules.
- nfl-oracle/src/nfl_oracle/calendar/schedule.py -- Public nflverse / nfldata schedule helpers (no Real Sports auth).
- nfl-oracle/src/nfl_oracle/calendar/season.py -- Minimal NFL season/week helpers (domain-owned; not a provider adapter).
- nfl-oracle/src/nfl_oracle/calendar/slate.py -- Week / slate resolution over dense offline schedules (observation only).
- nfl-oracle/src/nfl_oracle/calendar/week_close.py -- Week-close gate helpers: final slate identity, live finalization, buffer.

## nfl-oracle/src/nfl_oracle/common/
- nfl-oracle/src/nfl_oracle/common/__init__.py -- Shared NFL Oracle helpers.
- nfl-oracle/src/nfl_oracle/common/logging.py
- nfl-oracle/src/nfl_oracle/common/paths.py -- Project-owned runtime path discovery for nfl-oracle.

## nfl-oracle/src/nfl_oracle/contests/
- nfl-oracle/src/nfl_oracle/contests/__init__.py -- Corpus C: the historical Real Sports daily-draft contest archive.
- nfl-oracle/src/nfl_oracle/contests/boost_watch.py -- ``nfl-boost-watch`` — observe when the live card-boost table publishes.
- nfl-oracle/src/nfl_oracle/contests/boosts.py -- Card boosts: what they are, when they appear, and how to recover them.
- nfl-oracle/src/nfl_oracle/contests/cli.py -- ``nfl-contest-backfill`` — resumable, read-only Corpus C collection.
- nfl-oracle/src/nfl_oracle/contests/collector.py -- Read-only sweep of the Real Sports contest id space.
- nfl-oracle/src/nfl_oracle/contests/field.py -- What winning lineups actually did, measured from the saved contest archive.
- nfl-oracle/src/nfl_oracle/contests/parse.py -- Turn saved Corpus C payloads into validated records.
- nfl-oracle/src/nfl_oracle/contests/schema.py -- Typed, validated records parsed out of saved Corpus C payloads.
- nfl-oracle/src/nfl_oracle/contests/store.py -- Resumable, content-addressed persistence for the Corpus C contest archive.

## nfl-oracle/src/nfl_oracle/data/
- nfl-oracle/src/nfl_oracle/data/__init__.py -- NFL data-layer scaffolding: catalog, coverage, paths.
- nfl-oracle/src/nfl_oracle/data/catalog.py -- Committed season → game-id seed catalog.
- nfl-oracle/src/nfl_oracle/data/coverage.py -- Coverage matrix row schema (STATUS vocabulary).
- nfl-oracle/src/nfl_oracle/data/coverage_matrix.py -- Coverage matrix load/save helpers (STATUS vocabulary).
- nfl-oracle/src/nfl_oracle/data/density.py -- Offline coverage / catalog density summaries (observation only).
- nfl-oracle/src/nfl_oracle/data/label_depth.py -- Classify archive depth by which training-label rung each season supports.
- nfl-oracle/src/nfl_oracle/data/paths.py -- Filesystem layout helpers for nfl-oracle data roots (no secrets).
- nfl-oracle/src/nfl_oracle/data/summary.py -- Read-only research summaries over catalog + coverage matrix + schedule.

## nfl-oracle/src/nfl_oracle/features/
- nfl-oracle/src/nfl_oracle/features/__init__.py -- Feature schema scaffolding for nfl-oracle.
- nfl-oracle/src/nfl_oracle/features/live.py -- Map captured pre-lock evidence onto FeatureSpec names.
- nfl-oracle/src/nfl_oracle/features/matchup.py -- Static NFL division membership for the ``is_divisional`` FeatureSpec.
- nfl-oracle/src/nfl_oracle/features/opponent_defense.py -- Walk-forward Real-value-allowed priors for the opponent defense.
- nfl-oracle/src/nfl_oracle/features/rows.py -- Build observation-only feature rows from walk-forward priors.
- nfl-oracle/src/nfl_oracle/features/schema.py -- FeatureSpec v1: availability clocks + train/live flags.
- nfl-oracle/src/nfl_oracle/features/stubs.py -- Offline placeholder values for any FeatureSpec still marked ``offline_stub``.

## nfl-oracle/src/nfl_oracle/identity/
- nfl-oracle/src/nfl_oracle/identity/__init__.py -- Player identity scaffolding (Real Sports id primary).
- nfl-oracle/src/nfl_oracle/identity/aliases.py -- Alias / dedup reconciliation for Real-primary identity maps (offline).
- nfl-oracle/src/nfl_oracle/identity/density.py -- Offline identity density summaries (observation only).
- nfl-oracle/src/nfl_oracle/identity/from_corpus.py -- Hydrate IdentityMap from Corpus G players payloads (offline).
- nfl-oracle/src/nfl_oracle/identity/load.py -- Offline identity map loaders (observation only; no network).
- nfl-oracle/src/nfl_oracle/identity/map.py -- Real-primary identity map stubs — no cross-app imports.

## nfl-oracle/src/nfl_oracle/ingest/
- nfl-oracle/src/nfl_oracle/ingest/__init__.py -- NFL Real Sports ingest surfaces (Corpus G first).
- nfl-oracle/src/nfl_oracle/ingest/backfill.py -- Resumable season-by-season Corpus G backfill with coverage tracking.
- nfl-oracle/src/nfl_oracle/ingest/clocks.py -- Train/live information clocks for Corpus G provenance.
- nfl-oracle/src/nfl_oracle/ingest/corpus_g.py -- Corpus G persistence for Real Sports NFL game payloads.
- nfl-oracle/src/nfl_oracle/ingest/persist.py -- Idempotent redacted payload persistence helper for Corpus G.
- nfl-oracle/src/nfl_oracle/ingest/realsports.py -- Thin Real Sports HTTP client for NFL Corpus G (read-only).
- nfl-oracle/src/nfl_oracle/ingest/redact.py -- Redact identity fields from Real Sports NFL payloads before persistence.

## nfl-oracle/src/nfl_oracle/labels/
- nfl-oracle/src/nfl_oracle/labels/__init__.py -- Real value label schema and Corpus G extraction.
- nfl-oracle/src/nfl_oracle/labels/extract.py -- Extract Real ``value`` labels from Corpus G on-disk artifacts.
- nfl-oracle/src/nfl_oracle/labels/schema.py -- Real ``value`` label schema and train/live clock boundaries.

## nfl-oracle/src/nfl_oracle/providers/
- nfl-oracle/src/nfl_oracle/providers/RULES_OFFLINE.md -- UNKNOWN_PROVIDER_RULES — offline notes (no submit)
- nfl-oracle/src/nfl_oracle/providers/__init__.py -- Observation-only Real Sports provider stubs (#91). No contest submission.
- nfl-oracle/src/nfl_oracle/providers/auth_status.py -- Report Real Sports auth presence without printing secret values.
- nfl-oracle/src/nfl_oracle/providers/cli.py -- CLI for provider/auth status (no secrets printed).
- nfl-oracle/src/nfl_oracle/providers/five_card.py -- Five-card Real Sports provider stub (#91). Observation / shadow only.

## nfl-oracle/src/nfl_oracle/recommendations/
- nfl-oracle/src/nfl_oracle/recommendations/__init__.py -- NFL recommendation generation and serving, without contest submission.
- nfl-oracle/src/nfl_oracle/recommendations/app.py -- Read-only recommendation API. Provider credentials are never loaded here.
- nfl-oracle/src/nfl_oracle/recommendations/cli.py -- Production roles for the NFL recommendation service.
- nfl-oracle/src/nfl_oracle/recommendations/context.py -- Time-filtered NFL role, matchup and environment features.
- nfl-oracle/src/nfl_oracle/recommendations/dayclose.py -- Day-close grading: score a frozen NFL lineup against finalized real-world
- nfl-oracle/src/nfl_oracle/recommendations/weekclose.py -- Week-close punch-list producer: audit freezes/grades/on-disk contests for one NFL week (audit-only; never trains).
- nfl-oracle/src/nfl_oracle/recommendations/grading.py -- Immutable post-slate grading for frozen NFL recommendations.
- nfl-oracle/src/nfl_oracle/recommendations/high_tv.py -- NFL wiring for shared high-potential training (issue #185).
- nfl-oracle/src/nfl_oracle/recommendations/history.py -- Resumable, bounded historical collection and audited model input loading.
- nfl-oracle/src/nfl_oracle/recommendations/model.py -- Chronological Real-value model with explicit evidence and holdout diagnostics.
- nfl-oracle/src/nfl_oracle/recommendations/optimizer.py -- Five-card selection with committed ordering and feasible slate diversity.
- nfl-oracle/src/nfl_oracle/recommendations/pipeline.py -- NFL prepare, publish, and lock lifecycle on the shared durable store.
- nfl-oracle/src/nfl_oracle/recommendations/provider.py -- Read-only, audited NFL collection. Never exposes an entry mutation method.
- nfl-oracle/src/nfl_oracle/recommendations/schema.py -- Validated recommendation inputs. Research and submission gates remain separate.
- nfl-oracle/src/nfl_oracle/recommendations/sources.py -- Public NFL context captures with immutable, honest observation clocks.
- nfl-oracle/src/nfl_oracle/recommendations/store.py -- NFL-owned append-only decisions on the shared transaction infrastructure.

## nfl-oracle/src/nfl_oracle/replay/
- nfl-oracle/src/nfl_oracle/replay/__init__.py -- Replay the saved Corpus C contest archive against the verified scoring law.
- nfl-oracle/src/nfl_oracle/replay/backtest.py -- Historical zero-boost projection backtests over Corpus G player games.
- nfl-oracle/src/nfl_oracle/replay/harness.py -- Replay the saved Corpus C archive against the verified scoring law.

## nfl-oracle/src/nfl_oracle/service/
- nfl-oracle/src/nfl_oracle/service/__init__.py -- Read-only nfl-oracle research service scaffold.
- nfl-oracle/src/nfl_oracle/service/app.py -- FastAPI app via oracle-core — research/schema routes only.
- nfl-oracle/src/nfl_oracle/service/cli.py -- Run the read-only nfl-oracle research service.

## nfl-oracle/src/nfl_oracle/strategy/
- nfl-oracle/src/nfl_oracle/strategy/__init__.py -- Observation-only strategy contracts; no provider or submission integration.
- nfl-oracle/src/nfl_oracle/strategy/algebra.py -- Verified Real Sports NFL five-card scoring algebra (observation only).
- nfl-oracle/src/nfl_oracle/strategy/cli.py -- CLI for strategy schema document (offline).
- nfl-oracle/src/nfl_oracle/strategy/clocks.py -- Compat wrappers around strategy.schema clock gates.
- nfl-oracle/src/nfl_oracle/strategy/document.py -- Compat re-export — prefer nfl_oracle.strategy.schema.
- nfl-oracle/src/nfl_oracle/strategy/dry_run.py -- Offline contest dry-run: five-card shadow slate from fixtures.
- nfl-oracle/src/nfl_oracle/strategy/dry_run_cli.py -- CLI: offline contest dry-run five-card shadow slate (hard-deny submit).
- nfl-oracle/src/nfl_oracle/strategy/enumerate.py -- Enumerate ordered five-card actions for offline shadow comparisons.
- nfl-oracle/src/nfl_oracle/strategy/gates.py -- Contest-entry readiness gates (always deny submission from this package).
- nfl-oracle/src/nfl_oracle/strategy/lineup.py -- Compat aliases for five-card structural helpers.
- nfl-oracle/src/nfl_oracle/strategy/posture.py -- Derive strategy posture from provider readiness (observation only).
- nfl-oracle/src/nfl_oracle/strategy/readiness_score.py -- Observation-only research readiness score (0–100). Never authorizes entry.
- nfl-oracle/src/nfl_oracle/strategy/schema.py -- Observation-only strategy contracts; no provider submission.
- nfl-oracle/src/nfl_oracle/strategy/scoring.py -- Shadow score helpers for ordered five-card actions.
- nfl-oracle/src/nfl_oracle/strategy/snapshot.py -- Compat re-export for shadow snapshots.
- nfl-oracle/src/nfl_oracle/strategy/value_preds.py -- Map leakage-safe feature value model outputs into shadow value maps.

## nfl-oracle/src/nfl_oracle/valuelaw/
- nfl-oracle/src/nfl_oracle/valuelaw/__init__.py -- Value-law research package for the NFL five-card slate.
- nfl-oracle/src/nfl_oracle/valuelaw/boxstats.py -- Flat supervised dataset mapping Corpus G box statistics to the Real ``value`` label.
- nfl-oracle/src/nfl_oracle/valuelaw/candidates.py -- Live candidate pool for an NFL five-card slate, joined to Corpus G history.
- nfl-oracle/src/nfl_oracle/valuelaw/model.py -- Fit and apply the box-stats-to-value model.
- nfl-oracle/src/nfl_oracle/valuelaw/project.py -- Project live candidate values from Corpus G history.

## nfl-oracle/tests/
- nfl-oracle/tests/__init__.py
- nfl-oracle/tests/conftest.py -- Shared pytest fixtures for nfl-oracle.

## nfl-oracle/tests/fixtures/
- nfl-oracle/tests/fixtures/feed_126323.json -- (test fixture data)
- nfl-oracle/tests/fixtures/players_126323.json -- (test fixture data)
- nfl-oracle/tests/fixtures/stats_126323.json -- (test fixture data)

## nfl-oracle/tests/fixtures/corpus_g/
- nfl-oracle/tests/fixtures/corpus_g/feed_all.json -- (test fixture data)
- nfl-oracle/tests/fixtures/corpus_g/players.json -- (test fixture data)
- nfl-oracle/tests/fixtures/corpus_g/stats.json -- (test fixture data)

## nfl-oracle/tests/fixtures/coverage/
- nfl-oracle/tests/fixtures/coverage/dense_catalog.json -- (test fixture data)
- nfl-oracle/tests/fixtures/coverage/dense_matrix.json -- (test fixture data)

## nfl-oracle/tests/fixtures/identity/
- nfl-oracle/tests/fixtures/identity/dense_players.json -- (test fixture data)

## nfl-oracle/tests/fixtures/offline_research/data/catalog/
- nfl-oracle/tests/fixtures/offline_research/data/catalog/coverage_matrix.json -- (test fixture data)
- nfl-oracle/tests/fixtures/offline_research/data/catalog/season_game_ids.json -- (test fixture data)

## nfl-oracle/tests/fixtures/offline_research/data/identity/
- nfl-oracle/tests/fixtures/offline_research/data/identity/players.json -- (test fixture data)

## nfl-oracle/tests/fixtures/offline_research/data/schedule/
- nfl-oracle/tests/fixtures/offline_research/data/schedule/schedules.csv -- (data file)

## nfl-oracle/tests/fixtures/schedule/
- nfl-oracle/tests/fixtures/schedule/dense_schedules.csv -- (data file)

## nfl-oracle/tests/fixtures/value_labels/2022/1001/
- nfl-oracle/tests/fixtures/value_labels/2022/1001/manifest.json -- (test fixture data)
- nfl-oracle/tests/fixtures/value_labels/2022/1001/stats.json -- (test fixture data)

## nfl-oracle/tests/fixtures/value_labels/2022/1002/
- nfl-oracle/tests/fixtures/value_labels/2022/1002/manifest.json -- (test fixture data)
- nfl-oracle/tests/fixtures/value_labels/2022/1002/stats.json -- (test fixture data)

## nfl-oracle/tests/fixtures/value_labels/2023/2001/
- nfl-oracle/tests/fixtures/value_labels/2023/2001/manifest.json -- (test fixture data)
- nfl-oracle/tests/fixtures/value_labels/2023/2001/stats.json -- (test fixture data)

## nfl-oracle/tests/fixtures/value_labels/2024/3001/
- nfl-oracle/tests/fixtures/value_labels/2024/3001/manifest.json -- (test fixture data)
- nfl-oracle/tests/fixtures/value_labels/2024/3001/stats.json -- (test fixture data)

## nfl-oracle/tests/fixtures/value_labels/2025/5001/
- nfl-oracle/tests/fixtures/value_labels/2025/5001/manifest.json -- (test fixture data)
- nfl-oracle/tests/fixtures/value_labels/2025/5001/stats.json -- (test fixture data)

## nfl-oracle/tests/integration/
- nfl-oracle/tests/integration/__init__.py -- Integration tests for nfl-oracle research paths (offline).
- nfl-oracle/tests/integration/test_boost_regime_pick_path.py -- Integration coverage for issue #166: the live pick path under real boosts.
- nfl-oracle/tests/integration/test_research_routes.py -- Integration coverage for research FastAPI routes (offline fixtures).

## nfl-oracle/tests/unit/
- nfl-oracle/tests/unit/__init__.py
- nfl-oracle/tests/unit/test_anti_chalk_high_tv.py -- Anti-chalk + high-potential label path pins for issue #185.
- nfl-oracle/tests/unit/test_auth_presence_check.py -- auth_presence_check must see volume-backed Real Sports session files.
- nfl-oracle/tests/unit/test_backfill_cursor.py -- Tests for season backfill cursor resume.
- nfl-oracle/tests/unit/test_capture_storage_state_paths.py -- capture_storage_state must write under volume-aware scraper_dir.
- nfl-oracle/tests/unit/test_clocks.py -- Tests for train/live Corpus G clock helpers.
- nfl-oracle/tests/unit/test_contest_algebra_and_gates.py -- Contest scoring algebra + entry gates (observation only).
- nfl-oracle/tests/unit/test_contest_corpus.py -- Corpus C: scoring-law verification, boost recovery, and censoring honesty.
- nfl-oracle/tests/unit/test_contest_dry_run.py -- Offline contest dry-run: five-card shadow slate + hard-deny submit.
- nfl-oracle/tests/unit/test_corpus_backup.py
- nfl-oracle/tests/unit/test_corpus_g.py -- Tests for Corpus G summarize + persist boundary.
- nfl-oracle/tests/unit/test_corpus_g_store.py
- nfl-oracle/tests/unit/test_coverage_matrix.py -- Tests for season coverage matrix status vocabulary.
- nfl-oracle/tests/unit/test_data_features_calendar.py -- Data catalog, features schema, calendar helpers.
- nfl-oracle/tests/unit/test_dayclose.py
- nfl-oracle/tests/unit/test_dayclose_gate.py
- nfl-oracle/tests/unit/test_eval_report.py -- Tests for offline walk-forward eval report (baselines vs feature_ridge).
- nfl-oracle/tests/unit/test_feature_registry_depth.py -- Feature registry depth for pre-lock decisioning.
- nfl-oracle/tests/unit/test_feature_value_model.py -- Leakage-safe feature_ridge value model + strategy wiring.
- nfl-oracle/tests/unit/test_feature_wiring_189.py -- Evidence-backed FeatureSpec wiring landed for issue #189.
- nfl-oracle/tests/unit/test_identity_coverage_density.py -- Offline identity + coverage density fixtures and helpers.
- nfl-oracle/tests/unit/test_identity_dedup_collisions.py -- Identity alias/dedup reconciliation beyond first+last (offline).
- nfl-oracle/tests/unit/test_identity_from_corpus.py -- Identity hydration from Corpus G players fixtures.
- nfl-oracle/tests/unit/test_label_depth.py -- Max-season label-kind depth across the catalog (issue #189).
- nfl-oracle/tests/unit/test_local_research_docker.py -- Local nfl-oracle-local research Docker assets (observation-only; no secrets).
- nfl-oracle/tests/unit/test_player_mean_and_coverage_matrix.py -- player_mean baseline + coverage matrix document helpers.
- nfl-oracle/tests/unit/test_player_priors_scoring.py -- Player priors + shadow scoring scaffolds.
- nfl-oracle/tests/unit/test_production_container.py
- nfl-oracle/tests/unit/test_provider_stubs.py -- Provider stubs: auth probe + five-card shadow (no network).
- nfl-oracle/tests/unit/test_readiness_score.py -- Unit tests for observation-only research readiness score.
- nfl-oracle/tests/unit/test_realsports_auth_bootstrap.py
- nfl-oracle/tests/unit/test_recommendation_context_sources.py
- nfl-oracle/tests/unit/test_recommendation_contracts.py
- nfl-oracle/tests/unit/test_recommendation_defense_eligibility.py -- Defense eligibility: pool and optimizer must not silently exclude DL/LB/DB.
- nfl-oracle/tests/unit/test_recommendation_grading.py
- nfl-oracle/tests/unit/test_recommendation_model_optimizer.py
- nfl-oracle/tests/unit/test_recommendation_model_safety.py
- nfl-oracle/tests/unit/test_recommendation_multi_game_slate.py -- The decision path must survive a full Sunday, not just a one-game slate.
- nfl-oracle/tests/unit/test_recommendation_pool_denominator.py -- Pool completeness must be measured against games that can still be drafted.
- nfl-oracle/tests/unit/test_recommendation_provider.py
- nfl-oracle/tests/unit/test_recommendation_store.py
- nfl-oracle/tests/unit/test_redact.py -- Tests for Corpus G identity redaction.
- nfl-oracle/tests/unit/test_replay_backtest.py
- nfl-oracle/tests/unit/test_replay_harness.py -- Unit tests for nfl_oracle.replay.harness.
- nfl-oracle/tests/unit/test_research_api_draft_edges.py -- Additional research API + fixture honesty edges for draft readiness.
- nfl-oracle/tests/unit/test_research_client_smoke.py -- Offline research_client_smoke script.
- nfl-oracle/tests/unit/test_research_path_extras.py -- Extra research/service/strategy scaffolding tests.
- nfl-oracle/tests/unit/test_schedule_census_and_aliases.py -- Identity alias reconciliation + schedule helper smoke (offline).
- nfl-oracle/tests/unit/test_schedule_coverage_edges.py -- Edge cases: schedule density, empty coverage, posture, algebra override.
- nfl-oracle/tests/unit/test_schedule_parse.py -- Offline nflverse schedule CSV parse + density.
- nfl-oracle/tests/unit/test_schedule_slate_census.py -- Continuous season slate discovery + coverage census (offline nflverse).
- nfl-oracle/tests/unit/test_schedule_slate_resolve.py -- Week/slate resolution helpers over dense offline schedules.
- nfl-oracle/tests/unit/test_service_app.py -- Research service scaffold smoke tests.
- nfl-oracle/tests/unit/test_service_shadow_edges.py -- Research service edge cases for shadow/gates/status (observation only).
- nfl-oracle/tests/unit/test_strategy_scaffold.py -- Strategy scaffold: clocks, five-card legality, snapshots.
- nfl-oracle/tests/unit/test_value_baselines.py -- Tests for walk-forward Real value baselines (offline).
- nfl-oracle/tests/unit/test_value_labels.py -- Tests for Real value label schema + Corpus G extraction.
- nfl-oracle/tests/unit/test_valuelaw_model.py -- Unit tests for nfl_oracle.valuelaw.model.
- nfl-oracle/tests/unit/test_valuelaw_project.py
- nfl-oracle/tests/unit/test_weekclose.py
- nfl-oracle/tests/unit/test_weekclose_gate.py
- nfl-oracle/tests/unit/test_worker_retry.py
- nfl-oracle/tests/unit/test_worker_terminal_state.py -- A published slate is terminal: freeze once, then stop.

## nhl-oracle/
- nhl-oracle/.agent.md -- NHL Oracle agent instructions
- nhl-oracle/.env.example
- nhl-oracle/AGENTS.md -- NHL Oracle agent instructions
- nhl-oracle/CLAUDE.md -- NHL Oracle agent instructions
- nhl-oracle/Makefile -- Build/test/lint entrypoints
- nhl-oracle/README.md -- nhl-oracle
- nhl-oracle/STATUS.md -- Status
- nhl-oracle/pyproject.toml -- Package/tool configuration

## nhl-oracle/src/nhl_oracle/
- nhl-oracle/src/nhl_oracle/__init__.py -- NHL Oracle application package.

## nhl-oracle/src/nhl_oracle/contract/
- nhl-oracle/src/nhl_oracle/contract/__init__.py -- NHL contest contract shape and audit gates (observation only, pre-provider).
- nhl-oracle/src/nhl_oracle/contract/gates.py -- NHL contract audit gates (always observation only, never contest entry).
- nhl-oracle/src/nhl_oracle/contract/schema.py -- Candidate NHL contest contract shape, pending live-provider confirmation.

## nhl-oracle/src/nhl_oracle/identity/
- nhl-oracle/src/nhl_oracle/identity/__init__.py -- NHL player identity map and collision reconciliation.
- nhl-oracle/src/nhl_oracle/identity/map.py -- NHL identity map keyed by the provider's primary player id.
- nhl-oracle/src/nhl_oracle/identity/reconcile.py -- Same-name identity collision reconciliation (offline, observation only).

## nhl-oracle/src/nhl_oracle/ingest/
- nhl-oracle/src/nhl_oracle/ingest/__init__.py -- NHL raw payload provenance and persistence (pre-provider scaffold).
- nhl-oracle/src/nhl_oracle/ingest/provenance.py -- Redacted NHL raw payload persistence with sidecar provenance.

## nhl-oracle/src/nhl_oracle/scheduler/
- nhl-oracle/src/nhl_oracle/scheduler/__init__.py -- NHL freeze-cycle job skeleton (no live provider, no contest entry).
- nhl-oracle/src/nhl_oracle/scheduler/freeze.py -- NHL freeze-cycle job skeleton.

## nhl-oracle/tests/
- nhl-oracle/tests/test_contract_gates.py
- nhl-oracle/tests/test_contract_schema.py
- nhl-oracle/tests/test_freeze_cycle.py
- nhl-oracle/tests/test_identity_reconcile.py
- nhl-oracle/tests/test_import.py
- nhl-oracle/tests/test_provenance.py

## packages/oracle-core/
- packages/oracle-core/README.md -- oracle-core
- packages/oracle-core/pyproject.toml -- Package/tool configuration

## packages/oracle-core/src/oracle_core/
- packages/oracle-core/src/oracle_core/__init__.py -- Domain-free runtime infrastructure for Oracle applications.
- packages/oracle-core/src/oracle_core/artifacts.py -- Atomic artifact persistence and integrity verification.
- packages/oracle-core/src/oracle_core/cache.py -- Atomic JSON TTL caching over a technical key-value capability.
- packages/oracle-core/src/oracle_core/config.py -- Runtime settings shared by applications without loading an env file.
- packages/oracle-core/src/oracle_core/dayclose.py -- Generic day-close sweep orchestration, shared by every sport application.
- packages/oracle-core/src/oracle_core/dossier.py -- Provider-neutral dossier entry and gap schema for contest analysis.
- packages/oracle-core/src/oracle_core/high_tv.py -- Domain-free high-potential training contracts and dataset helpers.
- packages/oracle-core/src/oracle_core/http.py -- Provider-neutral HTTP transports with bounded retry behavior.
- packages/oracle-core/src/oracle_core/jobs.py -- Generic job registration, lifecycle, role validation, and execution.
- packages/oracle-core/src/oracle_core/logging.py -- Structured, redacted logging primitives for application adapters.
- packages/oracle-core/src/oracle_core/py.typed
- packages/oracle-core/src/oracle_core/redaction.py -- Secret redaction helpers for logs, diagnostics, and HTTP URLs.
- packages/oracle-core/src/oracle_core/schemaorg.py -- schema.org vocabulary helpers for shared Oracle data contracts.
- packages/oracle-core/src/oracle_core/service.py -- Generic FastAPI service metadata and health behavior.
- packages/oracle-core/src/oracle_core/storage.py -- Provider-neutral PostgreSQL transactions and Redis-backed stores.
- packages/oracle-core/src/oracle_core/testing.py -- Deterministic fakes and log capture helpers for application tests.

## packages/oracle-core/tests/
- packages/oracle-core/tests/test_artifacts.py
- packages/oracle-core/tests/test_config.py
- packages/oracle-core/tests/test_dayclose.py
- packages/oracle-core/tests/test_high_tv.py -- High-potential label ladder and weight builders (issue #185).
- packages/oracle-core/tests/test_http.py
- packages/oracle-core/tests/test_jobs.py
- packages/oracle-core/tests/test_redaction_logging.py
- packages/oracle-core/tests/test_schemaorg.py -- schema.org contract helpers.
- packages/oracle-core/tests/test_service.py
- packages/oracle-core/tests/test_storage_cache.py
- packages/oracle-core/tests/test_testing.py

## scripts/
- scripts/auth-check
- scripts/check_applications.py -- Validate the minimum contract for every top-level sport application.
- scripts/check_dev_services.py -- Read-only, bounded probes of the explicitly configured development services.
- scripts/check_import_boundaries.py -- Enforce the workspace dependency direction with static import checks.
- scripts/check_issue_link.py -- Enforce issue linkage for material pull request work.
- scripts/codespaces-smoke.sh -- Shell script
- scripts/generate_file_manifest.py -- Regenerate FILES.md: a one-line-per-file manifest of every tracked file.
- scripts/with-secrets
- scripts/write-path-check

## scripts/tests/
- scripts/tests/test_check_applications.py
- scripts/tests/test_check_dev_services.py
- scripts/tests/test_check_issue_link.py

## wnba-oracle/
- wnba-oracle/.agent.md -- WNBA Oracle Instructions
- wnba-oracle/.env.example
- wnba-oracle/.gitignore
- wnba-oracle/.mcp.json
- wnba-oracle/AGENTS.md -- WNBA Oracle Instructions
- wnba-oracle/CLAUDE.md -- WNBA Oracle Instructions
- wnba-oracle/COMMUNITY_STRATEGY_TASK.md -- Community/Field Strategy Calibration — Copilot Task
- wnba-oracle/Dockerfile
- wnba-oracle/MODEL_PICK_POSTMORTEM_2026-08-28.md -- Model Pick Postmortem — 2026-08-28 Slate
- wnba-oracle/Makefile -- Build/test/lint entrypoints
- wnba-oracle/README.md -- WNBA Oracle
- wnba-oracle/STATUS.md -- Status
- wnba-oracle/alembic.ini
- wnba-oracle/pyproject.toml -- Package/tool configuration
- wnba-oracle/railway.toml -- Package/tool configuration

## wnba-oracle/.pgssl/
- wnba-oracle/.pgssl/server.crt

## wnba-oracle/data/contest_payouts/
- wnba-oracle/data/contest_payouts/.gitkeep

## wnba-oracle/data/historical/
- wnba-oracle/data/historical/.gitkeep

## wnba-oracle/data/processed/
- wnba-oracle/data/processed/.gitkeep

## wnba-oracle/data/raw/
- wnba-oracle/data/raw/.gitkeep

## wnba-oracle/eval/
- wnba-oracle/eval/.gitkeep

## wnba-oracle/frontend/
- wnba-oracle/frontend/.dockerignore
- wnba-oracle/frontend/.gitignore
- wnba-oracle/frontend/Dockerfile
- wnba-oracle/frontend/build-serve-config.mjs
- wnba-oracle/frontend/eslint.config.mjs
- wnba-oracle/frontend/index.html -- Static frontend page
- wnba-oracle/frontend/package-lock.json
- wnba-oracle/frontend/package.json
- wnba-oracle/frontend/playwright.config.ts
- wnba-oracle/frontend/railway.toml -- Package/tool configuration
- wnba-oracle/frontend/serve.template.json
- wnba-oracle/frontend/tsconfig.json
- wnba-oracle/frontend/vite.config.ts
- wnba-oracle/frontend/vitest.config.ts

## wnba-oracle/frontend/e2e/
- wnba-oracle/frontend/e2e/no-scroll.spec.ts

## wnba-oracle/frontend/src/
- wnba-oracle/frontend/src/App.tsx
- wnba-oracle/frontend/src/main.tsx

## wnba-oracle/frontend/src/components/
- wnba-oracle/frontend/src/components/BoostBadge.tsx
- wnba-oracle/frontend/src/components/Countdown.tsx
- wnba-oracle/frontend/src/components/ErrorState.tsx
- wnba-oracle/frontend/src/components/Footer.tsx
- wnba-oracle/frontend/src/components/Header.tsx
- wnba-oracle/frontend/src/components/Headshot.tsx
- wnba-oracle/frontend/src/components/Icon.tsx
- wnba-oracle/frontend/src/components/IntervalBar.tsx
- wnba-oracle/frontend/src/components/OracleLoader.tsx
- wnba-oracle/frontend/src/components/Shell.tsx
- wnba-oracle/frontend/src/components/SlateBand.tsx
- wnba-oracle/frontend/src/components/Slip.tsx
- wnba-oracle/frontend/src/components/SlipRow.tsx
- wnba-oracle/frontend/src/components/ThemeToggle.tsx
- wnba-oracle/frontend/src/components/WatchdogDot.tsx

## wnba-oracle/frontend/src/hooks/
- wnba-oracle/frontend/src/hooks/useLineupData.ts
- wnba-oracle/frontend/src/hooks/useLiveBoxScores.ts
- wnba-oracle/frontend/src/hooks/useSlateLifecycle.ts
- wnba-oracle/frontend/src/hooks/useSlateTiming.ts
- wnba-oracle/frontend/src/hooks/useTheme.ts
- wnba-oracle/frontend/src/hooks/useWatchdogStatus.ts

## wnba-oracle/frontend/src/lib/
- wnba-oracle/frontend/src/lib/actionability.test.ts
- wnba-oracle/frontend/src/lib/actionability.ts
- wnba-oracle/frontend/src/lib/api.ts
- wnba-oracle/frontend/src/lib/demo.ts
- wnba-oracle/frontend/src/lib/espn.ts
- wnba-oracle/frontend/src/lib/http.test.ts
- wnba-oracle/frontend/src/lib/http.ts
- wnba-oracle/frontend/src/lib/lineup.test.ts
- wnba-oracle/frontend/src/lib/lineup.ts
- wnba-oracle/frontend/src/lib/playerMatch.ts
- wnba-oracle/frontend/src/lib/scheduling.test.ts
- wnba-oracle/frontend/src/lib/scheduling.ts
- wnba-oracle/frontend/src/lib/teams.ts

## wnba-oracle/frontend/src/pages/
- wnba-oracle/frontend/src/pages/FreezesPage.tsx
- wnba-oracle/frontend/src/pages/HistoryPage.tsx
- wnba-oracle/frontend/src/pages/PickerPage.tsx
- wnba-oracle/frontend/src/pages/PlayerPage.tsx
- wnba-oracle/frontend/src/pages/SlatePage.tsx
- wnba-oracle/frontend/src/pages/SystemPage.tsx

## wnba-oracle/frontend/src/styles/
- wnba-oracle/frontend/src/styles/main.css

## wnba-oracle/frontend/src/styles/partials/
- wnba-oracle/frontend/src/styles/partials/app-shell.css
- wnba-oracle/frontend/src/styles/partials/base.css
- wnba-oracle/frontend/src/styles/partials/depth-pages.css
- wnba-oracle/frontend/src/styles/partials/error-state.css
- wnba-oracle/frontend/src/styles/partials/footer.css
- wnba-oracle/frontend/src/styles/partials/header.css
- wnba-oracle/frontend/src/styles/partials/loader.css
- wnba-oracle/frontend/src/styles/partials/pick-ui.css
- wnba-oracle/frontend/src/styles/partials/slate-band.css
- wnba-oracle/frontend/src/styles/partials/slip.css
- wnba-oracle/frontend/src/styles/partials/stub-pages.css
- wnba-oracle/frontend/src/styles/partials/theme-toggle.css
- wnba-oracle/frontend/src/styles/partials/tokens.css
- wnba-oracle/frontend/src/styles/partials/utility.css

## wnba-oracle/migrations/
- wnba-oracle/migrations/README
- wnba-oracle/migrations/env.py -- Alembic environment. Reads DATABASE_URL from env (Pydantic settings).
- wnba-oracle/migrations/script.py.mako

## wnba-oracle/migrations/versions/
- wnba-oracle/migrations/versions/20260526_0001_init.py -- init: core picker tables.
- wnba-oracle/migrations/versions/20260527_0002_slate_labels.py -- slate_labels: per-slate per-player training labels (real_score + card_boost).
- wnba-oracle/migrations/versions/20260527_0003_contest_leaderboards.py -- contest_leaderboards: top-20 finishers' lineups per finalized contest.
- wnba-oracle/migrations/versions/20260605_0004_wnba_game_logs.py -- wnba_game_logs: per-game box scores from stats.wnba.com (nba_api).
- wnba-oracle/migrations/versions/20260605_0005_wnba_game_logs_matchup.py -- wnba_game_logs: add opponent / home_away / game_id matchup fields.
- wnba-oracle/migrations/versions/20260610_0006_frozen_append_only.py -- frozen_lineups: append-only freezes + slate_meta lock times.
- wnba-oracle/migrations/versions/20260613_0007_contest_placements.py -- contest_placements: closed-loop placement / calibration tracking (D90).
- wnba-oracle/migrations/versions/20260613_0008_contest_placements_sha64.py -- Fix freeze_model_sha column: varchar(40) -> varchar(64).
- wnba-oracle/migrations/versions/20260820_0009_freeze_operation_key.py -- Add semantic idempotency keys to append-only freezes.
- wnba-oracle/migrations/versions/20260820_0010_job_runs.py -- Add durable job lifecycle heartbeats.

## wnba-oracle/models/
- wnba-oracle/models/.gitkeep
- wnba-oracle/models/picker_95264ce9_1788339935.manifest.json
- wnba-oracle/models/picker_95264ce9_1788339935.pkl
- wnba-oracle/models/picker_95264ce9_1788339935.sha256
- wnba-oracle/models/picker_bf3c8996_1780752059.pkl
- wnba-oracle/models/picker_bf3c8996_1780752059.sha256
- wnba-oracle/models/picker_e2ced9ec_1780873338.pkl
- wnba-oracle/models/picker_e2ced9ec_1780873338.sha256

## wnba-oracle/runs/
- wnba-oracle/runs/.gitkeep

## wnba-oracle/scripts/
- wnba-oracle/scripts/analyze_stacking_decisions.py -- Read-only analytics for durable contextual-stacking decisions.
- wnba-oracle/scripts/analyze_strategy_gap.py -- Strategy-gap analysis against the 2026 WNBA leaderboard + slate_labels corpus.
- wnba-oracle/scripts/auth-check-live
- wnba-oracle/scripts/backfill_game_identity.py -- Backfill missing job1_enrichment.features_json.game_id from same-slate rows.
- wnba-oracle/scripts/backfill_head_features.py -- One-off backfill: merge the D69 `head_features` row into existing
- wnba-oracle/scripts/backfill_minutes.py -- Backfill WNBA per-game minutes + box lines from stats.wnba.com (nba_api).
- wnba-oracle/scripts/backfill_placement_scores.py -- Recompute contest_placements.entry_score under the committed slot order.
- wnba-oracle/scripts/backfill_player_slate_ownership.py -- Backfill player_slate_ownership.actual_* from existing slate_labels.drafts.
- wnba-oracle/scripts/backtest_counterfactual.py -- Counterfactual backtest: attribute the picker's leaderboard gap to its
- wnba-oracle/scripts/backtest_optimizer.py -- Run the picker on the 2026-05-25 slate using its actual realized
- wnba-oracle/scripts/backtest_pipeline.py -- Out-of-sample backtest of the full picker pipeline on the 16 2026
- wnba-oracle/scripts/backtest_walkforward.py -- Walk-forward backtest: HONEST prediction-quality measurement (no leakage).
- wnba-oracle/scripts/backup_corpus.py -- Off-platform logical backup of the irreplaceable WNBA corpus.
- wnba-oracle/scripts/build_model_research_benchmark.py -- Model research benchmark: walk-forward variant sweep over stored slates.
- wnba-oracle/scripts/calibrate_knobs.py -- Calibrate D87-D90 optimizer knobs against 2026 historical slates.
- wnba-oracle/scripts/calibrate_starter_and_boost.py -- Calibrate STARTER_UNKNOWN_FADE and PICKER_BOOST_TAIL_LIFT from the corpus.
- wnba-oracle/scripts/check_migrations.py -- Exercise empty and existing-schema Alembic upgrades on a local PostgreSQL server.
- wnba-oracle/scripts/cloud_setup.sh -- Shell script
- wnba-oracle/scripts/compare_artifacts.py -- Compare two PickerArtifact pickles by trained-model CONTENT (determinism gate).
- wnba-oracle/scripts/corpus_backup_common.py -- Integrity helpers shared by the corpus backup and restore entry points.
- wnba-oracle/scripts/dayclose_verify.py -- Verify the WNBA day-close cron using public durable application evidence.
- wnba-oracle/scripts/dev.sh -- Shell script
- wnba-oracle/scripts/export_game_identity.py -- Export validated (slate_date, team, opponent) identity from job1_enrichment.
- wnba-oracle/scripts/export_game_logs.py -- Export the full ``wnba_game_logs`` corpus for offline tournament/benchmark use.
- wnba-oracle/scripts/lab.py -- Offline model lab: the one entry point for evaluating a change.
- wnba-oracle/scripts/loss_ledger.py -- Per-slate loss ledger: where our frozen lineup lost points, and why.
- wnba-oracle/scripts/manual_fire.py -- End-to-end manual fire against the live Real Sports slate.
- wnba-oracle/scripts/model_tournament.py -- Model tournament: real paired comparison of trained picker artifacts.
- wnba-oracle/scripts/ops_common.py -- Portable, fail-closed helpers for WNBA production checks.
- wnba-oracle/scripts/pre_freeze_guard.py -- Validate the WNBA production pipeline before the daily freeze window.
- wnba-oracle/scripts/probe_leaderboard.py -- Probe for the Real Sports WNBA leaderboard endpoint + verify historical
- wnba-oracle/scripts/probe_missing_slates.py -- Probe Real Sports contest_ids to find slates we are missing for the
- wnba-oracle/scripts/probe_realsports.py -- Step 2 probe: confirm WNBA Real Sports endpoints + archive payout curve.
- wnba-oracle/scripts/replay_slate.py -- Replay one slate through the picker, old config vs shipped config, and
- wnba-oracle/scripts/research_game_script.py -- Research script: empirical evaluation of blowout/bench minutes redistribution.
- wnba-oracle/scripts/research_ownership_estimator.py -- Research script: learned pre-lock WNBA ownership estimator.
- wnba-oracle/scripts/resolve_ops_window.py -- Resolve validated manual or scheduled WNBA operations run windows.
- wnba-oracle/scripts/restore_corpus.py -- Validate and explicitly restore a verified corpus backup.
- wnba-oracle/scripts/runtime_role_probe.py -- Validate that a built runtime image enforces its configured cron role.
- wnba-oracle/scripts/rwgql.py -- Call Railway GraphQL with ambient auth and optional variables on stdin.
- wnba-oracle/scripts/rwgql.sh -- Shell script
- wnba-oracle/scripts/seed_storage_state.py -- Materialize the Playwright storage_state.json from a base64+gzip env var.
- wnba-oracle/scripts/snapshot_corpus.py -- Materialize a frozen local corpus snapshot for offline model work.
- wnba-oracle/scripts/snapshot_training_inputs.py -- Snapshot one immutable pair of live training inputs for reproducibility checks.
- wnba-oracle/scripts/stack_alignment_check.py -- Game-stack alignment audit (post-mortem item 2).
- wnba-oracle/scripts/sweep_max_boost.py -- Sweep OPTIMIZER_MAX_SINGLE_BOOST against the corpus counterfactual.
- wnba-oracle/scripts/validate_minutes_model.py -- Go/no-go: does a minutes x per-minute-rate model beat the boost prior?
- wnba-oracle/scripts/verify_durable_job.py -- Verify one new successful durable job outcome through the public API.
- wnba-oracle/scripts/watchdog_monitor.py -- Probe WNBA serving, durable job runs, and the freeze watchdog.

## wnba-oracle/skills/corpus-status/
- wnba-oracle/skills/corpus-status/SKILL.md -- From wnba-oracle/

## wnba-oracle/skills/knob-shadow/
- wnba-oracle/skills/knob-shadow/SKILL.md

## wnba-oracle/skills/ops-runbook/
- wnba-oracle/skills/ops-runbook/SKILL.md -- 1. Verify job1 ran and pool is non-empty

## wnba-oracle/skills/slate-review/
- wnba-oracle/skills/slate-review/SKILL.md -- From wnba-oracle/

## wnba-oracle/skills/strategy-gap/
- wnba-oracle/skills/strategy-gap/SKILL.md -- From wnba-oracle/

## wnba-oracle/src/wnba_oracle/
- wnba-oracle/src/wnba_oracle/__init__.py -- WNBA Oracle - Real Sports daily-draft WNBA picker.
- wnba-oracle/src/wnba_oracle/dossier.py -- Build dossier entries for finalized slates.

## wnba-oracle/src/wnba_oracle/api/
- wnba-oracle/src/wnba_oracle/api/__init__.py
- wnba-oracle/src/wnba_oracle/api/app.py -- FastAPI app. Read-only surface over the frozen lineup.
- wnba-oracle/src/wnba_oracle/api/dossier.py -- Read-only API endpoint for the post-slate dossier (#35 phase 3, #39).
- wnba-oracle/src/wnba_oracle/api/lineup.py -- Read-only API endpoints for the frozen lineup.
- wnba-oracle/src/wnba_oracle/api/slate.py -- Read-only slate-timing endpoint for the frontend countdown (D104).
- wnba-oracle/src/wnba_oracle/api/watchdog_router.py -- Operator-facing watchdog surface.

## wnba-oracle/src/wnba_oracle/assurance/
- wnba-oracle/src/wnba_oracle/assurance/__init__.py -- WNBA-owned connector inventory and observational source assurance.
- wnba-oracle/src/wnba_oracle/assurance/connectors.py -- Stable, value-free map of the WNBA application's connector boundaries.
- wnba-oracle/src/wnba_oracle/assurance/source_quality.py -- Observational source-quality facts attached to a frozen recommendation.

## wnba-oracle/src/wnba_oracle/audit/
- wnba-oracle/src/wnba_oracle/audit/__init__.py
- wnba-oracle/src/wnba_oracle/audit/rotation_cli.py -- Rotation gate CLI: oracle-rotate-check.

## wnba-oracle/src/wnba_oracle/common/
- wnba-oracle/src/wnba_oracle/common/__init__.py
- wnba-oracle/src/wnba_oracle/common/clock.py -- WNBA slate-calendar conversion over an injected UTC instant.
- wnba-oracle/src/wnba_oracle/common/db_utils.py -- Database URL helpers. One place to keep the postgres scheme normalization.
- wnba-oracle/src/wnba_oracle/common/feature_payload.py -- Shared decoding for the persisted WNBA feature payload shape.
- wnba-oracle/src/wnba_oracle/common/logging.py -- WNBA compatibility surface over oracle-core structured logging.
- wnba-oracle/src/wnba_oracle/common/paths.py -- Project-owned runtime path discovery.
- wnba-oracle/src/wnba_oracle/common/settings.py -- Pydantic-settings driven config. Single source of truth for env vars.

## wnba-oracle/src/wnba_oracle/db/
- wnba-oracle/src/wnba_oracle/db/__init__.py
- wnba-oracle/src/wnba_oracle/db/engine.py -- SQLAlchemy engine factory + Redis client helper.
- wnba-oracle/src/wnba_oracle/db/reads.py -- Canonical Postgres read helpers for training, backtest, and analysis scripts.

## wnba-oracle/src/wnba_oracle/eval/
- wnba-oracle/src/wnba_oracle/eval/__init__.py
- wnba-oracle/src/wnba_oracle/eval/conformal.py -- Mondrian Conformalized Quantile Regression (CQR).
- wnba-oracle/src/wnba_oracle/eval/contest_score.py -- Canonical realized contest scoring for offline evaluation.
- wnba-oracle/src/wnba_oracle/eval/cv.py -- Walk-forward purged + embargoed cross-validation.
- wnba-oracle/src/wnba_oracle/eval/metrics.py -- Calibration-first metrics: CRPS, reliability, ECE, quantile loss.
- wnba-oracle/src/wnba_oracle/eval/multiple_comparisons.py -- Multiple-comparisons guard for the rotation gate (#MC, D63).

## wnba-oracle/src/wnba_oracle/features/
- wnba-oracle/src/wnba_oracle/features/__init__.py
- wnba-oracle/src/wnba_oracle/features/corpus.py -- Assemble the two training corpora (D63, the Phase-1 keystone).
- wnba-oracle/src/wnba_oracle/features/game_features.py -- Per-player-game targets + schedule features: the train/serve parity anchor.
- wnba-oracle/src/wnba_oracle/features/game_script_minutes.py -- Game-script minutes redistribution (Tier 3).
- wnba-oracle/src/wnba_oracle/features/injury_cascade.py -- Injury-cascade minutes redistribution.
- wnba-oracle/src/wnba_oracle/features/provenance.py -- Feature-pipeline provenance hash.
- wnba-oracle/src/wnba_oracle/features/rolling.py -- Rolling-window features computed strictly before slate_date.
- wnba-oracle/src/wnba_oracle/features/serving_features.py -- Build head feature rows for a slate at serve time (D69 / Phase 2b).
- wnba-oracle/src/wnba_oracle/features/serving_schema.py -- Serve-time enrichment schema (pandera[polars]).
- wnba-oracle/src/wnba_oracle/features/spec.py -- Feature spec registry.

## wnba-oracle/src/wnba_oracle/ingest/
- wnba-oracle/src/wnba_oracle/ingest/__init__.py
- wnba-oracle/src/wnba_oracle/ingest/backfill.py -- WNBA contest backfill + corpus assembler.
- wnba-oracle/src/wnba_oracle/ingest/cache.py -- Lightweight file-system cache for ingest responses.
- wnba-oracle/src/wnba_oracle/ingest/contest_stats.py -- Real Sports contest endpoint adapters: /stats + /entries.
- wnba-oracle/src/wnba_oracle/ingest/identity.py -- Resolve Real Sports player_id → stats.wnba.com (`nba_api`) player_id.
- wnba-oracle/src/wnba_oracle/ingest/minutes_backfill.py -- Refresh wnba_game_logs from stats.wnba.com (nba_api).
- wnba-oracle/src/wnba_oracle/ingest/minutes_features.py -- Per-player minutes features from stats.wnba.com game logs (D55).
- wnba-oracle/src/wnba_oracle/ingest/odds.py -- The Odds API client for `basketball_wnba`.
- wnba-oracle/src/wnba_oracle/ingest/realsports.py -- Real Sports (web.realapp.com) WNBA scraper.
- wnba-oracle/src/wnba_oracle/ingest/rotowire.py -- RotoWire WNBA lineup scraper.

## wnba-oracle/src/wnba_oracle/modeling/
- wnba-oracle/src/wnba_oracle/modeling/__init__.py -- WNBA-owned model contracts and deterministic decision primitives.
- wnba-oracle/src/wnba_oracle/modeling/artifact.py -- Pure prediction helpers over an already-loaded model artifact.
- wnba-oracle/src/wnba_oracle/modeling/policy.py -- Immutable, versioned policy passed across the infrastructure/model seam.
- wnba-oracle/src/wnba_oracle/modeling/prediction.py -- Model-kernel spec building: per-player prediction tiers, sampling/field specs,
- wnba-oracle/src/wnba_oracle/modeling/provenance.py -- Canonical model-ingress fingerprints for replay and drift diagnosis.
- wnba-oracle/src/wnba_oracle/modeling/scoring.py -- Pure scoring and feature-extraction helpers for the model kernel.

## wnba-oracle/src/wnba_oracle/monitoring/
- wnba-oracle/src/wnba_oracle/monitoring/__init__.py

## wnba-oracle/src/wnba_oracle/picker/
- wnba-oracle/src/wnba_oracle/picker/__init__.py
- wnba-oracle/src/wnba_oracle/picker/field.py -- Ownership projection (field model).
- wnba-oracle/src/wnba_oracle/picker/game_script.py -- Game-script tier multipliers and blowout adjustments.
- wnba-oracle/src/wnba_oracle/picker/optimize.py -- Two-stage lineup optimizer.
- wnba-oracle/src/wnba_oracle/picker/payout.py -- Payout-curve loader and per-lineup EV computation.
- wnba-oracle/src/wnba_oracle/picker/popularity.py -- Draft-popularity estimator + anti-popularity contrarian adjustment.
- wnba-oracle/src/wnba_oracle/picker/sample.py -- Joint sampling via Gaussian copula on log-residuals.
- wnba-oracle/src/wnba_oracle/picker/stacking.py -- Pure helpers for contextual lineup-balance decisions.

## wnba-oracle/src/wnba_oracle/predict/
- wnba-oracle/src/wnba_oracle/predict/__init__.py
- wnba-oracle/src/wnba_oracle/predict/archetypes.py -- DFS value archetype classification.
- wnba-oracle/src/wnba_oracle/predict/availability.py -- Two-part availability model (D57, Tier 2).
- wnba-oracle/src/wnba_oracle/predict/base.py -- Base prediction functions: boost prior calibration and per-player volatility.
- wnba-oracle/src/wnba_oracle/predict/minutes.py -- Minutes x per-minute-rate real_score predictor (D55).
- wnba-oracle/src/wnba_oracle/predict/scoring.py -- Real Sports real_score reconstructed from the box line (D55).
- wnba-oracle/src/wnba_oracle/predict/stat_leverage.py -- Stat-leverage concentration analysis.
- wnba-oracle/src/wnba_oracle/predict/streak_quality.py -- Hot-streak quality assessment.

## wnba-oracle/src/wnba_oracle/scheduler/
- wnba-oracle/src/wnba_oracle/scheduler/__init__.py
- wnba-oracle/src/wnba_oracle/scheduler/antibot.py -- Anti-bot timing primitives.
- wnba-oracle/src/wnba_oracle/scheduler/cron.py -- WNBA cron command backed by the shared job runner.
- wnba-oracle/src/wnba_oracle/scheduler/job1.py -- Job 1: morning scrape + Real Sports re-auth + odds + RotoWire lineups.
- wnba-oracle/src/wnba_oracle/scheduler/job1_persist.py -- Job 1 persistence: enrichment UPSERTs and slate_meta timing writes.
- wnba-oracle/src/wnba_oracle/scheduler/job1_rotowire.py -- Job 1 RotoWire identity matching and injury-status interpretation.
- wnba-oracle/src/wnba_oracle/scheduler/job2.py -- Job 2: predict + freeze near tip. Redis SET NX + Postgres UPSERT.
- wnba-oracle/src/wnba_oracle/scheduler/job2_freeze.py -- Job 2 freeze persistence: append-only frozen_lineups writes.
- wnba-oracle/src/wnba_oracle/scheduler/job2_io.py -- Job 2 database read helpers.
- wnba-oracle/src/wnba_oracle/scheduler/job2_model.py -- Job 2 model-artifact loading and trained-head prediction.
- wnba-oracle/src/wnba_oracle/scheduler/job2_scoring.py -- Compatibility exports for model scoring helpers.
- wnba-oracle/src/wnba_oracle/scheduler/job2_specs.py -- Call-compatible exports for the historical Job 2 prediction module.
- wnba-oracle/src/wnba_oracle/scheduler/job2_timing.py -- Job 2 freeze-timing gates.
- wnba-oracle/src/wnba_oracle/scheduler/job_backfill.py -- Backfill job1_enrichment head_features for all historical slates.
- wnba-oracle/src/wnba_oracle/scheduler/job_dayclose.py -- Day-close cron: capture yesterday's finalized WNBA contest and extend
- wnba-oracle/src/wnba_oracle/scheduler/job_runtime.py -- WNBA-owned job registration and lifecycle hooks.
- wnba-oracle/src/wnba_oracle/scheduler/live_ownership.py -- Same-day live ownership capture (#38 / F6).
- wnba-oracle/src/wnba_oracle/scheduler/placements.py -- Closed-loop placement / calibration tracking.
- wnba-oracle/src/wnba_oracle/scheduler/placements_calibration.py -- Pure calibration math for the placement feedback loop: DB-free,
- wnba-oracle/src/wnba_oracle/scheduler/shadow.py -- Model shadow-eval: run a challenger head over the same enrichment as
- wnba-oracle/src/wnba_oracle/scheduler/shadow_knobs.py -- Knob-overlay shadow harness (2026-07-04, follow-up to model shadow D95).
- wnba-oracle/src/wnba_oracle/scheduler/watchdog.py -- Watchdog: pipeline-health checks + persistence + operator surface.
- wnba-oracle/src/wnba_oracle/scheduler/watchdog_checks.py -- Watchdog pipeline-health checks.
- wnba-oracle/src/wnba_oracle/scheduler/watchdog_drift.py -- Watchdog rolling prediction-drift metrics (dayclose-only).

## wnba-oracle/src/wnba_oracle/schemas/
- wnba-oracle/src/wnba_oracle/schemas/__init__.py -- Pandera schemas at every module boundary.
- wnba-oracle/src/wnba_oracle/schemas/ingest.py -- Pandera schemas for ingest-layer dataframes.

## wnba-oracle/src/wnba_oracle/train/
- wnba-oracle/src/wnba_oracle/train/__init__.py
- wnba-oracle/src/wnba_oracle/train/calibrators.py -- Calibration helpers.
- wnba-oracle/src/wnba_oracle/train/cli.py -- Training CLI: oracle-train.
- wnba-oracle/src/wnba_oracle/train/eb_baseline.py -- Empirical-Bayes hierarchical baseline.
- wnba-oracle/src/wnba_oracle/train/lgbm_heads.py -- LightGBM quantile heads for the multi-task pipeline.
- wnba-oracle/src/wnba_oracle/train/models.yaml
- wnba-oracle/src/wnba_oracle/train/pipeline.py -- Top-level training pipeline.

## wnba-oracle/tests/
- wnba-oracle/tests/__init__.py
- wnba-oracle/tests/conftest.py -- Pytest fixtures shared across the suite.

## wnba-oracle/tests/fixtures/
- wnba-oracle/tests/fixtures/rotowire_lineups.html -- Static frontend page

## wnba-oracle/tests/fixtures/realsports/
- wnba-oracle/tests/fixtures/realsports/contest_1840_2026-05-26.json -- (test fixture data)
- wnba-oracle/tests/fixtures/realsports/home_next_2026-05-26.json -- (test fixture data)
- wnba-oracle/tests/fixtures/realsports/leaderboard_entries.json -- (test fixture data)
- wnba-oracle/tests/fixtures/realsports/search_a_2026-05-26.json -- (test fixture data)

## wnba-oracle/tests/integration/
- wnba-oracle/tests/integration/test_runtime_boundaries.py -- Acceptance tests against real PostgreSQL and Redis services.

## wnba-oracle/tests/unit/
- wnba-oracle/tests/unit/test_all_tiers_integration.py -- End-to-end integration: all three D57 tiers armed at once.
- wnba-oracle/tests/unit/test_analyze_stacking_decisions.py -- Pure helper tests for read-only stacking-decision analytics.
- wnba-oracle/tests/unit/test_anchor_floor.py -- Tier 1 lineup anchor floor (D57): the optimizer must field >= min_anchors
- wnba-oracle/tests/unit/test_api_app.py -- Compatibility and dependency-health coverage for the WNBA API factory.
- wnba-oracle/tests/unit/test_archetypes.py -- DFS value archetype classification.
- wnba-oracle/tests/unit/test_artifact_io.py -- Artifact persistence and integrity compatibility tests.
- wnba-oracle/tests/unit/test_artifact_serving.py -- Tests for the D45 wiring: job2 loads the trained PickerArtifact and
- wnba-oracle/tests/unit/test_availability.py -- Two-part availability model (D57, Tier 2).
- wnba-oracle/tests/unit/test_availability_wired.py -- Availability model (D57, Tier 2) wired into job2._build_specs.
- wnba-oracle/tests/unit/test_backfill_game_identity.py -- Pure planning-logic tests for the game_id backfill script (#32).
- wnba-oracle/tests/unit/test_backfill_outcomes.py -- Truthful Real Sports historical-backfill completion semantics.
- wnba-oracle/tests/unit/test_backfill_player_slate_ownership.py -- Pure planning-logic tests for the player_slate_ownership backfill (D90/#38).
- wnba-oracle/tests/unit/test_backtest_walkforward.py -- Point-in-time ownership in scripts/backtest_walkforward.py.
- wnba-oracle/tests/unit/test_boost_cap.py -- Lineup boost caps.
- wnba-oracle/tests/unit/test_boost_tail_lift.py -- Stage-1 ranking uses rank_pred_override when set (2026-07-04 boost-tail lift).
- wnba-oracle/tests/unit/test_cache.py -- File cache round-trip + TTL semantics. Mocks CACHE_DIR to a tmp_path.
- wnba-oracle/tests/unit/test_ceiling_sigma.py -- Environment-conditioned ceiling sigma scaling.
- wnba-oracle/tests/unit/test_committed_order_objective.py -- The optimizer objective under committed vs per-draw slot assignment.
- wnba-oracle/tests/unit/test_conformal.py -- MondrianCQR sanity tests.
- wnba-oracle/tests/unit/test_connector_catalog.py -- Stable, value-free connector catalog contract.
- wnba-oracle/tests/unit/test_contest_score.py -- Contest scoring, checked against the platform's own arithmetic.
- wnba-oracle/tests/unit/test_contest_stats.py -- Unit tests for contest_stats parsing.
- wnba-oracle/tests/unit/test_contextual_stacking.py -- Contextual stacking policy, identity, and decision-trace tests.
- wnba-oracle/tests/unit/test_contract_schemas.py -- External-API schema contract tests.
- wnba-oracle/tests/unit/test_corpus.py -- Feature+target corpus keystone (D63).
- wnba-oracle/tests/unit/test_corpus_backup_integrity.py -- Pure integrity tests for the off-platform corpus backup and restore tools.
- wnba-oracle/tests/unit/test_corpus_matchup_enrichment.py -- D77: _enrich_corpus_matchup adds team_pace/opp_pace/opp_dvp to the corpus.
- wnba-oracle/tests/unit/test_cron_pause.py -- cron.py: PICKS_PAUSE_START/END skips job1/job1late/job2, never dayclose.
- wnba-oracle/tests/unit/test_cron_runtime_validation.py -- Production cron entry points fail closed before running without dependencies.
- wnba-oracle/tests/unit/test_cv_splitter.py -- WalkForwardSplitter invariants.
- wnba-oracle/tests/unit/test_dayclose_actual_ownership.py -- D90/#38: _auto_record_placement also persists per-player actual_ownership
- wnba-oracle/tests/unit/test_dayclose_outcomes.py -- Truthful completion semantics for required and optional day-close work.
- wnba-oracle/tests/unit/test_dayclose_placement_catchup.py -- Placement catch-up sweep: recent slates with a frozen lineup but no
- wnba-oracle/tests/unit/test_dayclose_placement_score.py -- The realized score dayclose records must be the committed-order score.
- wnba-oracle/tests/unit/test_dayclose_verify_ops.py -- Durable, credential-free evidence for scheduled day-close verification.
- wnba-oracle/tests/unit/test_db_engine.py -- Isolation and boundedness for application database engine factories.
- wnba-oracle/tests/unit/test_db_utils.py -- normalize_postgres_url is consumed in three places (db/engine.py,
- wnba-oracle/tests/unit/test_determinism_compare.py -- Content-based artifact comparison for the determinism gate.
- wnba-oracle/tests/unit/test_dossier.py -- Unit and integration tests for dossier entry and gap computation.
- wnba-oracle/tests/unit/test_dossier_api.py -- #35 phase 3 / #39: read-only dossier API surface.
- wnba-oracle/tests/unit/test_feature_payload.py
- wnba-oracle/tests/unit/test_features_cohort.py -- Spec / cohort assignment tests.
- wnba-oracle/tests/unit/test_field_measured_ownership.py -- Field-ownership model: measured-drafts path (D86).
- wnba-oracle/tests/unit/test_field_stack_aware.py -- Stack-aware correlated field simulation.
- wnba-oracle/tests/unit/test_freeze_append_fix.py -- Regression tests for the 2026-06-13 freeze outage.
- wnba-oracle/tests/unit/test_freeze_idempotency.py -- Lock the true-freeze semantics in job2._freeze.
- wnba-oracle/tests/unit/test_frozen_append.py -- D82: append-only freeze writes in job2._freeze.
- wnba-oracle/tests/unit/test_game_script.py -- Game-script tier multipliers + blowout penalty.
- wnba-oracle/tests/unit/test_game_script_minutes.py -- Game-script (blowout) minutes redistribution.
- wnba-oracle/tests/unit/test_game_script_wired.py -- Game-script (blowout) minutes redistribution wired into job2._build_specs.
- wnba-oracle/tests/unit/test_game_stack.py -- Hard anti-stacking policy in the optimizer.
- wnba-oracle/tests/unit/test_head_tier0.py -- D69 / Phase 2b: the D63 trained-head Tier-0 path in job2._build_specs.
- wnba-oracle/tests/unit/test_identity_resolver.py -- Unit tests for the identity resolver. No network: uses the static catalog.
- wnba-oracle/tests/unit/test_import_boundaries.py -- Regression tests for static infrastructure and model import boundaries.
- wnba-oracle/tests/unit/test_injury_cascade.py -- Injury-cascade minutes redistribution.
- wnba-oracle/tests/unit/test_job1_game_context_recovery.py
- wnba-oracle/tests/unit/test_job1_lite.py -- Credit-free confirmed-lineup refresh.
- wnba-oracle/tests/unit/test_job1_pool_gate.py -- D84: degraded job1 pool is a hard error, not a quiet log line.
- wnba-oracle/tests/unit/test_job2_name_fallback.py -- D50: the frozen lineup must never ship a `Player <id>` placeholder when a
- wnba-oracle/tests/unit/test_job_backfill_outcomes.py -- Truthful completion semantics for the on-demand enrichment backfill.
- wnba-oracle/tests/unit/test_job_runtime.py -- WNBA registration, heartbeat, and dead-man surface tests.
- wnba-oracle/tests/unit/test_knob_shadow.py -- Knob-overlay shadow harness (2026-07-04, follow-up to model shadow D95).
- wnba-oracle/tests/unit/test_late_refreeze.py -- D75: late re-freeze path in job2._freeze(force=True).
- wnba-oracle/tests/unit/test_leaderboard_labels.py -- D85: supplemental slate_labels from top-20 finisher lineups.
- wnba-oracle/tests/unit/test_lineup_history.py -- D82: append-only lineup API surface.
- wnba-oracle/tests/unit/test_live_ownership.py -- #38/F6: same-day live ownership capture gating and safety.
- wnba-oracle/tests/unit/test_logging_httpx_redact.py -- httpx logs the full request URL (incl. query-string secrets like The Odds
- wnba-oracle/tests/unit/test_metrics.py -- Metrics tests: CRPS, coverage, ECE.
- wnba-oracle/tests/unit/test_minutes_backfill.py -- wnba_game_logs refresh (D102): row mapping and truthful outcomes.
- wnba-oracle/tests/unit/test_minutes_model.py -- Minutes/role model (D55): scoring formula, predictor, ingest, job2 wiring.
- wnba-oracle/tests/unit/test_model_boundary.py -- Versioned policy and input fingerprints at the infrastructure/model seam.
- wnba-oracle/tests/unit/test_model_research_benchmark.py -- Pure helper tests for the model research benchmark script.
- wnba-oracle/tests/unit/test_model_tournament.py
- wnba-oracle/tests/unit/test_model_validity_audit.py -- Model-validity audit (#53 umbrella): machine-readable characterization of
- wnba-oracle/tests/unit/test_multiple_comparisons.py -- Multiple-comparisons guard: CPCV splitter + deflated-edge test (D63).
- wnba-oracle/tests/unit/test_objective_shaping.py -- Objective-shaping terms (D87, Phase 1): leverage / ceiling / duplication.
- wnba-oracle/tests/unit/test_opp_dvp_lookup.py -- D74: build_opp_dvp_lookup computes per-opponent mean real_score allowed.
- wnba-oracle/tests/unit/test_ops_common.py -- Secret-safety tests for the portable production automation helpers.
- wnba-oracle/tests/unit/test_optimizer_input_contract.py -- The optimizer's two player views form one ID-keyed model contract.
- wnba-oracle/tests/unit/test_optimizer_team_cap.py -- max_per_team constraint in the optimizer.
- wnba-oracle/tests/unit/test_ownership_capture.py -- D90/#38: job2's post-freeze projected-ownership recording.
- wnba-oracle/tests/unit/test_payout_vectorized.py -- #13a: vectorized expected_payout / payouts_for_ranks must be numerically
- wnba-oracle/tests/unit/test_per_player_frozen.py -- Lock the per_player JSON contract in the frozen lineup payload.
- wnba-oracle/tests/unit/test_picker.py -- Lineup optimizer unit tests.
- wnba-oracle/tests/unit/test_placements.py -- Placement / calibration tracking (D90, Phase 2).
- wnba-oracle/tests/unit/test_player_props.py -- D80: per-event player-prop fetch + parse.
- wnba-oracle/tests/unit/test_popularity.py -- Anti-popularity contrarian adjustment + draft-popularity estimator.
- wnba-oracle/tests/unit/test_pre_freeze_guard.py -- Tests for the durable Job 1 pre-freeze evidence check.
- wnba-oracle/tests/unit/test_project_paths.py
- wnba-oracle/tests/unit/test_prop_signal.py -- D78: sportsbook prop-signal multiplier in job2._prop_signal_multiplier.
- wnba-oracle/tests/unit/test_reads_point_in_time.py -- Point-in-time safeguards on the label-corpus read helpers.
- wnba-oracle/tests/unit/test_realsports_parse.py -- Parser tests for the Real Sports pool response. Hits no network.
- wnba-oracle/tests/unit/test_realsports_pool_fallback.py -- Targeted-search fallback in `fetch_pool_for_date`.
- wnba-oracle/tests/unit/test_recompose.py -- predict_real_score recompose helpers + fallback (D63, Phase 2).
- wnba-oracle/tests/unit/test_refreeze_lock_gate.py -- D83: the late re-freeze lock gate.
- wnba-oracle/tests/unit/test_resolve_ops_window.py
- wnba-oracle/tests/unit/test_rolling.py -- Rolling-window tests against a synthetic per-player game log.
- wnba-oracle/tests/unit/test_rotowire_parse.py -- RotoWire HTML parse coverage (D100 fix).
- wnba-oracle/tests/unit/test_rotowire_url.py -- D74: RotoWire URL + CSS selector fix.
- wnba-oracle/tests/unit/test_rotowire_wired.py -- RotoWire injury wiring: job1 persists is_out into features_json,
- wnba-oracle/tests/unit/test_sampling_offset.py -- score_offset (K) calibration in the copula sampler (D52).
- wnba-oracle/tests/unit/test_schemas.py -- Pandera schema sanity checks. Validate that good frames pass and obvious
- wnba-oracle/tests/unit/test_secret_contract.py
- wnba-oracle/tests/unit/test_serving_schema.py -- Serve-time enrichment schema validator (features/serving_schema.py).
- wnba-oracle/tests/unit/test_settings_pause.py -- picks_paused_on / picks_resume_date: the operator-directed pause window.
- wnba-oracle/tests/unit/test_shadow.py -- Tests for scheduler.shadow. Pure metric compute + writer contract.
- wnba-oracle/tests/unit/test_slate_api.py -- D104: /slate/{date} timing endpoint feeding the tip-relative countdown.
- wnba-oracle/tests/unit/test_slate_clock.py
- wnba-oracle/tests/unit/test_slate_meta.py -- D83: slate timing capture (job1) feeding the late-refreeze lock gate.
- wnba-oracle/tests/unit/test_slot_scheme.py -- Pin the WNBA Real Sports slot multiplier scheme.
- wnba-oracle/tests/unit/test_smoke.py -- Sanity tests that the package imports and the api app builds.
- wnba-oracle/tests/unit/test_source_assurance.py -- Observational source assurance must never influence recommendation math.
- wnba-oracle/tests/unit/test_stack_alignment_check.py -- Security regression tests for the legacy stack-alignment diagnostic.
- wnba-oracle/tests/unit/test_starter_minutes_lift.py -- Minutes-conditional starter lift + mid-slot floor tilt (2026-07-10).
- wnba-oracle/tests/unit/test_starter_signal.py -- job2 starter-signal multiplier from the RotoWire starter flag (D52, D104).
- wnba-oracle/tests/unit/test_stat_leverage.py -- Stat-leverage concentration analysis.
- wnba-oracle/tests/unit/test_streak_quality.py -- Hot-streak quality assessment.
- wnba-oracle/tests/unit/test_train_cli.py
- wnba-oracle/tests/unit/test_upcoming_games_pool.py -- D109: scope the optimizer pool to games that have not tipped yet.
- wnba-oracle/tests/unit/test_verify_durable_job.py -- Tests for bounded durable job verification.
- wnba-oracle/tests/unit/test_watchdog.py -- Watchdog trigger logic — pure function tests against a mocked engine.
- wnba-oracle/tests/unit/test_watchdog_monitor_ops.py -- Schedule-aware tests for the independent production monitor.
- wnba-oracle/tests/unit/test_workflow_setup_contract.py -- Keep independent hosted jobs on the same portable Python contract.


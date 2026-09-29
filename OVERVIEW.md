# Sports Oracle: Portfolio Overview

Generated reference doc. Purpose: give any session, on any surface, full
structural context on first read, i.e. what exists and what it does. It does
**not** cover auth, credentials, process, or operational status; those live
in root `AGENTS.md` (portfolio rules + sync process) and each app's
`AGENTS.md` / `STATUS.md` (domain rules + live state), which this doc points
to rather than duplicates. For an exhaustive per-file listing, see `FILES.md`
(generated, not hand-maintained).

## What this is

A Python monorepo: one domain-free shared platform (`oracle-core`) plus four
independent sport applications (`wnba-oracle`, `nfl-oracle`, `nba-oracle`,
`nhl-oracle`). Each app owns its models, features, strategy, scoring,
calendar, and provider adapters. Dependency direction is one-way: sport
application to `oracle-core`. Sport apps never import each other or
`oracle-core` domain code back.

The portfolio product goal is stated once in root `README.md` (Product goal).
Do not restate it here; each sport `README.md` points at that section and at
its own `STATUS.md` for current serve knobs.

## Monorepo layout

Three layers. Dependency direction is sport application to `oracle-core`.
Apps do not import each other. `oracle-core` does not import an app.

| Layer | Path | Owns |
|---|---|---|
| Root | `AGENTS.md`, `README.md`, `OVERVIEW.md`, `ENTRY_POINTS.md`, `Makefile`, `pyproject.toml`, `.github/workflows/`, `scripts/`, `drive/` | Portfolio rules, product goal, this map, entry/auth recipes, shared CI, portfolio helpers |
| Platform | `packages/oracle-core/` | Domain-free infrastructure only |
| Apps | `wnba-oracle/`, `nfl-oracle/`, `nba-oracle/`, `nhl-oracle/` | Models, features, scoring, calendars, providers, jobs, serve knobs |

`drive/` is scratch. It points here; it is not a second copy of this map.
`FILES.md` is the generated per-file list.

## Win stack

Product goal (one statement): root `README.md`. The stack that pursues it:

Shape-and-condition campaign (#653). Learn the shapes of every HV/TDV
board appearance over history, learn the slate conditions that produced
each shape, and at T-40 match shape and condition with the sport-owned
model to commit the 5-player lineup that maximizes capture of that
slate's Highest value / Total Value board, with Ollama on top as
LLM-internal runs-on-shape. Ollama learns and tilts into the existing
optimizer and serve. It never replaces ridge, math, valuelaw, or a
sport-owned model. Models stay in the sport app. `oracle-core` stays
domain-free. Same-slate settlement features stay off the live clock. The
train record is a schema.org FeatureSpec and condition Observation. Do
not restore NFL blend 0.75. Near-term slate facts stay in each app
`STATUS.md`.

1. **Label.** Real Sports Highest value / Total Value boards
   (`highestBoostedValuePlayers`). Prior users' winning drafts are a
   reference bar, not the fit target.
2. **Own model, inside the app.** WNBA serve primary is empirical-Bayes
   (`WNBA_SERVE_PRIMARY`, code default `eb`). NFL serve math is valuelaw
   plus feature ridge. NHL projection v0 (Real `primaryValue` per prior
   GP) feeds the hosted T-40 runner (#675). LightGBM is not the primary. No new model stack lives
   in `oracle-core`.
3. **Ollama, on top of that model path.** `scripts/ollama_hv_watcher` is
   LLM-internal runs-on-shape. Learn ticks and, when armed, tilt go into
   the existing optimizer and serve. It never replaces ridge, math,
   valuelaw, or a sport-owned model. It is not a serve primary and it does
   not publish a freeze. Gate and commands: `ENTRY_POINTS.md` and
   `scripts/ollama_hv_watcher/README.md`.
4. **T-40 runner, per sport.** Table below. Portfolio Ollama arms at the
   earliest supplied T-40; that arm is a learn window, not a freeze.
5. **Knobs.** Code defaults live in each app `README.md`. Live Railway
   values live only in that app's `STATUS.md`.
6. **Backtest race.** `oracle_core.race` plus `oracle_core.fitness`
   (WIN/CLOSE band). The app supplies the backtest. Workflows
   `wnba-race.yml` and `nfl-race.yml` dispatch that work.
7. **Contest-max map.** `oracle_core.contest_max` scores a supplied pool
   under `value * (slot_multiplier + card_boost)`. It compares the HV
   display five (`value * (2 + card_boost)`), the raw-value five, and a
   draft-count chalk five. Draft count is a comparison bar, never a
   label. Measured tables live in each app `STATUS.md`. Inventory and
   the remaining research list live in
   `drive/2026-09-28-contest-max-history-map.md` (issue #633).

### T-40 runner map

| Sport | Who freezes | Code | Watch / guard | Hosted? |
|---|---|---|---|---|
| WNBA | `job2` once at first tip minus `FREEZE_LEAD_MINUTES` (code default 40) | `wnba_oracle.scheduler.job2`, `api/slate.py` | `wnba-pre-freeze-guard.yml`, `wnba-oracle/scripts/pre_freeze_guard.py` | Yes. Schedules in `wnba-oracle/STATUS.md` |
| NFL | worker publish at contest cutoff minus 40 minutes | `nfl_oracle.recommendations.pipeline`, `recommendations/cli.py` (`waiting_for_t40`) | `nfl-t40-watchdog.yml`, `nfl_oracle.recommendations.watchdog`, `nfl-oracle/scripts/nfl_t40_watchdog.py` (alert only; does not publish) | Yes. Worker facts in `nfl-oracle/STATUS.md` |
| NHL | `nhl-pipeline worker` at earliest Real game start minus 40 minutes (`scheduler.t40`) | `nhl_oracle.scheduler.runner`, `scheduler/live_cycle.py`, `service/lineup_store.py` | `nhl-t40-watchdog.yml` (public schedule alert) | `nhl-pipeline worker` collects the Real pool, freezes at T-40, persists; `nhl-api` `/lineup/{date}` serves it (#675, `nhl-oracle/STATUS.md`) |
| NBA | none | none | none | No freeze runner |
| Portfolio | Ollama learn window at min(T-40) of supplied live windows | `scripts/ollama_hv_watcher` | coverage manifest gate (#526) or `SPORTS_OLLAMA_UNLOCK=1` | Codespace helper, not a freeze publisher |

### Connectors

Interfaces, not secret values. WNBA's stable catalog is
`wnba_oracle.assurance.connectors` (ids include `realsports`, `rotowire`,
`the_odds_api`, `wnba_stats`, `postgres`, `redis`, `model_artifact`,
`railway`, `github_actions`, `espn`, `wnba_api`, `frontend`). Other sports
do not share that catalog.

| Connector | Where it is wired |
|---|---|
| Real Sports session | Portfolio contract in `AGENTS.md`. App clients: `wnba_oracle.ingest`, `nfl_oracle.ingest.realsports`, `nhl_oracle.ingest.realsports`. NBA Corpus G gate records blocked coverage and exits non-zero when the process has no `REALSPORTS_*` material. |
| Railway | `ENTRY_POINTS.md`. Per-sport services and knobs: that app's `STATUS.md`. |
| Sibling contest corpus | `scripts/realsports_corpus/`, `oracle_core.realsports_corpus`, `oracle_core.hv_board_corpus`. Workflows `hv-leaderboard-corpus.yml`, `realsports-corpus-append.yml`. |
| Game-stats matchup append | `oracle_core.corpus_matchup`. Each app has `scripts/append_game_stats_matchup.py`. Workflow `game-stats-matchup-corpus.yml`. |
| Ollama HTTP | `scripts/ollama_hv_watcher/client.py` (localhost serve). Training inventory: `training_data_manifest.json`. |
| Public history | NHL: `nhl_oracle.history_loader` (official NHL API) and `nhl-history-nightly.yml`. NBA: `nba_oracle.history_loader` (`data.nba.com`) via `nba-history-load`. Observation only. |
| Draft Stats catalog | `oracle_core.draft_stats_catalog` lists section names. Parsing stays in the owning app. |

## oracle-core (`packages/oracle-core/src/oracle_core/`)

Domain-free technical infrastructure. 27 Python modules as of this sync,
including package `realsports_corpus/` (layout, manifest, store). Prefer
schema.org (and PROV-O / IPTC Sport Schema only where noted in `AGENTS.md`)
for shared entity contracts; see `schemaorg.py`. The package README is the
inline list; this table is the outline.

| Module | Purpose |
|---|---|
| `artifacts.py`, `dossier.py` | Artifact/snapshot handling; cross-sport post-slate dossier |
| `cache.py`, `storage.py`, `config.py` | Cache, Postgres/Redis/lease primitives, process-environment config |
| `http.py`, `browser.py` | HTTP transport; Playwright session cleanup with guaranteed browser close |
| `jobs.py`, `dayclose.py`, `timing.py` | Job execution; day-close sweep; lead-time window arithmetic (no sport policy) |
| `logging.py`, `redaction.py` | Structured logging with secret redaction |
| `service.py`, `testing.py` | Service scaffolding; shared test helpers |
| `schemaorg.py`, `high_tv.py` | schema.org / JSON-LD constructors; high-TV board helpers |
| `contest_max.py` | Five-card display rank, chalk comparison, hindsight ceiling (#633) |
| `race.py`, `fitness.py` | WIN/CLOSE backtest race (search, genetics, elite band). Domain-free |
| `draft_stats_catalog.py`, `hv_board_corpus.py` | Draft Stats section inventory; HV board document helper (#526) |
| `realsports_corpus/` | Sibling-repo layout, coverage manifest, store |
| `corpus_matchup.py` | Idempotent `{sport}/{season}/{game_id}/` matchup + stats append |
| `slate_advice.py` | Freshness and clamped tilt map for optional app influence (#574) |

## wnba-oracle

Production app: API, cron roles, day-close, frontend (Vite + React),
Postgres, Redis. Service list and live knobs: `STATUS.md`. Stable contract:
`README.md`.

`src/wnba_oracle/` subpackages (Python file counts at this sync):

| Subpackage | Files | Purpose |
|---|---|---|
| `scheduler/` | 27 | Jobs, including T-40 freeze in `job2` |
| `features/` | 13 | Feature engineering, including `rs_field_map` |
| `ingest/` | 11 | Provider ingest |
| `eval/` | 10 | Evaluation, including highest-value grading |
| `api/`, `picker/`, `predict/` | 8 each | HTTP API; lineup selection; inference |
| `common/` | 7 | Settings and app-local utilities (serve knobs) |
| `modeling/`, `train/` | 6 each | Model definitions; training |
| `lineage/` | 4 | Feature/signal lineage |
| `assurance/`, `corpus/`, `db/` | 3 each | Connector catalog; contest corpus export; DB access |
| `audit/`, `schemas/` | 2 each | Audit trail; schema definitions |
| `monitoring/`, `ops/` | 1 each | Monitoring hooks; ops helpers |

## nfl-oracle

Railway API + worker are in production use for read-only research and
freeze/grade. Contest entry stays forbidden. Live facts: `STATUS.md`.
Frontend is a static `index.html` (no build pipeline).

`src/nfl_oracle/` subpackages (Python file counts at this sync):

| Subpackage | Files | Purpose |
|---|---|---|
| `recommendations/` | 21 | Live pipeline: prepare/publish/lock, optimizer, T-40 watchdog, CLI |
| `strategy/` | 16 | Five-card legality, clocks, scoring algebra |
| `contests/` | 11 | Contest archive parsing, including Corpus C HV export |
| `baselines/`, `features/` | 10 each | Ridge / priors / walk-forward; own-model feature map |
| `replay/` | 9 | Historical contest replay, including `nfl-contest-max-map` |
| `data/` | 8 | Coverage and catalog helpers |
| `ingest/` | 7 | Corpus G ingest and Real Sports client |
| `identity/` | 6 | Player identity resolution |
| `calendar/`, `valuelaw/` | 5 each | Season/week resolution; box-score to contest-value model |
| `providers/` | 4 | Provider adapters |
| `common/`, `labels/`, `service/` | 3 each | Shared utilities; value-label schema; research API |

## nba-oracle

Not an empty package. `src/nba_oracle/` has `api/` (health only),
`calendar/`, `data/`, `ingest/` (Corpus G gate, no HTTP client wired), and
`history_loader.py` (public `data.nba.com`, observation only). No model, no
T-40 runner, no contest optimizer. Staging shell facts: `STATUS.md`.

## nhl-oracle

Read-only contract audit, identity, redacted ingest, labels, baselines,
contest algebra, zero-boost gate, and a T-40 freeze skeleton. Staging API /
worker runs the hosted T-40 runner (#675) and the API serves its lineup.
No contest entry. Progress: `STATUS.md`. Roadmap: `README.md`.

`src/nhl_oracle/` subpackages (Python file counts at this sync):
`contract/` 5, `ingest/` 6, `baselines/` 4, `identity/` 3, `scheduler/` 3
(`t40.py`, `freeze.py`), `contest/` 3, `labels/` 3, `service/` 3,
`calendar/` 2, `common/` 2, `eval/` 2, `features/` 2. Plus
`history_loader.py` at the package root.

## Root-level files

`README.md`, `AGENTS.md` (with `CLAUDE.md` and `.cursorrules` symlinks):
portfolio purpose and agent rules. `CONTRIBUTING.md`, `ENTRY_POINTS.md`,
`APPLICATION_GUIDE.md`, `BENCHMARK_TASK.md`: process and onboarding (not
duplicated here). `Makefile`, `pyproject.toml`, `uv.lock`: build and
dependency root.

`scripts/`: portfolio tooling (`auth-check`, `write-path-check`,
`codespace-push`, `codespace-railway-env`, boundary checks) plus
`ollama_hv_watcher/`, `corpus/`, `realsports_corpus/`, `rs_corpus/`, and
`tests/`. `.github/workflows/` holds 26 workflow files, including the T-40
guard/watchdog, race, corpus, and history jobs named above.
`.devcontainer/`: Codespace environment. `drive/`: scratch; see
`drive/README.md`.

## Keeping this synchronized

`FILES.md` is regenerated by `scripts/generate_file_manifest.py` (extracts
each Python file's first docstring line / each Markdown file's H1); it is
never hand-edited. Run `scripts/generate_file_manifest.py --check` to verify
it is current; run it without `--check` to rewrite it. This document
(`OVERVIEW.md`) is the hand-maintained outline. Each app `README.md` is the
inline contract for that sport. A new top-level subpackage or app is a
signal to update this file. Python file counts above are from the tree at
the docs sync for issue #594; `FILES.md` is the exhaustive list after that.
Neither file covers auth, credentials, or operational status; see `AGENTS.md`
and each app's `STATUS.md` for that.

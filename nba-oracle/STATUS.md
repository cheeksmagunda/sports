# Status

## Win stack index (#594)

Pointer only. Not a new live check.

- Code contract: no model, no T-40 runner, no serve knobs, HV export stub
  exits 78, history loader is observation-only. See `README.md` (Win stack).
- Partial `nba_history_*` counts and Railway shell: sections below.
- Ollama is not an NBA model. LLM-internal runs-on-shape sits on top of
  a sport model and never replaces one. Role and shape-and-condition
  campaign (#653): root `../OVERVIEW.md` (Win stack). NBA has no train
  path yet.

## History corpus gap (#453 / #489)  -  2026-09-27

## Total Value HV leaderboard corpus (#526)  -  2026-09-27

- No Real Sports contest / `draftStats` / HV ingest yet.
- Stub only: `nba-oracle/scripts/export_hv_board.py` exits 78 (fail-closed).
- Portfolio layout contract: `oracle_core.hv_board_corpus` + workflow
  `hv-leaderboard-corpus.yml` (separate corpus repo).

## Railway mono-project shell (verified non-serving) (#457)  -  2026-09-27

- Public `nba-history-load` (data.nba.com) writes `nba_history_*` into
  `sports-oracle` / `nba-staging` Postgres over public TCP.
- **Partial load verified:** games ~2086, player rows ~70912, then blocked by
  data.nba.com HTTP 403 (Akamai) under high concurrency.
- **Empty / incomplete DB blocker:** full complete-season coverage for
  2021-22..2024-25 is **not** claimed. Re-run with `--concurrency 4` after
  cool-down. Do not treat health-scaffold Online as history-ready.
- Real Sports variable presence is in the Railway table below. No contest entry.


Last verified: 2026-09-28 (T-40 pool/runner/Railway audit, issue #600).
History row counts and the public TCP proxy remain the 2026-09-27 check
(`scripts/codespace-railway-env`, issue #504 / PR #489).

This file records application state only.

## Application state

- Package: `nba-oracle` workspace member
- Scope live now: health-only FastAPI (`GET /health`) + NBA calendar /
  coverage vocabulary + auth-blocked `nba-corpus-g-backfill` gate +
  observation-only T-40 freeze gate in `scheduler/` (not mounted, not hosted)
- Deploy surface: `nba-oracle/Dockerfile` + `nba-oracle/railway.toml`
  (DOCKERFILE builder; health-only image lineage from #486; no Playwright in
  the serving image)
- Calendar: `NEXT_REGULAR_SEASON_OPEN = 2026-10-20`; tracked seasons
  `2002`..(current Eastern season label) for Corpus G planning
- Ingest: `nba-corpus-g-backfill` gate writes a blocked coverage matrix and exits
  non-zero without portfolio `REALSPORTS_*`; HTTP Corpus G client not wired yet.
  Separate observation-only path: `nba-history-load` loads public `data.nba.com`
  schedule/gamedetail into Postgres over public TCP (`sslmode=require`), no Real
  Sports auth.
- Public history tables (target): `nba_history_games`, `nba_history_player_games`,
  `nba_history_season_coverage`. Verified counts: games **2086**, player rows **70912** (partial; see section below).
- Not started: schemas, modeling, contest entry, nightly worker. The
  freeze gate does not submit lineups and does not run on Railway.

## Railway mono (`sports-oracle` / `nba-staging`, env `7ac1e6f8-…`)

Verified 2026-09-27 from Codespace. Non-serving scaffold only (#457 / #504).

| Service | Source | Last observed | Notes |
| --- | --- | --- | --- |
| `nba-api` | `cheeksmagunda/sports` `main` (connected) | SUCCESS `c4d41d74-bb69-4af3-8a9d-415c9d1b91b1` at `e636040` (created 2026-09-28T02:57:26Z). Newer deploy `e31bf446-f7c6-4723-92a1-a9b9eebf90f8` at `578566d` still QUEUED at 2026-09-28T03:02Z. | DOCKERFILE. Public domain `https://nba-api-nba-staging.up.railway.app`. `GET /health` 200 `{"status":"ok","version":"0.1.0"}` at 2026-09-28T03:02:55Z. Health-only. |
| `nba-worker` | no source block | Offline. Latest deployment `70f255ac-cd29-4586-b98e-9ac0c71a4aa6` FAILED (2026-09-27T02:43:25Z), builder RAILPACK. | Leave disconnected. Variable name `REALSPORTS_STORAGE_STATE_B64GZ` is defined; value not read. Offline with no source is not a live session. |
| `nba-frontend` | no source block | Offline. Latest deployment `0e4a9020-9d79-43a6-8221-61c53cf1d9fb` FAILED (2026-09-27T01:57:38Z), builder RAILPACK. | No frontend package. Leave disconnected. |
| `nfl-frontend` | not rechecked 2026-09-28 | unverified this session | Stray service id `57ea95df-dede-461c-8164-5cb5d3c5ebf7` is still listed on the project. Not an NBA serving path. |
| `Postgres-6eeu` | n/a | not rechecked 2026-09-28 | Volume and partial history counts in the section below were verified 2026-09-27. This audit did not re-query row counts. |

No contest features on the API. Serving is not dual-firing: only `nba-api` is source-connected, and it serves `GET /health`. Worker and frontend stay source-disconnected.


## T-40 WIN readiness (#600)  -  2026-09-28

No live NBA slate to freeze. `NEXT_REGULAR_SEASON_OPEN` remains `2026-10-20`.
This issue does not redeploy, reconnect, or edit Railway variables.

### Pool

`nba-oracle` had no player-pool or freeze module before this change. No live
pool was fetched. `scheduler.pool.evaluate_draftable_pool` counts only games
whose tip is still ahead of the decision clock, so a tipped game cannot leave
a later window permanently `incomplete_player_pool`. An unobserved player on
a still-draftable game fails closed. Five distinct observed players are
required (`fewer_than_five_candidates`). That size matches the portfolio
five-card T-40 gate. Live NBA contest law is unverified, and this is not a
provider roster claim.

`run_freeze_cycle` collects, then reads `decision_at`, then stamps one
evidence epoch for that tick so in-collect aging does not raise
`stale_player`. Optional future feature rows are skipped by name. A required
future row fails closed as `future_feature:<name>`. Refusal reasons are on
the job result. `contest_entry` is false.

### Runners

No GitHub Actions workflow runs an NBA T-40 freeze.
`hv-leaderboard-corpus.yml` can be dispatched with sport `nba` and then runs
`nba-oracle/scripts/export_hv_board.py`, which exits 78. `nba_freeze_cycle`
is role `worker` only, lease `nba:freeze_cycle`, and is not mounted on the
health API. Nothing hosted executes it. The Ollama app helper reads NFL and
WNBA freeze APIs only (`scripts/ollama_hv_watcher/adapters/app_api.py`); NBA
has no freeze route for that helper to copy.

### Railway and docs

Service state is the table in **Railway mono** above. `README.md` describes
the freeze-gate shape. Health image routes stay `GET /` and `GET /health`.

## Public NBA history staging load (#453 / #489)  -  2026-09-27

Verified from Codespace `fluffy-zebra-g4gqq746477q2jg` against
`sports-oracle` / `nba-staging` Postgres-6eeu via public TCP
(`trolley.proxy.rlwy.net`, `DATABASE_PUBLIC_URL`, `sslmode=require`; never
`railway.internal`).

Loader: `nba-history-load` / `nba_oracle.history_loader` (public
`data.nba.com` schedule + gamedetail).

Verified table counts after partial backfill:
- `nba_history_games`: **2086**
- `nba_history_player_games`: **70912**
- `nba_history_season_coverage`: **3**

Verified season coverage rows (partial; Akamai 403s interrupted later passes):
- 2021-22: scheduled **1317**, loaded **988**, failed **329**, status `partial`
- 2022-23: scheduled **1314**, loaded **741**, failed **573**, status `partial`
- 2023-24: scheduled **1312**, loaded **357**, failed **955**, status `partial`
  (coverage timestamp from an earlier interrupted pass; games may overlap)

Blocker: Codespace egress began receiving HTTP 403 from `data.nba.com` after
high-concurrency fetches. Re-run with concurrency<=4 after cool-down to raise
coverage toward complete. Observation-only; not Real Sports labels; no contest
entry.

## Boundaries

- NBA domain behavior stays in `nba-oracle`
- Shared technical abstractions may move to `oracle-core` only after proven
  provider-neutral use across multiple sports
- No contest entry code in this package

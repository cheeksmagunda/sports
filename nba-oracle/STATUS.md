# Status

## Win stack index (#594)

Pointer only. Not a new live check.

- Code contract: no model, no T-40 runner, no serve knobs, HV export stub
  exits 78, history loader is observation-only. See `README.md` (Win stack).
- Partial `nba_history_*` counts and Railway shell: sections below.
- Ollama is not an NBA model. Role: root `../OVERVIEW.md`.

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
- No Real Sports credential on NBA services. No contest entry.


Last verified: 2026-09-27 (public history partial load + TCP proxy verified)
`scripts/codespace-railway-env`, issue #504 / PR #489)

This file records application state only.

## Application state

- Package: `nba-oracle` workspace member
- Scope live now: health-only FastAPI (`GET /health`) + NBA calendar /
  coverage vocabulary + auth-blocked `nba-corpus-g-backfill` gate
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
- Not started: schemas, modeling, scheduling, contest logic, nightly worker

## Railway mono (`sports-oracle` / `nba-staging`, env `7ac1e6f8-…`)

Verified 2026-09-27 from Codespace. Non-serving scaffold only (#457 / #504).

| Service | Source | Last observed | Notes |
| --- | --- | --- | --- |
| `nba-api` | `cheeksmagunda/sports` (connected) | Online | Deployment id `c35dd53b-…` Online (post-queue). No public domain. External `/health` therefore unverified from outside Railway. |
| `nba-worker` | not shown / Failed | Failed | Leave disconnected until Real Sports auth + nightly are authorized. |
| `nba-frontend` | not shown / Failed | Failed | No frontend package; leave disconnected. |
| `nfl-frontend` | Offline | Offline | Stray service instance visible in `nba-staging`; not an NBA serving path. |
| `Postgres-6eeu` | n/a | Online | Volume `postgres-volume-jmAe`. Public TCP proxy ACTIVE (`trolley.proxy.rlwy.net`). `DATABASE_PUBLIC_URL` set with `sslmode=require`. Public history present (partial): games **2086**, players **70912**. |

No public NBA domain. No contest features. No Real Sports credential verified on NBA services. Serving is not dual-firing for NBA: only `nba-api` is Online (queued rebuild); worker/frontend Failed/Offline.


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

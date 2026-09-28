# Ollama HV/TDV helper on each sport app's daily picks

Portfolio Codespace helper tracked by
[#574](https://github.com/cheeksmagunda/sports/issues/574).

## What it is (and is not)

Sports Oracle is LLM-internal. This package is the internal LLM layer that
drives runs on shape: learn ticks, and tilt when a sport app arms it. It
is not a chatbot and not decoration. The one-sentence objective is in root
`README.md`'s pointer to `OVERVIEW.md` (Win stack, #653). Product goal:
root `README.md` **Product goal**.

Each sport app fires its own T-40 freeze and publishes its five-player
lineup. Ollama does not publish that freeze.

- It only READS each app's public API (`adapters/app_api.py`, stdlib
  `urllib`, bounded timeout and retry, no credentials).
- Every learn tick's `five_player_lineup` is exactly the app's five in the
  app's slot order (`lineup_source=app_frozen_lineup`). The tick records
  that shape. It does not replace, reorder, block, or delay the freeze.
- Tilt is the armed path into the NFL picker (`NFL_OLLAMA_TICK_TILT_WEIGHT`,
  default 0, identity). Weight 0 does not open the tick file.
- If Ollama is down or times out the tick is still written with
  `notes="ollama_unavailable"` (or `ollama_gate_forbidden` when the gate is
  closed), so the app's five are always recorded.

## Pre-game only (leak stop)

Live advice only ever sees pre-game data. A board used for a live tick must
carry `phase: "pregame"` and is refused (`LIVE_DATA_REQUIRED`) when
`game_status` is final or any player carries `real_score`, `score`, or an
`actual*` field. Pregame prompts and lineups never emit `real_score`.

Live discovery reads only `data/ollama_hv/<sport>/<slate_id>/hv_board.json`
for slates armed right now. Post-game boards load only through the explicit
history path (`--once --history-board PATH`, ticks under
`data/ollama_hv/history/`); they are never auto-discovered.

## App API adapter

Base URLs come from the environment only:

| Env | App |
| --- | --- |
| `SPORTS_OLLAMA_NFL_API_URL` | nfl-oracle recommendations API (`/slate/{day}`, `/lineup/{day}`) |
| `SPORTS_OLLAMA_WNBA_API_URL` | wnba-oracle API (`/slate/{day}`, `/lineup/{day}`) |

Missing env fails closed. Current public URLs live in each app's
`STATUS.md`; the helper hardcodes none.

Window per slate (`slate_window`):

- NFL: freeze target is the app's `cutoff_at` (run details before freeze,
  top level after) minus the app's `next_freeze` lead (40 minutes when not
  exposed, copied from nfl-oracle). Close is last kickoff + 3h + 1h, the
  constants copied from nfl-oracle `calendar/week_close.py`. Before the
  freeze the app lists no games, so `cutoff_at` stands in for the last
  kickoff; the daemon re-reads the window every poll and the close extends
  once the frozen snapshot lists its games.
- WNBA: freeze target is the app's `freeze_target_utc` against
  `contest_lock_utc` or `first_tip_utc`. The app exposes only the first
  tip, so close is lock + 6h (helper-owned constant; it only bounds how long
  the helper stays alive).

`frozen_board` returns `None` until the app freezes, refuses anything but
exactly five picks, a snapshot the app marks `stale`, or another day's
answer, and writes the pregame board atomically to
`data/ollama_hv/<sport>/<day>/hv_board.json`. Board `value` is NFL
`projected_value`; WNBA exposes no per-player projected value, so `value`
is the model's pre-game `pred_real_score_p50` (never an actual score).

## Commands for today

```sh
bash scripts/ollama_hv_watcher/install_codespace.sh
export SPORTS_OLLAMA_NFL_API_URL=...   # from nfl-oracle/STATUS.md
export SPORTS_OLLAMA_WNBA_API_URL=...  # from wnba-oracle/STATUS.md
DAY=$(TZ=America/New_York date +%F)

# 1. Windows from the apps (usable as SPORTS_OLLAMA_WINDOWS_JSON):
PYTHONPATH=scripts python -m ollama_hv_watcher --windows-from-apps \
  --day "$DAY" --sports nfl,wnba
export SPORTS_OLLAMA_WINDOWS_JSON="data/ollama_hv/windows/$DAY.json"
PYTHONPATH=scripts python -m ollama_hv_watcher --status

# 2. Daemon: polls each app per armed slate, ticks once per app freeze,
#    exits after the latest close. --execute calls Ollama (needs the gate).
SPORTS_OLLAMA_UNLOCK=1 nohup env PYTHONPATH=scripts \
  python -m ollama_hv_watcher --daemon --day "$DAY" --sports nfl,wnba \
  --execute --ensure-serve > data/ollama_hv/daemon.log 2>&1 &
ls data/ollama_hv/*/"$DAY"/   # hv_board.json + tick_*.json
```

Offline fixture calendars (synthetic day 2000-01-03) are tests only:
`--once --allow-fixtures`.

## Gate

- Binary install + `ollama serve`: allowed on the Codespace now.
- Training / `ollama generate`: FORBIDDEN until
  `coverage_manifest.historical_capture_complete` (#526), unless
  `SPORTS_OLLAMA_UNLOCK=1`. Without `--execute` ticks are dry runs that
  still record the app's five and the prepared prompt.

## Five players every day

Contest card size is fixed at **5** (`FIVE_PLAYER_LINEUP_SIZE` in
`pick.py`). App boards must carry exactly five players with slots 1..5;
anything else fails closed.

Default model: `llama3.2:3b`. Artifacts under gitignored `data/ollama_hv/`.

Each learn tick also refreshes `latest_tick.json` in the same slate directory
(stable pointer for tooling / env-gated NFL picker tilt).

## NFL picker tilt (default off)

Live freeze authority stays Corpus G → ridge → `max_value` → freeze →
frontend. Tilt is how an armed tick drives a run on that shape. Ollama
does not publish the freeze. Mount a tick onto the worker and arm it:

```sh
NFL_OLLAMA_TICK_TILT_WEIGHT=0.15   # 0 = identity (production default)
NFL_OLLAMA_TICK_TILT_PATH=/path/to/data/ollama_hv/nfl/<slate>/latest_tick.json
```

Weight 0 never opens the file. Positive weight fail-closes if the path is
missing or the tick lacks an exact five-player card. Do not arm on a live
freeze window without an explicit operator decision.

`client.generate_json` posts `/api/generate` with `format=json` and returns
one object. NFL candidate scoring loads that module from
`nfl_oracle.recommendations.ollama_engine`. Lineup rules stay in nfl-oracle.

## Training-data inventory

Machine-readable board roots + gate pointers live in
`training_data_manifest.json` (loader: `training_manifest.py`). Use it to
point `--board-root` / sparse corpus hydrates at HV/TDV sources without
guessing paths.

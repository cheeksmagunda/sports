# Ollama HV/TDV self-learning slate watcher

Portfolio Codespace helper tracked by
[#574](https://github.com/cheeksmagunda/sports/issues/574).

## Five players every day

Contest card size is fixed at **5** (`FIVE_PLAYER_LINEUP_SIZE` in
`pick.py`). Every learn tick writes an ordered `five_player_lineup` of
exactly five distinct players. Boards with fewer than five ranked players
fail closed.

## Chalk vs multiplier (encoded in every tick)

Ticks include `principle`, `slot_multipliers` `[2.0, 1.8, 1.6, 1.4, 1.2]`,
and `serve_shape` `{nfl: max_value, wnba: total_draft_value}`. Prompts
require: true HV/TDV in high slots even when chalk; fade soft chalk; never
chase ownership alone. Board digests expose `drafts` as the chalk proxy.

## Live only (no placeholders)

Default discovery refuses fixture calendars. Supply LIVE windows via
`--windows-json` or `SPORTS_OLLAMA_WINDOWS_JSON`. Missing or ambiguous
fields raise `LIVE_DATA_REQUIRED` (exit 4). Opt-in fixtures for offline
tests only: `--allow-fixtures`.

## Gate

- Binary install + `ollama serve`: allowed on the Codespace now.
- Training / `ollama generate`: FORBIDDEN until
  `coverage_manifest.historical_capture_complete` (#526), unless
  `SPORTS_OLLAMA_UNLOCK=1`.

## Window math

`portfolio_window(slates)` returns `arm_at=min(T-40)`, `close_at=max(close)`,
with `is_active(now)`.

## Commands

```sh
bash scripts/ollama_hv_watcher/install_codespace.sh
# LIVE windows required:
SPORTS_OLLAMA_WINDOWS_JSON=/path/to/live_windows.json \
  PYTHONPATH=scripts python -m ollama_hv_watcher --status
SPORTS_OLLAMA_UNLOCK=1 SPORTS_OLLAMA_WINDOWS_JSON=/path/to/live_windows.json \
  PYTHONPATH=scripts python -m ollama_hv_watcher --daemon
# Offline tests only:
PYTHONPATH=scripts python -m ollama_hv_watcher --once --allow-fixtures --dry-run
```

Default model: `llama3.2:3b`. Artifacts under gitignored `data/ollama_hv/`.

## Optional app influence (default OFF)

Closed loop for T-40 (does **not** replace the app's five-card size):

1. Codespace writes `data/ollama_hv/<sport>/<day>/advice.json` via
   `--advice` (pre-freeze; uses an HV board, not the frozen five).
2. Push the file onto the worker volume with
   `scripts/ollama_hv_watcher/push_advice_to_volume.sh <day> <sport>`
   (no redeploy).
3. Apps tilt projected scores only when env is on:
   - `NFL_OLLAMA_INFLUENCE=1` + `NFL_OLLAMA_ADVICE_PATH=...`
   - `WNBA_OLLAMA_INFLUENCE=1` + `WNBA_OLLAMA_ADVICE_PATH=...`
   Optional HTTP: `NFL_OLLAMA_ADVICE_URL` / `WNBA_OLLAMA_ADVICE_URL`.
4. Stale / missing / wrong-slate advice is ignored (identity). Mults clamp
   to `[0.85, 1.15]`. Frontend still reads each app's `/lineup/{day}`.

**Merge timing:** every merge to `main` redeploys Railway workers. Do not
merge inside ~2h of NFL 16:20Z / WNBA 17:20Z freezes unless influence stays
Codespace-side only. Prefer merge with ≥5h buffer, land default-OFF code,
then set influence=1 + advice path in the same Railway change so one
redeploy settles before the 2h buffer.

```sh
SPORTS_OLLAMA_UNLOCK=1 PYTHONPATH=scripts python -m ollama_hv_watcher \
  --advice --board path/to/hv_board.json --execute --model llama3.1:8b
bash scripts/ollama_hv_watcher/push_advice_to_volume.sh 2026-09-27 nfl
```

## Training-data inventory

Machine-readable board roots + gate pointers live in
`training_data_manifest.json` (loader: `training_manifest.py`). Use it to
point `--board-root` / sparse corpus hydrates at HV/TDV sources without
guessing paths.

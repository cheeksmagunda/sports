# Ollama HV/TDV self-learning slate watcher

Portfolio Codespace helper tracked by
[#574](https://github.com/cheeksmagunda/sports/issues/574).

## Five players every day

Contest card size is fixed at **5** (`FIVE_PLAYER_LINEUP_SIZE` in
`pick.py`). Every learn tick writes an ordered `five_player_lineup` of
exactly five distinct players. Boards with fewer than five ranked players
fail closed.

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
PYTHONPATH=scripts python -m ollama_hv_watcher --status
PYTHONPATH=scripts python -m ollama_hv_watcher --once --dry-run
SPORTS_OLLAMA_UNLOCK=1 PYTHONPATH=scripts python -m ollama_hv_watcher --daemon
```

Default model: `llama3.2:3b`. Artifacts under gitignored `data/ollama_hv/`.

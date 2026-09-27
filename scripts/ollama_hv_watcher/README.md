# Ollama HV/TDV self-learning slate watcher

Portfolio Codespace helper tracked by
[#574](https://github.com/cheeksmagunda/sports/issues/574).

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

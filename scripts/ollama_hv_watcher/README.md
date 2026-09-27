# Ollama HV/TDV self-learning slate watcher (#574)

Codespace helper that arms at the earliest T-40 across discovered sport
slate windows and stays until the latest slate close. Writes learning
notes under gitignored `data/ollama_hv/`.

## Gate

Training / `ollama generate` requires either:

- `coverage_manifest.historical_capture_complete` (see #526), or
- `SPORTS_OLLAMA_UNLOCK=1` (Codespace helper override only)

Install + `ollama serve` healthchecks are always allowed.

## CLI

From the repo root (scripts on `PYTHONPATH`):

```sh
cd scripts
python -m ollama_hv_watcher status
python -m ollama_hv_watcher plan --windows-json ollama_hv_watcher/fixtures/calendars/sample_day.json
SPORTS_OLLAMA_UNLOCK=1 python -m ollama_hv_watcher learn --board ollama_hv_watcher/fixtures/hv_board_sample.json
SPORTS_OLLAMA_UNLOCK=1 nohup python -m ollama_hv_watcher watch \
  --windows-json ollama_hv_watcher/fixtures/calendars/sample_day.json \
  --ensure-serve >../data/ollama_hv/watcher.log 2>&1 &
```

## Offline tests

```sh
make test-core   # includes scripts/tests via root Makefile scripts/tests target
# or:
uv run --frozen --package oracle-core --extra dev python -m pytest scripts/tests/test_ollama_hv_watcher.py -q
```

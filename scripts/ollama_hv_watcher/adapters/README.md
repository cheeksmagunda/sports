# Ollama HV helper adapters (#574)

`app_api.py` is the only adapter: a read-only, stdlib `urllib` client over
each sport app's public API (bounded timeout and retry, no credentials).

- `slate_window(sport, day)`: watch window from the app's own cutoff /
  freeze target.
- `frozen_board(sport, day)`: the app's frozen five as a `phase=pregame`
  board, or `None` before the app freezes.
- `windows_payload(day, sports)`: `SPORTS_OLLAMA_WINDOWS_JSON` payload.

Base URLs come from `SPORTS_OLLAMA_NFL_API_URL` and
`SPORTS_OLLAMA_WNBA_API_URL` only. Current URLs live in each app's
`STATUS.md`. No sport-app imports.

# NHL connector map

NHL freezes and serves a hosted five through `nhl-pipeline worker` (#675). Readiness stays in `STATUS.md`. Do not copy NFL or WNBA env onto
NHL services from this file.

## Chain

```
Real /home/nhl/next (day, daily contest, games)
        -> Real /games/{id}/sport/nhl/players (full pool, injuryStatus, rankings)
        -> scheduler.runner projection v0 (primaryValue / public prior GP, shrunk)
        -> evaluate_win_freeze_readiness (full pool, zero-boost gate, T-40)
        -> contest algebra, ordered five, slots (2.0, 1.8, 1.6, 1.4, 1.2)
        -> nhl_t40_lineups on nhl-staging Postgres (preview, then frozen)
        -> nhl-api GET /lineup/{date}, GET /readiness

RS contest HV section (gap: no durable multi-contest corpus yet)
        -> labels.hv (highestBoostedValuePlayers)
        -> priors / future ridge-valuelaw (no LightGBM primary)
```

`export_hv_board.py` exits 78 until a real board writer exists.
`report_hv_corpus_gap` is the honest empty-corpus report. Do not invent
labels.

`contract.boost_gate` keeps boost at zero until every franchise has at
least one regular-season game played. That gate is the early-season ON
state. Runner env on `nhl-worker`: `DATABASE_URL` (nhl-staging Postgres),
`REALSPORTS_STORAGE_STATE_B64GZ` (root `../AGENTS.md` contract), optional
`NHL_T40_RUNNER=0` kill switch and `NHL_PRIMARY_VALUE_SEASON_ID`.

Ollama is not an NHL publisher. Contest entry stays off.

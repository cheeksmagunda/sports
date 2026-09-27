# Real Sports separate corpus plan (#526)

Offline history so models train/grade on (1) today's slate + boost pool and
(2) this corpus — no daily full-history Real Sports re-scrape.

## Layout (separate GitHub-tracked corpus repo)

```
realsports-corpus/
  README.md
  manifest.json                 # sport/slate/game coverage + sha256
  nfl/
    hv_boards/YYYY/MM/DD.json   # highestBoostedValuePlayers (+ every key)
    game_stats/{game_id}.json   # /games/{id}/sport/nfl/stats every key
    contest/{contest_id}/       # meta, draftStats, boostControl, payoutInfo
  wnba/ ...
  nba/ ...
  nhl/ ...
  workflows/ append-nightly.yml # idempotent append from monorepo Actions
```

Monorepo holds only the **scaffold** (this directory + `dump_exposed_keys.py`).
Payload bytes live in the separate corpus; Railway/workers read volume or
release artifacts. Never mint Real Sports credentials here.

## Must scrape every slate/game

1. Total Value / Highest value leaderboards (`highestBoostedValuePlayers`)
2. Game stats + matchups (box scores, opponents, home/away, pace context)
3. Contest/pool/draftStats/boosts — dump **every exposed key** for replay

## Local inventory (no auth)

```sh
python scripts/rs_corpus/dump_exposed_keys.py drive/nfl_fixtures/*.json
```

## Labels

Train / grade on HV boards only. Winning drafts are never the primary target
(see #523 / #505).

# NHL connector map

NHL has the five-card policy in code and does not yet publish a hosted
freeze. Readiness stays in `STATUS.md`. Do not copy NFL or WNBA env onto
NHL services from this file.

## Chain

```
RS contest HV section (gap: no durable multi-contest corpus yet)
        -> labels.hv (highestBoostedValuePlayers)
        -> priors / future ridge-valuelaw (no LightGBM primary)
        -> contest algebra, ordered five, slots (2.0, 1.8, 1.6, 1.4, 1.2)
        -> scheduler.t40 (lock minus 40 minutes)
        -> hosted freeze: not wired
        -> nhl-api / nhl-frontend: staging health and page only
```

`export_hv_board.py` exits 78 until a real board writer exists.
`report_hv_corpus_gap` is the honest empty-corpus report. Do not invent
labels.

`contract.boost_gate` keeps boost at zero until every franchise has at
least one regular-season game played. That gate is the early-season ON
state. There is no MNF-style env checklist because nothing here freezes a
live card.

Ollama is not an NHL publisher. Contest entry stays off.

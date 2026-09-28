# WNBA T-40 connector map

WNBA owns its freeze. It does not import NFL picker knobs or NFL env names.
Live serve values stay in `STATUS.md`. The product goal stays in root
`../README.md`. The machine-readable connector catalog, with credential
classes and no secret values, is `src/wnba_oracle/assurance/connectors.py`
(`CONNECTORS`, `DECISION_INPUT_CONNECTOR_IDS`).

## Chain

```
Real Sports + optional public signals (RotoWire, odds, stats)
        -> ingest / features
        -> serving model (EB when WNBA_SERVE_PRIMARY is unset)
        -> optimizer (total_draft_value, payout top_1)
        -> tip-relative T-40 freeze (job2)
        -> Postgres
        -> wnba-api
        -> frontend
```

The freeze clock is `first_tip - freeze_lead_minutes` in
`wnba_oracle.scheduler.job2` (40 minutes by default). It is not NFL's
cutoff-minus-40 gate. Ollama may read the published five afterward. It
does not choose it. See `scripts/ollama_hv_watcher/README.md`.

## Highest value

Train and grade on `highestBoostedValuePlayers`. `popularPlayers`,
`mostCommon3xPlayers`, winning lineups, and NFL `mostDrafted` are recorded
states, not the fit target (`oracle_core.draft_stats_catalog`). Year span
of the WNBA HV rows is a `STATUS.md` fact, not restated here.

## Env that must be on

Names only. Last verified process values are in `STATUS.md`. This session
does not re-query Railway.

| Env | Required state |
| --- | --- |
| `OPTIMIZER_OBJECTIVE_MODE` | `total_draft_value` |
| `PAYOUT_REGIME` | `top_1` |
| `WNBA_SERVE_PRIMARY` | unset, so the code default `eb` applies, unless STATUS records an explicit override |
| `DATABASE_URL` | present on API and job2 |
| `REALSPORTS_STORAGE_STATE_B64GZ` | present for Real Sports jobs. Portfolio contract is root `AGENTS.md` |

`OPTIMIZER_MAX_VALUE_OWNERSHIP_FADE` and `LIVE_OWNERSHIP_CAPTURE_ENABLED`
are additional serve knobs. Their last verified values stay in `STATUS.md`.
Ownership fade is not permission to fit on draft-count chalk.

## Stay off

- Fitting on winning drafts or the popular / most-drafted sections
- Treating `SPORTS_OLLAMA_UNLOCK` as the freeze switch
- Contest entry from this map

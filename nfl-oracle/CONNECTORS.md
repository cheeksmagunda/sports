# NFL T-40 connector map

Stable hook graph for a five-card freeze. Live knob values, deployment ids,
and incidents stay in `STATUS.md`. The portfolio product goal stays in root
`../README.md`. This file is the required-ON contract for Monday Night
Football and every other NFL slate.

There is no neural-net serving head. The model that freezes the five is
stdlib ridge (`nfl_oracle.baselines.ridge`, `recommendations.model`,
`baselines.value_model`). Ollama does not sit in that path.

## Chain

```
Corpus G boxes + Corpus C / HV boards + nflverse schedule + NWS weather
        -> features (live context + ridge core)
        -> ridge
        -> picker knobs
        -> optimizer (objective total_value, profile max_value)
        -> T-40 freeze (worker)
        -> Postgres
        -> nfl-api  /lineup/{day}
        -> static frontend
```

Ollama is a side reader. After the app freezes, the Codespace helper may
copy that same five and write a note. It does not feed the ridge, the
picker, the optimizer, or the freeze. Commands and the leak stop live in
`scripts/ollama_hv_watcher/README.md`.

| Hop | Owner | What crosses the hop |
| --- | --- | --- |
| Corpora | `ingest`, `contests`, `calendar`, `recommendations.sources` | Real `value` history, Highest value boards, public schedule, pre-lock weather |
| Features | `features.live`, `features.rs_aliases`, `features.own_model_map` | Force-included context vector plus ridge core priors |
| Ridge | `recommendations.model.RatingModel`, `baselines.value_model.FeatureDrivenValueModel` | Projected Real value. No LightGBM, no PyTorch |
| Picker knobs | `recommendations.picker_knobs` | Post-predict blend of projected value with the provider card-boost rank |
| Optimizer | `recommendations.optimizer` | One ordered five. Objective is always `total_value` |
| Freeze | `recommendations.pipeline.freeze_due`, worker `nfl-pipeline` | Publish once at cutoff minus 40 minutes when `NFL_RECOMMENDATIONS_ENABLED` is on |
| Railway | `nfl-oracle-worker` writes, `nfl-api` reads | Same image, separate commands. Ids and health stay in `STATUS.md` |
| Frontend | `nfl-oracle/frontend`, packaged at `nfl_oracle/recommendations/frontend` | `GET /` plus `GET /lineup/{day}`. Shows the frozen five. Does not sort by draft count |

Contest entry stays hard off (`contest_entry: Literal[False]`). Nothing in
this map authorizes a submit.

## Corpora

Verified complete Corpus G on the mono worker volume is seasons **2024 and
2025** (stats, feed, and players). Earlier seasons are not claimed complete.
That verification date and the row counts live in `STATUS.md`. Do not treat
this paragraph as a new volume probe.

| Source | Years / window | Role | Not used as |
| --- | --- | --- | --- |
| Corpus G `playerBoxScores[].value` | 2024-2025 verified complete | Historical Real value for ridge priors and valuelaw | The slate Highest value board |
| Corpus C `draftStats.highestBoostedValuePlayers` | Whatever is on the volume under `NFL_CORPUS_C_ROOT` | Train / grade label via `recommendations.high_tv` | Draft-count rank |
| Sibling contest corpus | See `scripts/realsports_corpus/README.md` | Multi-year Real Sports payloads outside this checkout | A second train target |
| nflverse / nfldata `games.csv` | Public schedule file in `calendar.schedule` | Week identity and kickoff bucket, including Monday | A Real value label |
| NWS forecast | Pre-lock outdoor venues only | `weather_*` features. Missing or indoor stays `weather_available` false | A guessed magnitude |

Same-slate draft counts, winning drafts, and `mostDrafted` stay out of the
label. `high_tv_board_from_draft_stats` ranks `highestBoostedValuePlayers`
and ignores `draft_count`.

## Highest value, not draft-count chalk

Real Sports Daily Draft Stats shows Slot, Drafts, and Value on one board.
The column this path optimizes is **Value** (Highest value / Total Value).
The Drafts column is how often the field took the name. A high draft count
is chalk. It is not the objective.

Consequences already in code:

- Train and grade on `highestBoostedValuePlayers` (`oracle_core.draft_stats_catalog.HV_SECTION`).
- Optimizer objective is `total_value`. `max_value` drops the team/game floor to 1/1 so the highest projected total-value five can be committed even when it stacks one game.
- Attribution zeros a `prior_log_count` coefficient when that slot exists, so appearance frequency cannot explain a pick.
- `draft_stats_score`, `draft_stats_rank`, raw `did_not_play` / `started` / `minutes`, and `base_boosted_value` are leakage-blocked on the live slate. Use `prior_*` only.

`NFL_OPTIMIZER_FIELD_WEIGHT` (default 0.10) is a simulated-opponent re-rank
inside that total-value utility. It is not a switch to most-drafted names.
Leave it unset unless a later issue changes it.

## Features that must be on

These are not Railway toggles. `RatingModel` force-includes every name in
`REQUIRED_LIVE_OK_CONTEXT_FEATURES`, and `FeatureDrivenValueModel` appends
that same set beside `MODEL_FEATURE_NAMES`. A serving bundle that drops one
is not this contract.

Context (39):

`days_rest`, `home_away`, `injury_active`, `injury_body_part_available`,
`injury_body_part_hash`, `injury_dnp`, `injury_doubtful`, `injury_full`,
`injury_inactive`, `injury_ir`, `injury_limited`, `injury_out`,
`injury_questionable`, `injury_status_available`, `injury_suspended`,
`injury_unknown`, `is_divisional`, `is_home`, `kickoff_slot_early`,
`kickoff_slot_late`, `kickoff_slot_mnf`, `kickoff_slot_other`,
`kickoff_slot_snf`, `last_ten_wins`, `moneyline_available`,
`opp_def_value_allowed_prior`, `opponent_adjusted_prior`,
`opponent_moneyline`, `opponent_pace_prior`, `overall_rank`,
`prior_did_not_play`, `prior_minutes`, `prior_started`, `team_moneyline`,
`team_pace_prior`, `weather_available`, `weather_precip_prob`,
`weather_temp_f`, `weather_wind_mph`.

Ridge core:

`intercept`, `player_prior_mean`, `player_prior_median`,
`position_prior_mean`, `position_prior_median`, `global_prior_mean`,
`team_prior_mean`, `prior_n_games`, `pos_QB`, `pos_RB`, `pos_WR`, `pos_TE`,
`pos_K`.

Monday night: `kickoff_slot_name` returns `mnf` for any Monday kickoff in
US Eastern, and `kickoff_slot_features` sets `kickoff_slot_mnf` to 1 and
the other `kickoff_slot_*` keys to 0. No env var selects the bucket.

## Env that must be on for the freeze

Last live read of these values is the serve table in `STATUS.md`. This
contract says what the next MNF worker must be running. A wiped env must
still land on `max_value` because that is the code default in
`optimizer_config_from_env`.

| Env | Required state | Where |
| --- | --- | --- |
| `NFL_RECOMMENDATIONS_ENABLED` | `1` | `nfl-oracle-worker` only. This is the publish gate |
| `NFL_OPTIMIZER_PROFILE` | `max_value` (or unset) | worker and API |
| `NFL_PICKER_BOOST_RANK_BLEND` | `0.75` | worker and API |
| `NFL_PICKER_PROFILE` | `boost_0.75` | worker and API |
| `NFL_DATABASE_URL` | present | worker and API. Value stays in Railway |
| `REALSPORTS_STORAGE_STATE_B64GZ` | present on the worker | Compare copies by `sha256[:8]` only. Contract is root `AGENTS.md` |
| `NFL_DEVICE_UUID` | present | worker header harvest |
| `NFL_DEVICE_NAME` | present | worker header harvest |
| Volume | mounted at `/app/nfl-oracle/data` | `NFL_DATA_ROOT` defaults there |

`NFL_PICKER_POSITION_CALIBRATION` stays unset (identity 0) until a separate
issue flips it. `NFL_OPTIMIZER_MIN_DISTINCT_TEAMS` and
`NFL_OPTIMIZER_MIN_DISTINCT_GAMES` stay unset so the `max_value` preset
keeps the floor at 1 and 1.

## Stay off

Do not turn these on for the MNF freeze:

- `NFL_OPTIMIZER_PROFILE=diversified` (rollback only; diversity floor 3 teams / 2 games)
- Any train or optimize target of `mostDrafted`, `popularPlayers`, winning drafts, or raw Drafts count
- Live inputs `base_boosted_value`, `draft_stats_score`, `draft_stats_rank`, `did_not_play`, `started`, `minutes`, `card_boost_post_settlement`, `same_slate_final_value`, `same_slate_ownership`
- `SPORTS_OLLAMA_UNLOCK` as if it published the five. The unlock only allows the Codespace helper to call `ollama generate`. The freeze does not read it
- Contest submit. No env enables it

## Freeze and page

`freeze_due` is the slate cutoff minus 40 minutes. The worker publishes one
lineup and later polls do not replace it while the slate is still open.
`nfl-api` serves that row at `/lineup/{day}` and the static page at `/`.
The page states are waiting, five picks ready, or locked. It does not
render a Drafts leaderboard.

Railway project, environment, and the public API base URL are recorded in
`STATUS.md`. Re-read that file against Railway before treating a host as
current. This map does not copy those ids.

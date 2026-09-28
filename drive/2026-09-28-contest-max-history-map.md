# Historical contest maximization map

Status: done
Created: 2026-09-28
Owner: issue #633 (lineage #597, #603, #599)

Product goal stays in root `README.md`. Live Railway knobs stay in each app
`STATUS.md`. This brief is the inventory, the measurement method, and the
ranked research list. Capture ratios are copied into `nfl-oracle/STATUS.md`
and `wnba-oracle/STATUS.md` because those files own current measured facts.

## Scoring law

```text
item_score = value * (slot_multiplier + card_boost)
slots = 2.0, 1.8, 1.6, 1.4, 1.2
hv_display_key = value * (2.0 + card_boost)
```

`value` is the realized base. The hindsight ceiling pairs descending base
with descending slot multipliers (same rearrangement as
`nfl_oracle.replay.harness.best_lineup`). Draft count chooses the chalk five.
It is never a score and never a sample weight.

`player_results.highest_score` is not the rank key. On the 80 Highest-value
rows in the NFL backup, the max absolute gap versus `value * (2 + card_boost)`
is 3.445104 (2026-09-20).

## What this change wires

Highest-leverage unused signal: contest-display rank.

| Surface | Behavior |
|---|---|
| Train | `fit_model(..., contest_boosts=)` up-weights the display top five when a boost map is loaded. No map keeps raw-value top-k. Corpus G boxes have no `card_boost`, so an empty HV export dir leaves fingerprints unchanged. |
| Shared weights | `sample_weights_for_labeled_rows` uses `card_boost` when the attribute is present. Draft count is ignored. |
| HV export | `leaderboard_from_hv_section` orders by the display key. The stored `value` field stays the base. |
| Replay | `nfl-contest-max-map` writes the three fives and the ceiling. |
| Serve audit | `prepare` records `contest_display_top5` on `prepared_for_freeze`. The committed lineup is the optimizer result. |

Not wired, on purpose: display value is not added to the projected mean. The
exact search already multiplies boost when upside weight and field weight are
~0. `optimizer.py` is untouched (merged #616, open #619). Open #618 is
untouched; its raw top-k on HV labels should pass boosts after it merges
(backlog item 2).

This change does not set `NFL_PICKER_BOOST_RANK_BLEND`,
`NFL_OPTIMIZER_UPSIDE_WEIGHT`, or `NFL_OPTIMIZER_FIELD_WEIGHT`. On
2026-09-28 the names are present on `nfl-oracle-worker` in `nfl-production`.
This session could read names only. Do not revert the operator's live
blend=0, upside=0, field=0.

## Inventory

Checked out on `main` (code, not the million-line archives):

| Surface | Where | What it holds |
|---|---|---|
| Contest law helper | `packages/oracle-core/src/oracle_core/contest_max.py` | Display rank, chalk, ceiling, CSV/JSON loaders |
| High-TV weights | `oracle_core.high_tv` | Top-k sample weights; optional boost map |
| Draft Stats catalog | `oracle_core.draft_stats_catalog` | Section names. `leaderboard_lineup` is supplemental, not a board |
| HV document helper | `oracle_core.hv_board_corpus` | Sibling-repo board files |
| Corpus layout | `oracle_core.realsports_corpus` | `{sport}/{season}/{id}/` plus coverage manifest |
| NFL HV export | `nfl_oracle.contests.hv_export` | Corpus C `stats.json` to Total Value JSON |
| NFL replay ceiling | `nfl_oracle.replay.harness.best_lineup` | Same slot rearrangement |
| NFL field counterfactual | `nfl_oracle.contests.field` | Visible-pool counterfactual |
| WNBA contest score | `wnba_oracle.eval.contest_score` | App scoring. This change does not edit it |
| Ollama training inventory | `scripts/ollama_hv_watcher/training_data_manifest.json` | Watcher notes, not a serve primary |
| Freeze artifacts | NFL `frozen_lineups` / `prepared_decisions` on the `backups` branch | Full candidate pools (~150) with position and `game_id` |

`origin/backups` blobs scored in this session (not committed; `contest_leaderboards.csv` has `user_id` and stays out of git):

| Blob | Rows | Use |
|---|---|---|
| `wnba-oracle/data/backups/slate_labels.csv` | 7010 | 229 contests, 2025-05-16 through 2026-09-24. Sections: HV 4403, popular 1864, 3x 586, `leaderboard_lineup` 157 |
| `wnba-oracle/data/backups/contest_leaderboards.csv` | large | User lineups. Not a training target |
| `nfl-oracle/data/backups/player_results.csv` | 185 | 4 days: 2026-09-17, 20, 21, 24. Contests 2167, 2179, 2182, 2196 |
| `nfl-oracle/data/backups/frozen_lineups.csv` | 44 sequences | Position join and freeze game count for those four days |
| `nfl-oracle/data/backups/dayclose_grades.csv` | present | Not a five-card pool. Not scored here |
| `nfl-oracle/data/backups/prepared_decisions.csv` | present | Not scored here |

Pool rule in the CLI: board sections (HV, popular, 3x, most drafted) enter
the ceiling and the chalk. `leaderboard_lineup` and `My draft` are dropped.
Duplicate player rows keep HV membership and the max draft count. HV display
rank and raw rank use `highestBoostedValuePlayers` only.

Not re-counted this session:

- Corpus G on the Railway volume `/app/nfl-oracle/data`. The 2026-09-27 STATUS note says 668 games. Treat that count as prior, unverified here.
- Corpus C emptiness on the worker (PR #614). Unverified here.
- NBA and NHL HV boards. Catalog stubs only.

## Measured capture

Command: `nfl-contest-max-map` against the backup CSVs on 2026-09-28.
Capture is the five's optimal slot score divided by the hindsight ceiling
on that pool. The ceiling is the best five among rows in the file, not the
full freeze roster.

### WNBA (229 boards)

Regime is `team_count` (no `game_id` on these rows): two or fewer teams
read as `one_game`. Positions are absent, so every mix is
`position_unknown`.

| Slice | Boards | Display | Raw | Chalk |
|---|---:|---:|---:|---:|
| All | 229 | 0.996597 | 0.863336 | 0.432948 |
| multi_game | 220 | 0.996651 | 0.860487 | 0.423029 |
| one_game | 9 | 0.995274 | 0.932970 | 0.675422 |
| position_unknown | 229 | 0.996597 | 0.863336 | 0.432948 |

Overlap with the ceiling five: display 0.918777, raw 0.506550, chalk 0.081223.
Display minus raw capture: 0.133261.

HV-section boost tail, joined after the scorer:

| Boost slice | Boards | Display | Raw | Chalk |
|---|---:|---:|---:|---:|
| zero_boost | 4 | 1.0 | 1.0 | 0.527012 |
| has_3x_tail (boost >= 2.99) | 219 | 0.996684 | 0.860048 | 0.431768 |
| boosted, no 3x | 6 | 0.991138 | 0.892250 | 0.413318 |

### NFL (4 boards)

Positions come from the last freeze sequence's candidates for that date.
Freeze `games` is 1 on all four dates. The CLI regime uses team count on
`player_results` and disagrees on 2026-09-20 (21 team ids in the backup
rows, freeze slate says 1 game). Do not treat that day as a Sunday lesson
until the rows are reconciled.

| Date | Contest | CLI regime | Freeze games | Pool | HV | Ceiling | Display | Raw | Chalk | Ceiling mix |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 2026-09-17 | 2167 | one_game | 1 | 29 | 20 | 57.244905 | 1.0 | 0.924334 | 0.777843 | QB:2+RB:1+WR:2 |
| 2026-09-20 | 2179 | multi_game | 1 | 38 | 20 | 114.706247 | 0.997221 | 0.851815 | 0.351441 | K:1+unknown:4 |
| 2026-09-21 | 2182 | one_game | 1 | 30 | 20 | 103.190807 | 1.0 | 0.967633 | 0.763193 | DEF:2+QB:1+RB:1+WR:1 |
| 2026-09-24 | 2196 | one_game | 1 | 31 | 20 | 93.554760 | 1.0 | 0.858548 | 0.700719 | DEF:2+K:1+RB:1+WR:1 |

Means: display 0.999305, raw 0.900582, chalk 0.648299.
Overlap: display 0.95, raw 0.60, chalk 0.35.

Family counts across the four fives (2026-09-20 mostly unmatched to the
one-game freeze roster):

| Five | QB | RB | WR | TE | K | DEF | unknown |
|---|---:|---:|---:|---:|---:|---:|---:|
| Ceiling | 3 | 3 | 4 | 0 | 2 | 4 | 4 |
| Display | 3 | 3 | 4 | 0 | 2 | 4 | 4 |
| Chalk | 3 | 6 | 6 | 1 | 0 | 0 | 4 |

Two of the four visible ceilings contain two defenders. Freeze candidate
counts that day were 153, 152, 159, and 159. This table does not justify
changing `NFL_OPTIMIZER_MAX_DEFENDERS` or `NFL_OPTIMIZER_MAX_KICKERS`.

## Ranked backlog

1. Full-roster ceiling before any cap change. Acceptance: join realized
   value and card boost onto each freeze candidate pool (about 150 to 160
   on these one-game days) and recompute the hindsight five. Report whether
   `max_defenders=1` or `max_kickers=1` rejects that five. No Railway knob
   write in that PR.
2. After #618 merges, pass the boost map into its HV train-target weights.
   Acceptance: a base 3.4 with boost 3.0 outranks a base 5.0 with boost 0
   in the weight vector, and draft count still does not change the vector.
3. Hydrate Corpus C / HV boards onto the worker volume so
   `load_contest_boosts` finds files. Acceptance: `nfl-contest-max-map
   --root` on the worker export scores more than these four backup days,
   and a prepare audit shows `contest_display_boost_keys > 0` without an
   env flip. Corpus C emptiness from PR #614 was not re-checked here.
4. WNBA positions on slate labels. Acceptance: the history map's
   `by_position_mix` is not a single `position_unknown` bucket for a
   scored season.
5. WNBA `game_id` on the same rows. Acceptance: `regime_method` is
   `game_id` for those boards, and one-game versus multi-game no longer
   depends on team count.
6. Reconcile NFL 2026-09-20 contest 2179. Acceptance: the backup
   `player_results` team set and the freeze `games` list describe the same
   slate, then re-score that day.
7. Keep user lineups out of train. Acceptance: `boards_from_csv` still
   drops `leaderboard_lineup` and `My draft` (unit test), and no sample
   weight reads `contest_leaderboards.csv`.
8. NBA and NHL HV ingest. Acceptance: one board file per sport that
   `nfl-contest-max-map --root` can score, with the same three fives.
9. Do not copy display value into the projected mean. Acceptance: the
   committed lineup id list is unchanged when `contest_display_top5` is
   added to the prepare audit.

# Real Sports history corpus (#526)

Durable offline history so models run on (1) today's slate + boost pool and
(2) this corpus — **no daily full-history Real Sports re-scrape**.

Primary train/grade label: **Total Value / Highest-value leaderboard**
(`highestBoostedValuePlayers`).

## Sibling repo

Preferred destination: **`cheeksmagunda/sports-realsports-corpus`**
(separate GitHub-tracked repo; not the monorepo tree).

### Create (operator or agent with `repo` scope)

```sh
gh repo create cheeksmagunda/sports-realsports-corpus \
  --private \
  --description "Append-only Real Sports HV boards + game stats/matchups corpus (#526)" \
  --disable-wiki \
  --disable-issues
```

If auth cannot create repos, the operator creates that empty private repo once,
then set Actions secrets/vars on `cheeksmagunda/sports`:

| Name | Kind | Purpose |
|------|------|---------|
| `CORPUS_REPO` | var or secret | `cheeksmagunda/sports-realsports-corpus` |
| `CORPUS_REPO_TOKEN` | secret | contents:write on the corpus repo |
| `REALSPORTS_STORAGE_STATE_B64GZ` | secret | existing session (never mint) |

## Layout

```
{sport}/{season}/{slate_or_game_id}/{artifact}.json
coverage/manifest.json
```

Artifacts: `hv_board`, `draft_stats`, `pool_card`, `game_stats`, `matchups`,
`feed`. Schema: `scripts/corpus/schema/coverage_manifest.schema.json`.
Helpers: `oracle_core.realsports_corpus` + `oracle_core.hv_board_corpus`.

## Export paths (prefer durable stores first)

Zero Real Sports calls for proof:

```sh
# WNBA HV from backups-branch slate_labels.csv
git show origin/backups:wnba-oracle/data/backups/slate_labels.csv > /tmp/slate_labels.csv
uv run --frozen --package wnba-oracle python scripts/corpus/export_wnba_from_store.py \
  --corpus-root /tmp/sports-realsports-corpus \
  --labels-csv /tmp/slate_labels.csv --limit-slates 3

# NFL game_stats + matchups from Corpus G fixtures / volume
uv run --frozen --package nfl-oracle python scripts/corpus/export_nfl_from_corpus_g.py \
  --corpus-root /tmp/sports-realsports-corpus \
  --corpus-g-root nfl-oracle/tests/fixtures/corpus_g
```

One live WNBA HV append (Codespace login shell; sha8 only in logs):

```sh
python wnba-oracle/scripts/seed_storage_state.py
uv run --frozen --package wnba-oracle python wnba-oracle/scripts/export_hv_board.py \
  --corpus-root /tmp/sports-realsports-corpus --proof-latest-finalized
```

## Actions

Workflow `.github/workflows/hv-leaderboard-corpus.yml` clones the sibling
repo, runs the sport export CLI, and pushes an append-only commit. Fail-closed
without `CORPUS_REPO` / `CORPUS_REPO_TOKEN` / Real Sports auth.

## Own-model wiring (#523)

HV + matchup field map: `scripts/corpus/feature_field_map.md`.
NFL FeatureSpec matchup/prior groups and WNBA EB label corpus consume these
artifacts; wiring PRs stay under #523 / #453.

# Real Sports contest corpus (portfolio)

Durable offline contest history for every sport (WNBA, NFL, NBA, NHL). Models
operate from (1) the day's slate + boost pool and (2) this corpus — never a
daily full-history re-scrape of Real Sports.

Tracked issue: [#526](https://github.com/cheeksmagunda/sports/issues/526)
(refs [#453](https://github.com/cheeksmagunda/sports/issues/453)).

## Sequencing lock (operator)

1. **Complete representation first** — every Real Sports variable from every
   slate possible (kinds below).
2. **Only then** — Ollama on the Codespace as an internal smart **training**
   helper (`ollama generate` / HV self-learn ticks).
3. Until root `coverage_manifest.json` shows
   `historical_capture_complete: true` for every required family:
   **Ollama training is FORBIDDEN** (raises `OllamaForbiddenError`), unless
   the operator sets `SPORTS_OLLAMA_UNLOCK=1` for Codespace helper override.
4. **Binary install + `ollama serve` + watcher arming scaffold** are allowed
   now behind that gate (issue [#574](https://github.com/cheeksmagunda/sports/issues/574)).
   See `scripts/ollama_hv_watcher/README.md`.

## Separate GitHub repository

| Item | Value |
|---|---|
| Repo | [`cheeksmagunda/sports-realsports-corpus`](https://github.com/cheeksmagunda/sports-realsports-corpus) (private) |
| Purpose | Append-only RS history payloads + `coverage_manifest.json` |
| Monorepo checkout | Does **not** submodule or clone this repo by default |

Auth: portfolio `REALSPORTS_STORAGE_STATE_B64GZ` only. Never mint a session.
Never commit storage state into the corpus repo.

## Layout (corpus repo root)

Kind-first (matches the live corpus repo scaffold):

```
players/
team_weights/
lineups/
slate_rosters/
averages/
combined_stats/
recorded_states/
total_value_leaderboards/
matchups/
draft_stats_all_sections/
feeds/
coverage_manifest.json
```

Typical path: `{kind}/{sport}/{year}/slate_{YYYY-MM-DD}/…`. Sport keys:
`wnba`, `nfl`, `nba`, `nhl`.

Existing monorepo Postgres / `backups`-branch exports are complementary, not
replaced (WNBA `slate_labels`, NFL Corpus C/G, NHL corpus scaffolds, NBA TBD).

## Operator secret: `CORPUS_REPO_TOKEN`

The append workflow
(`.github/workflows/realsports-corpus-append.yml`) pushes commits into the
sibling corpus repository. **`GITHUB_TOKEN` cannot write to a sibling repo.**

Provision (operator only; agents must not mint):

1. Create a classic PAT or fine-grained token with `contents: write` on
   `cheeksmagunda/sports-realsports-corpus`.
2. Add it as repository secret `CORPUS_REPO_TOKEN` on `cheeksmagunda/sports`.

If the corpus repository is missing on a fresh fork, create it with:

```sh
env -u GH_TOKEN -u GITHUB_TOKEN gh repo create cheeksmagunda/sports-realsports-corpus \
  --private --description "Full Real Sports history corpus for Sports Oracle"
```

Then seed README + empty `coverage_manifest.json` + kind directories (see the
corpus repo root README).

## Helpers

| Module | Role |
|---|---|
| `layout.py` | Required kind constants + path helpers |
| `coverage_manifest.py` | Manifest schema + Ollama forbid gate |
| `stage_append.py` | Actions-side copy + soft-merge coverage |
| `export_stubs.py` | Offline export from WNBA DB / NFL Corpus G+C |
| `generate_coverage_status.py` | Offline fixture dry-run + Ollama unlock handoff |

Offline status (no Ollama, no Real Sports)::

```sh
PYTHONPATH=scripts python scripts/realsports_corpus/generate_coverage_status.py \
  --write-fixture-snapshot
```

Snapshot lands under `fixtures/offline_status/` for PR handoff.

## COMPLETE vs MISSING (after #532 / #533 / #534 / #537 / #538 / #539)

| Surface | COMPLETE | MISSING (blocks Ollama) |
|---|---|---|
| HV boards | WNBA export path + NFL Corpus C HV export; NBA/NHL fail-closed stubs | Sibling publish (`CORPUS_REPO_TOKEN`); NBA ingest; NHL RS contest HV durable |
| Corpus G | NFL volume hydrate (~3k files on worker) | Kind-first sibling soft-merge; WNBA/NBA/NHL RS boxes |
| Corpus C | NFL offline HV + draftStats + matchups export | Volume → sibling append |
| Matchups | Per-sport `#537` append scripts | Full-history sibling fill |
| draftStats | WNBA all-sections dump + Postgres export; NFL Corpus C | Sibling publish; NBA/NHL durable |

Live sibling `coverage_manifest.json` still has `historical_capture_complete: false`
(all families `unknown` except one synthetic NFL HV proof slate). **Ollama remains
FORBIDDEN.**

## Export stubs (existing durable stores)

| Family | WNBA durable source | NFL durable source |
|---|---|---|
| `players/` | `slate_labels` distinct players | Corpus G `players.json` |
| `team_weights/` | stub (no table yet) | Corpus C `draftinfo` multipliers (partial) |
| `lineups/` | `contest_leaderboards.lineup` | Corpus C `entries.json` |
| `slate_rosters/` | `job1_enrichment` pool | Corpus C `draftinfo` player pool |
| `averages/` | stub | stub |
| `combined_stats/` | `slate_labels` non-HV sections | Corpus G `stats.json` box scores |
| `recorded_states/` | stub | Corpus G `feed.json` (clocks/plays proxy) |
| `total_value_leaderboards/` | `slate_labels` `highestBoostedValuePlayers` | Corpus C `draftStats` HV section |
| `matchups/` | `wnba_game_logs` | Corpus G `feed.json` game matchup |
| `draft_stats_all_sections/` | `slate_labels` all sections (via combined) | Corpus C full `draftStats` |
| `feeds/` | stub | Corpus G `feed.json` |

Stubs write explicit `STUB.json` (or projected JSON) and mark
`coverage_manifest` status `stub` / `partial` / `present`. They never call
Real Sports and never mint credentials. Fixture proof inputs live under
`fixtures/durable_stores/`.

## How the monorepo references it (no Mac terabyte clone)

| Consumer | Mechanism |
|---|---|
| GitHub Actions | Sparse checkout / `gh api` of one kind/sport/year + manifest |
| Codespace research | Sparse clone of one sport/year, or a Release pack |
| Railway workers | Volume hydrate from a pinned Release tarball; never full-git clone |
| Mac laptop | Manifest + optional single-year pack only |

Env knobs (process environment only):

- `REALSPORTS_CORPUS_REPO` (default `cheeksmagunda/sports-realsports-corpus`)
- `REALSPORTS_CORPUS_REF` (default `main`)
- `REALSPORTS_CORPUS_ROOT` (local hydrate path when present)

## Nightly / backfill (append-only, idempotent)

1. Discover finalized contest / slate keys for the catch-up window.
2. Write kind payloads under the layout above; redact before commit.
3. Soft-merge `coverage_manifest.json` (union of keys; never delete).
4. Commit only new/changed paths via
   `realsports-corpus-append.yml` + `CORPUS_REPO_TOKEN`.
5. Scheduled runs append recent finalized slates only. Multi-year live
   backfill requires explicit `workflow_dispatch` confirmation and a bounded
   range — never an unbounded walk.

Default workflow mode is **fixture proof**
(`scripts/realsports_corpus/fixtures/proof_slate/`). Live Real Sports calls
stay operator-gated.

# Corpus field → own-model FeatureSpec map (#526 → #523 / #583)

Total Value leaderboard is the label. Corpus artifacts feed the existing own
learner surfaces (NFL ridge / valuelaw / context; WNBA EB + serving features).
Do not invent a parallel model stack.

Portfolio freeze inventory (available | wired | serving) lives in
`oracle_core.feature_matrix` (`FEATURE_MATRIX` / `unused_gold()`).

## HV board (`hv_board.json`)

| Corpus field | Own-model use | Surface | Notes |
|--------------|---------------|---------|-------|
| `players[].value` | train label | high_tv / valuelaw / EB real_score | Total Value Daily Leaderboard |
| `players[].real_score` | label / prior | WNBA `slate_labels.real_score`; NFL Real value | Same as value when boosts folded |
| `players[].card_boost` | slate_meta prior | boost prior; **not** `card_boost_post_settlement` | live_ok only when pre-lock |
| `players[].team` | matchup join | `opponent_team` / `home_away` via schedule | Never fuzzy `sameAs` |
| `players[].drafts` | ownership prior | measured ownership when pre-lock | Post-lock is train-only |
| `players[].player_id` | identity | platform id | Sport-owned identity map |

## Matchups / game_stats (`matchups.json`, `game_stats.json`)

| Corpus field | FeatureSpec / group | Own-model status (#523) |
|--------------|---------------------|-------------------------|
| home/away + opponent | `home_away`, `opponent_team`, `is_divisional` | `context_emitted` / `identity_encode` |
| box `value` | Real value priors / valuelaw target | ridge_core / label |
| opponent defense aggregates | `opp_def_value_allowed_prior` | `context_emitted` (Corpus G) |
| pace proxies | `team_pace_prior`, `opponent_pace_prior` | `context_emitted` |
| kickoff / slate meta | `kickoff_slot_*` | `context_required` |

## Wiring PRs

- Issue **#523**: own neural/learner feature map (ridge / valuelaw / EB).
- Issue **#453**: history / TDV / max-value product path.
- Issue **#526**: this corpus (append-only history; no daily full re-scrape).

Implementation lives in sport packages (`nfl_oracle.features`,
`nfl_oracle.valuelaw`, `wnba_oracle.train.eb_baseline`); this map is the
contract comment surface only.

# Corpus C HV export fixtures (#526)

Synthetic NFL Corpus C contest dirs for offline export tests.

- Contest shape mirrors `drive/nfl_fixtures/contest_2124_*.json` route files,
  but with NFL sport + non-empty `draftStats` (drive contest 2124 is soccer /
  empty stats).
- Matchup game id `19457` matches `drive/nfl_fixtures/home_next.json` /
  `game_19457_*.json` for Corpus G link proofs.
- `9001`: has `highestBoostedValuePlayers` + sibling section.
- `9002`: missing HV section (reconstruction path).

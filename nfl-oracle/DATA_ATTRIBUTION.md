# Data attribution (nfl-oracle)

## nflverse / nfldata schedules

Offline schedule CSVs under `data/schedule/`, `data/cache/`, and
`tests/fixtures/schedule/` are derived from public **nflverse/nfldata**
`games.csv` (Lee Sharpe / nflverse), licensed **CC BY 4.0**.

- Source URL: https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv
- Upstream project: https://github.com/nflverse/nfldata
- License: https://creativecommons.org/licenses/by/4.0/

Underlying NFL marks, scores, and game data remain property of their
respective owners. This project uses the public schedule feed for
**research / observation only** (no contest entry).

Refresh with:

```bash
uv run --package nfl-oracle python scripts/cache_nflverse_schedules.py
```

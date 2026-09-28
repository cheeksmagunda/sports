# NBA connector map

NBA is not on the T-40 five-card path. There is no feature matrix, no
ridge or other serving model, no picker, no optimizer, no freeze, and no
contest frontend.

What exists:

- Health-only API (`GET /health`) on `sports-oracle` / `nba-staging`. Service state is in `STATUS.md`.
- Public `data.nba.com` history load into staging Postgres. Coverage is partial. It is not a Highest value label corpus.
- `scripts/export_hv_board.py` exits 78 (fail closed). No Real Sports contest ingest.

Nothing in this folder must be switched on to freeze an NBA five, because
that freeze does not exist. Do not point NFL `NFL_*` knobs or the Ollama
helper at NBA until a later issue adds the chain.

"""Export the full ``wnba_game_logs`` corpus for offline tournament/benchmark use.

``wnba_game_logs`` is the nba_api-sourced per-player-game box score corpus
that ``features.corpus.build_gamelog_corpus`` (training) and
``features.serving_features.build_head_feature_lookup`` (live serve, job1)
both build causal rolling features from -- the ONLY input that lets the
D63 trained heads (``art.heads``) actually run at predict time. See
wnba-oracle/AGENTS.md: do not join the gamelog and label corpora without an
explicit identity map -- this export stays purely within the gamelog corpus,
mirroring export_game_identity.py's per-player identity export from the
label corpus.

Used by scripts/build_model_research_benchmark.py's offline
``--game-logs-csv`` path so the tournament/benchmark harness can populate
``head_features`` in its enrichment dict exactly like job1.py does at serve
time, instead of leaving the heads tier permanently empty (#53). Every
consumer applies its own as-of-date causality filter on top of this full
export (``build_rolling_features(as_of_date=...)``,
``compute_team_pace_map``/``compute_opp_dvp_map`` called on pre-filtered
rows) -- this script exports the raw table, unfiltered, same as
``db.reads.read_game_logs`` returns it live.

Pure-python (no pg_dump binary), reusing backup_corpus.py's connection
conventions. Reads the connection from DATABASE_PUBLIC_URL (read-only,
sslmode=verify-ca) or, as a fallback, DATABASE_URL. TLS root cert is taken
from the URL's sslrootcert param or the PGSSLROOTCERT env var (libpq).
"""

from __future__ import annotations

import os
import pathlib
import sys

import pandas as pd
from corpus_backup_common import atomic_write_bytes, portable_postgres_url, require_verified_tls
from sqlalchemy import create_engine, text

QUERY = (
    "select game_date, player_id, player_name, first_initial, last_name, "
    "team, opponent, home_away, game_id, min, season, "
    "pts, reb, oreb, dreb, ast, stl, blk, tov, "
    "fgm, fga, fg3m, ftm, fta "
    "from wnba_game_logs "
    "order by game_date, player_id"
)
OUT = pathlib.Path(os.environ.get("GAME_LOGS_OUTPUT_DIR", "."))


def export_game_logs(engine, output_dir: pathlib.Path) -> int:
    """Export the gamelog corpus from one read-only repeatable-read snapshot."""

    output_dir.mkdir(parents=True, exist_ok=True)
    connection = engine.connect().execution_options(isolation_level="REPEATABLE READ")
    try:
        with connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            frame = pd.read_sql(text(QUERY), connection)
    finally:
        connection.close()
    path = output_dir / "game_logs.csv"
    atomic_write_bytes(path, frame.to_csv(index=False).encode("utf-8"))
    n_players = frame["player_id"].nunique() if "player_id" in frame.columns else 0
    n_dates = frame["game_date"].nunique() if "game_date" in frame.columns else 0
    print(
        f"exported game logs: {len(frame)} player-game rows over {n_dates} dates, "
        f"{n_players} players -> {path}"
    )
    return len(frame)


def main() -> int:
    url = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: set DATABASE_PUBLIC_URL or DATABASE_URL", file=sys.stderr)
        return 1
    try:
        require_verified_tls(url)
    except RuntimeError as exc:
        print(f"ERROR: game logs export configuration rejected: {exc}", file=sys.stderr)
        return 1
    engine = create_engine(
        portable_postgres_url(url),
        connect_args={"options": "-c default_transaction_read_only=on"},
    )
    try:
        rows = export_game_logs(engine, OUT)
    except Exception as exc:
        print(f"ERROR: game logs export failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    if rows == 0:
        print("ERROR: game logs export returned zero rows", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

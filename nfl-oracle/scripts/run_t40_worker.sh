#!/usr/bin/env bash
# Launches the NFL recommendation worker against the real Railway Postgres,
# via a local SSH tunnel, for the live 2026-09-09 T-40 freeze (SEA at NE).
#
# The worker self-gates on `due <= now < cutoff` (T-40 through kickoff), so
# starting it any time before 18:40 America/Chicago is safe: it will log
# "waiting_for_t40" on every poll until the window opens, then attempt the
# real prepare/publish exactly once inside it.
#
# Run this yourself (it performs a live production write path, which this
# session will not do unattended):
#   bash nfl-oracle/scripts/run_t40_worker.sh
#
# Stop it any time with: kill $(cat /tmp/nfl_t40_worker.pid)
# Tail progress with:    tail -f /tmp/nfl_t40_worker.log

set -euo pipefail
cd "$(dirname "$0")/.."

SECRET_FILE=".secrets/local_tunnel_db_url"
TUNNEL_PORT=15433
LOG_FILE="/tmp/nfl_t40_worker.log"
PID_FILE="/tmp/nfl_t40_worker.pid"

if ! nc -z 127.0.0.1 "$TUNNEL_PORT" 2>/dev/null; then
  echo "Postgres tunnel not up on :$TUNNEL_PORT -- starting it."
  railway connect Postgres --ssh --tunnel-only --port "$TUNNEL_PORT" \
    > /tmp/nfl_pg_tunnel.log 2>&1 &
  disown
  sleep 4
fi

if [ ! -f "$SECRET_FILE" ]; then
  echo "Missing $SECRET_FILE -- writing tunnel URL." >&2
  exit 1
fi

echo "Starting worker (logs: $LOG_FILE) ..."
NFL_DATABASE_URL="$(cat "$SECRET_FILE")" NFL_RECOMMENDATIONS_ENABLED=1 \
  caffeinate -is uv run --package nfl-oracle nfl-pipeline worker \
  --day 2026-09-09 --poll-seconds 30 \
  > "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
disown

echo "Worker running as PID $(cat "$PID_FILE")."
echo "It will report waiting_for_t40 every ~30s until 2026-09-09 18:40 America/Chicago,"
echo "then attempt the real freeze once. Watch it with: tail -f $LOG_FILE"

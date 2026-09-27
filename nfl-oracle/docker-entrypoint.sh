#!/bin/sh
# NFL production entrypoint: Railway volumes mount as root. The image runs as
# oracle (uid 10001). Ensure the data root exists and is owned by oracle before
# dropping privileges so the worker can write under /app/nfl-oracle/data.
set -eu

DATA_ROOT="${NFL_DATA_ROOT:-/app/nfl-oracle/data}"

if [ "$(id -u)" = "0" ]; then
  mkdir -p "$DATA_ROOT"
  chown -R oracle:oracle "$DATA_ROOT" || true
  if command -v runuser >/dev/null 2>&1; then
    exec runuser -u oracle -- "$@"
  fi
  if command -v setpriv >/dev/null 2>&1; then
    exec setpriv --reuid=oracle --regid=oracle --clear-groups -- "$@"
  fi
  echo "nfl-oracle entrypoint: need runuser or setpriv to drop to oracle" >&2
  exit 1
fi

exec "$@"

#!/usr/bin/env bash
# Push Codespace advice.json onto NFL/WNBA freeze workers (no redeploy).
# Refs #574. Does not flip NFL_OLLAMA_INFLUENCE / WNBA_OLLAMA_INFLUENCE.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DAY="${1:-$(TZ=America/New_York date +%F)}"
SPORT="${2:-nfl}"
LOCAL="${ROOT}/data/ollama_hv/${SPORT}/${DAY}/advice.json"
if [[ ! -f "${LOCAL}" ]]; then
  echo "missing ${LOCAL}; run: PYTHONPATH=scripts python -m ollama_hv_watcher --advice --board <board> --execute" >&2
  exit 1
fi
case "${SPORT}" in
  nfl)
    SERVICE="nfl-oracle-worker"
    REMOTE_DIR="/app/nfl-oracle/data/ollama_hv/${SPORT}/${DAY}"
    ENV_PREFIX="NFL"
    ;;
  wnba)
    SERVICE="wnba-cron-job2"
    REMOTE_DIR="/app/data/ollama_hv/${SPORT}/${DAY}"
    ENV_PREFIX="WNBA"
    ;;
  *)
    echo "sport must be nfl or wnba, got ${SPORT}" >&2
    exit 2
    ;;
esac
echo "pushing ${LOCAL} -> ${SERVICE}:${REMOTE_DIR}/advice.json"
b64="$(base64 <"${LOCAL}" | tr -d '\n')"
"${ROOT}/scripts/codespace-railway-env" -- railway ssh -s "${SERVICE}" -- \
  bash -lc "mkdir -p '${REMOTE_DIR}' && printf '%s' '${b64}' | base64 -d > '${REMOTE_DIR}/advice.json' && ls -la '${REMOTE_DIR}/advice.json'"
echo "Set ${ENV_PREFIX}_OLLAMA_ADVICE_PATH=${REMOTE_DIR}/advice.json and ${ENV_PREFIX}_OLLAMA_INFLUENCE=1 on ${SERVICE} in the same Railway change as the influence merge (before the 2h freeze buffer)."

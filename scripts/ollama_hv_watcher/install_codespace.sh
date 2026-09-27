#!/usr/bin/env bash
# Codespace-safe Ollama binary install + small model pull + serve health (#573).
# Training remains gated by coverage_manifest / SPORTS_OLLAMA_UNLOCK.
set -euo pipefail

MODEL="${OLLAMA_MODEL:-llama3.2:3b}"
DATA_ROOT="${OLLAMA_DATA_ROOT:-${HOME}/.local/share/sports-ollama}"
REPO_DATA_ROOT="${SPORTS_OLLAMA_DATA_ROOT:-data/ollama_hv}"

mkdir -p "${DATA_ROOT}" "${REPO_DATA_ROOT}" "${HOME}/ollama-logs"

if ! command -v ollama >/dev/null 2>&1; then
  echo "installing ollama binary…"
  curl -fsSL https://ollama.com/install.sh | sh
fi

ollama --version

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  nohup ollama serve >"${HOME}/ollama-logs/serve.log" 2>&1 &
  echo $! >"${REPO_DATA_ROOT}/ollama_serve.pid"
  for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

curl -fsS http://127.0.0.1:11434/api/tags >/dev/null
ollama pull "${MODEL}"
ollama list
echo "ollama_install_ok model=${MODEL}"

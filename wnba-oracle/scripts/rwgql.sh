#!/usr/bin/env bash
# Railway GraphQL compatibility entry point. Auth is read from the environment.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
exec python3 "$script_dir/rwgql.py" "$@"

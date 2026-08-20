#!/usr/bin/env bash
# Compatibility entry point for the portable value-free authentication check.

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
portfolio_root="$(cd "$project_root/.." && pwd -P)"

exec "$portfolio_root/scripts/auth-check" wnba-oracle --live

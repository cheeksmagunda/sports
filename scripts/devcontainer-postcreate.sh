#!/usr/bin/env bash
# scripts/devcontainer-postcreate.sh
#
# Runs once when the devcontainer is created (postCreateCommand). Provisions
# the locked workspace, then the per-user Chromium binary Playwright needs
# for Real Sports session capture and verification (issue #242): the system
# libraries it depends on are baked into .devcontainer/Dockerfile, so this
# step is just the browser download, keeping the Real Sports auth path as
# available in a fresh Codespace as the GitHub and Railway CLIs already are.
set -eu

cd /workspaces/sports

make setup
uv run --frozen --package wnba-oracle playwright install chromium

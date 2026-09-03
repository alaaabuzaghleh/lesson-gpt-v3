#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
args=()
[[ -f .env ]] && args+=(--env-file .env)
docker compose -f docker-compose.dev.yml "${args[@]}" down "$@"

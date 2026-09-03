#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "Missing .env — run: cp .env.example .env" >&2
  exit 1
fi

if ! docker network inspect lessons-gpt >/dev/null 2>&1; then
  echo "Infra not running — run first: cd ../infra && ./up.sh" >&2
  exit 1
fi

docker compose -f docker-compose.dev.yml --env-file .env up -d --build "$@"

PORT="${REMOTE_API_HOST_PORT:-8081}"
if [[ -f .env ]]; then
  val="$(grep -E '^REMOTE_API_HOST_PORT=' .env | tail -1 | cut -d= -f2- | tr -d ' "'\''')"
  [[ -n "$val" ]] && PORT="$val"
fi

echo ""
echo "remoteLessonsGPT: http://localhost:${PORT}/docs"
echo ""
echo "Host apps (separate terminals):"
echo "  extractor: cd ../extractor-lessons-gpt && source .venv/bin/activate && python run_api.py"
echo "  admin:     cd ../admin-lessons-gpt && npm run dev"

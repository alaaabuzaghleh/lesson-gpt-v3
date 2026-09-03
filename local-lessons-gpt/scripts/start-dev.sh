#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Starting shared infrastructure (Postgres + OpenSearch)..."
docker compose -f "$ROOT/local-lessons-gpt/docker-compose.yml" up -d

echo ""
echo "Start each service in a separate terminal:"
echo ""
echo "  # 1. remoteLessonsGPT (production API)"
echo "  cd $ROOT/remote-lessons-gpt && source .venv/bin/activate && API_PORT=8081 python run_api.py"
echo ""
echo "  # 2. extractorLessonsGPT (local extraction)"
echo "  cd $ROOT/extractor-lessons-gpt && source .venv/bin/activate && python run_api.py"
echo ""
echo "  # 3. adminLessonsGPT (UI)"
echo "  cd $ROOT/admin-lessons-gpt && npm run dev"
echo ""
echo "Open http://localhost:5173/login"

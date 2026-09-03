#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
docker compose up -d "$@"
echo ""
echo "Infrastructure running:"
echo "  Postgres:              localhost:5432  (postgres / postgres, db: lessons_gpt)"
echo "  OpenSearch:            http://localhost:9200"
echo "  OpenSearch Dashboards: http://localhost:5601"
echo "  pgAdmin:               http://localhost:5050  (admin@lessonsgpt.local / admin)"
echo ""
echo "Next: cd ../remote-lessons-gpt && ./up.sh"

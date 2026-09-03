# Infrastructure

PostgreSQL and OpenSearch run here in Docker. **Only `remote-lessons-gpt`** should connect to them.

| Service | URL (host) |
|---------|------------|
| PostgreSQL | `localhost:5432` — user `postgres`, password `postgres`, db `lessons_gpt` |
| OpenSearch | `http://localhost:9200` |
| OpenSearch Dashboards | `http://localhost:5601` |
| pgAdmin | `http://localhost:5050` — `admin@lessonsgpt.local` / `admin` |

Start/stop via the local orchestrator:

```bash
cd ../local-lessons-gpt
./scripts/local up infra
./scripts/local down infra
```

The remote API (`local-lessons-gpt/docker-compose.apps.yml`) joins the `lessons-gpt` network and uses hostnames `postgres` and `opensearch`.

Local extractors publish extracted pages through the remote HTTP ingest API (`REMOTE_API_URL`), never directly to Postgres or OpenSearch.

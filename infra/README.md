# Infrastructure

PostgreSQL and OpenSearch in Docker. **Only `remote-lessons-gpt`** connects to them.

| Service | URL |
|---------|-----|
| PostgreSQL | `localhost:5432` — `postgres` / `postgres`, db `lessons_gpt` |
| OpenSearch | http://localhost:9200 |
| OpenSearch Dashboards | http://localhost:5601 |
| pgAdmin | http://localhost:5050 — `admin@lessonsgpt.local` / `admin` |

## Start / stop

```bash
cd infra
./up.sh      # or: docker compose up -d
./down.sh    # or: docker compose down
```

Then start the remote API:

```bash
cd ../remote-lessons-gpt
cp .env.example .env
./up.sh
```

Extractors publish pages through the remote HTTP ingest API — never directly to Postgres or OpenSearch.

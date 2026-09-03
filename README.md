# Lessons GPT

Textbook ingestion platform for Arabic and mixed-language school books.

## Monorepo packages

| Product name | Folder | Port | Role |
|--------------|--------|------|------|
| **remoteLessonsGPT** | [remote-lessons-gpt/](remote-lessons-gpt/) | 8081 | Production API: auth, catalog, ingest, PostgreSQL, OpenSearch |
| **extractorLessonsGPT** | [extractor-lessons-gpt/](extractor-lessons-gpt/) | 8080 | Local PDF extraction + per-page remote sync |
| **adminLessonsGPT** | [admin-lessons-gpt/](admin-lessons-gpt/) | 5173 | Arabic RTL admin dashboard |
| **localLessonsGPT** | [local-lessons-gpt/](local-lessons-gpt/) | — | Dev orchestration (Docker CLI) |

### Naming convention

- **Docs / product:** camelCase — `remoteLessonsGPT`
- **Folders:** kebab-case — `remote-lessons-gpt`
- **Python packages:** snake_case — `remote_lessons_gpt`

## Quick start (CLI on your machine)

```bash
cd local-lessons-gpt
cp .env.example .env
chmod +x scripts/local scripts/start-dev.sh
./scripts/start-dev.sh
```

This starts:

1. **External Docker stack** — Postgres, OpenSearch, Dashboards, pgAdmin
2. **Internal Docker stack** — remoteLessonsGPT API
3. Prints commands to start **extractor** and **admin** on your host

Then follow the printed host commands, or run:

```bash
./scripts/local host
```

### Default login

http://localhost:5173/login — `superadmin@lessonsgpt.com` / `SuperAdmin123!`

## Dev URLs

| Service | URL |
|---------|-----|
| Admin UI | http://localhost:5173 |
| extractorLessonsGPT | http://localhost:8080/docs |
| remoteLessonsGPT | http://localhost:8081/docs |
| OpenSearch | http://localhost:9200 |
| OpenSearch Dashboards | http://localhost:5601 |
| pgAdmin (PostgreSQL) | http://localhost:5050 |
| Postgres | `localhost:5432` / `lessons_gpt` |

## Architecture

```
adminLessonsGPT (:5173)  ──► extractorLessonsGPT (:8080)  ──► remoteLessonsGPT (:8081)
                                                                    │
                                                    Postgres + OpenSearch (Docker)
```

## Package READMEs

- [local-lessons-gpt/README.md](local-lessons-gpt/README.md) — Docker CLI and full dev stack
- [remote-lessons-gpt/README.md](remote-lessons-gpt/README.md) — production server + ingest API
- [extractor-lessons-gpt/README.md](extractor-lessons-gpt/README.md) — local extraction
- [admin-lessons-gpt/README.md](admin-lessons-gpt/README.md) — admin UI

## Key environment variables

| Variable | Package | Purpose |
|----------|---------|---------|
| `REMOTE_API_URL` | extractor | `http://localhost:8081` |
| `DATABASE_URL` | remote, extractor | PostgreSQL |
| `OPENSEARCH_URL` | remote, extractor | Search cluster |

See [local-lessons-gpt/.env.example](local-lessons-gpt/.env.example) for Docker orchestration variables.

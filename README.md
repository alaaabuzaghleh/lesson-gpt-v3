# Lessons GPT

Textbook ingestion platform for Arabic and mixed-language school books.

## Monorepo packages

| Product name | Folder | Port | Role |
|--------------|--------|------|------|
| **remoteLessonsGPT** | [remote-lessons-gpt/](remote-lessons-gpt/) | 8081 | Production API: auth, catalog, ingest, PostgreSQL, OpenSearch |
| **extractorLessonsGPT** | [extractor-lessons-gpt/](extractor-lessons-gpt/) | 8080 | Local PDF extraction + per-page remote sync |
| **adminLessonsGPT** | [admin-lessons-gpt/](admin-lessons-gpt/) | 5173 | Arabic RTL admin dashboard |
| **localLessonsGPT** | [local-lessons-gpt/](local-lessons-gpt/) | — | Dev orchestration (Docker, scripts) |

### Naming convention

- **Docs / product:** camelCase — `remoteLessonsGPT`
- **Folders:** kebab-case — `remote-lessons-gpt`
- **Python packages:** snake_case — `remote_lessons_gpt`

## Architecture

```
adminLessonsGPT (:5173)
    → extractorLessonsGPT (:8080)     PDF upload + extraction
    → remoteLessonsGPT (:8081)        auth, catalog, search, ingest

extractorLessonsGPT
    → after each page → POST /api/v1/ingest/jobs/{id}/pages
    → remoteLessonsGPT → PostgreSQL + OpenSearch (student app)
```

## Quick start

Use **[localLessonsGPT](local-lessons-gpt/README.md)** for the fastest path:

```bash
cd local-lessons-gpt
docker compose up -d
./scripts/start-dev.sh
```

Then start remote (8081), extractor (8080), and admin (5173) as printed.

### Prerequisites

- Python 3.11–3.13, Node.js 20+, Docker Desktop
- Ollama with `qwen2.5vl:7b` (local extraction) or ChatGPT.app Codex

### Default login

Remote admin credentials from `remote-lessons-gpt/.env`:

- `superadmin@lessonsgpt.com` / `SuperAdmin123!`

## Typical workflow

1. Log in to adminLessonsGPT with **remote** credentials
2. Pick a subject from the remote catalog
3. Upload a PDF (stored locally, registered on remote)
4. Start extraction with **remote sync** enabled
5. Each page appears in remote OpenSearch for the AI teacher app

## Package READMEs

- [local-lessons-gpt/README.md](local-lessons-gpt/README.md) — run the full dev stack
- [remote-lessons-gpt/README.md](remote-lessons-gpt/README.md) — production server + ingest API
- [extractor-lessons-gpt/README.md](extractor-lessons-gpt/README.md) — local extraction
- [admin-lessons-gpt/README.md](admin-lessons-gpt/README.md) — admin UI

## Ports

| Service | URL |
|---------|-----|
| Admin UI | http://localhost:5173 |
| extractorLessonsGPT | http://localhost:8080/docs |
| remoteLessonsGPT | http://localhost:8081/docs |
| OpenSearch | http://localhost:9200 |
| Postgres | `localhost:5432` / `lessons_gpt` |

## Key environment variables

| Variable | Package | Purpose |
|----------|---------|---------|
| `REMOTE_API_URL` | extractor | Points to remoteLessonsGPT |
| `DATABASE_URL` | remote, extractor | PostgreSQL |
| `OPENSEARCH_URL` | remote, extractor | Search cluster |
| `API_PORT` | remote, extractor | HTTP port (8081 / 8080) |

See each package's `.env.example` for the full list.

# Lessons GPT

Textbook ingestion platform for Arabic and mixed-language school books.

Admins upload PDFs on their machine, extract pages with **Ollama** or **Codex**, and publish structured content to students through a **remote API** backed by PostgreSQL and OpenSearch.

Only **remote-lessons-gpt** (Docker) talks to Postgres and OpenSearch. The extractor and admin UI use HTTP APIs only.

---

## Architecture

| Component | Postgres / OpenSearch | Role |
|-----------|----------------------|------|
| [infra/](infra/) (Docker) | Hosts both | Database layer |
| [remote-lessons-gpt/](remote-lessons-gpt/) (Docker) | **Only direct client** | Auth, catalog, search, ingest |
| [extractor-lessons-gpt/](extractor-lessons-gpt/) (host) | No access | Local PDFs + jobs on disk; pages sent via ingest API |
| [admin-lessons-gpt/](admin-lessons-gpt/) (host) | No access | UI → remote + extractor |

```
infra/                   Postgres + OpenSearch  (Docker)
remote-lessons-gpt/      API :8081  ──────────▶ infra
extractor-lessons-gpt/   :8080  ──ingest HTTP──▶ remote
admin-lessons-gpt/       :5173  ──▶ remote (login, catalog, search)
                              └──▶ extractor (PDF upload, jobs)
```

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running)
- **Python 3.11–3.13** (not 3.14)
- **Node.js 20+**
- **[Ollama](https://ollama.com)** — `ollama pull qwen2.5vl:7b`
- **ChatGPT.app** (optional) — Codex backend

Clone the repo and work from its root (`lessons-gpt-v3/`).

---

## One-time setup

Copy env templates once:

```bash
cp remote-lessons-gpt/.env.example remote-lessons-gpt/.env
cp extractor-lessons-gpt/.env.example extractor-lessons-gpt/.env
cp admin-lessons-gpt/.env.example admin-lessons-gpt/.env
```

Edit `extractor-lessons-gpt/.env` — **required**:

```env
REMOTE_API_URL=http://localhost:8081
```

Auth credentials (`JWT_SECRET`, `SUPER_ADMIN_*`) live in `remote-lessons-gpt/.env` only.

Make Docker scripts executable (first time):

```bash
chmod +x infra/up.sh infra/down.sh remote-lessons-gpt/up.sh remote-lessons-gpt/down.sh
```

---

## Run locally

### 1. Infrastructure (Docker)

```bash
cd infra
./up.sh
```

| Service | URL |
|---------|-----|
| Postgres | `localhost:5432` — user `postgres`, password `postgres`, db `lessons_gpt` |
| OpenSearch | http://localhost:9200 |
| OpenSearch Dashboards | http://localhost:5601 |
| pgAdmin | http://localhost:5050 — `admin@lessonsgpt.local` / `admin` |

### 2. Remote API (Docker)

Requires Step 1 (`lessons-gpt` Docker network must exist).

```bash
cd remote-lessons-gpt
./up.sh
```

API docs: http://localhost:8081/docs

Uses `docker-compose.dev.yml` and joins the infra network. Port defaults to `8081` (`REMOTE_API_HOST_PORT` in `remote-lessons-gpt/.env`).

### 3. Extractor (host)

Do **not** run the extractor in Docker — it needs Ollama/Codex on your machine.

```bash
cd extractor-lessons-gpt
python3.13 -m venv .venv
source .venv/bin/activate
pip install -U pip && pip install -r requirements.txt
ollama pull qwen2.5vl:7b
python run_api.py
```

http://localhost:8080/docs

- Stores PDFs and job state under `API_DATA_ROOT` (default `./data`)
- Requires `REMOTE_API_URL` — fails at startup if unset
- For Codex: set `EXTRACTOR_BACKEND=codex` in `.env`

### 4. Admin UI (host)

Requires Steps 2 and 3 running.

```bash
cd admin-lessons-gpt
npm install
npm run dev
```

http://localhost:5173

Leave these empty in `.env` so Vite dev proxies work:

- `VITE_REMOTE_API_BASE_URL` → `/remote-api` → remote `:8081`
- `VITE_EXTRACTOR_API_BASE_URL` → `/api` → extractor `:8080`

### 5. Log in and extract

1. Open http://localhost:5173/login
2. Sign in with credentials from `remote-lessons-gpt/.env` (default `superadmin@lessonsgpt.com` / `SuperAdmin123!`)
3. Pick a catalog subject, upload a PDF, start extraction
4. Each page is ingested on the remote server → Postgres + OpenSearch

---

## Stop Docker

```bash
cd remote-lessons-gpt && ./down.sh
cd ../infra && ./down.sh
```

Stop extractor and admin with `Ctrl+C` in their terminals.

---

## URLs

| Service | URL | Where |
|---------|-----|-------|
| Admin UI | http://localhost:5173 | Host |
| Extractor API | http://localhost:8080/docs | Host |
| Remote API | http://localhost:8081/docs | Docker |
| OpenSearch | http://localhost:9200 | Docker |
| OpenSearch Dashboards | http://localhost:5601 | Docker |
| pgAdmin | http://localhost:5050 | Docker |

---

## Environment files

| File | Purpose |
|------|---------|
| `remote-lessons-gpt/.env` | Auth, `DATABASE_URL`, `OPENSEARCH_*`, `REMOTE_API_HOST_PORT`, workers |
| `extractor-lessons-gpt/.env` | `REMOTE_API_URL`, Ollama/Codex, local API settings |
| `admin-lessons-gpt/.env` | Vite proxy base URLs (leave empty in dev) |

When the remote API runs in Docker, `docker-compose.dev.yml` overrides `DATABASE_URL` and `OPENSEARCH_URL` to internal hostnames `postgres` and `opensearch`.

**Do not** put `DATABASE_URL` or `OPENSEARCH_URL` in the extractor or admin env files.

---

## Alternative: all-in-one Docker

To run Postgres, OpenSearch, and the API in a single compose file (no separate `infra/` step):

```bash
cd remote-lessons-gpt
cp .env.example .env
docker compose up -d
```

API on http://localhost:8080/docs. For day-to-day dev matching production separation, prefer `infra/` + `remote-lessons-gpt/./up.sh`.

---

## Package READMEs

- [infra/README.md](infra/README.md)
- [remote-lessons-gpt/README.md](remote-lessons-gpt/README.md)
- [extractor-lessons-gpt/README.md](extractor-lessons-gpt/README.md)
- [admin-lessons-gpt/README.md](admin-lessons-gpt/README.md)

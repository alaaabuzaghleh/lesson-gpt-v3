# Lessons GPT

Textbook ingestion platform for Arabic and mixed-language school books.

Admins upload PDFs locally, extract pages with **Ollama** or **Codex**, and publish structured content to students through a **remote API** backed by PostgreSQL and OpenSearch.

---

## Architecture

### Security boundary

| Component | PostgreSQL / OpenSearch | How data is stored |
|-----------|-------------------------|-------------------|
| **infra** (Docker) | Hosts Postgres + OpenSearch | — |
| **remoteLessonsGPT** (Docker) | **Only service with direct access** | Auth, catalog, search, ingest |
| **extractorLessonsGPT** (host) | **No direct access** | Local PDFs + job files on disk; pages sent via HTTP ingest |
| **adminLessonsGPT** (host) | **No direct access** | UI only; calls remote + extractor APIs |

The extractor and admin UI must never receive `DATABASE_URL` or `OPENSEARCH_URL`. All persistence for students goes through authenticated remote APIs.

### What runs where

| Layer | What | Where | Why |
|-------|------|-------|-----|
| **1. Infrastructure** | Postgres, OpenSearch, Dashboards, pgAdmin | **Docker** (`infra/`) | Shared DB and search (production-like) |
| **2. remoteLessonsGPT** | Auth, catalog, ingest, workers | **Docker** | Production API; sole DB/OS client |
| **3. extractor + admin** | PDF extraction + admin UI | **Your Mac** | Needs local Ollama / Codex |

```
┌─ Docker: infra/ ───────────────────────────────────────────────────────┐
│  Postgres :5432  │  OpenSearch :9200  │  Dashboards :5601  │  pgAdmin :5050 │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │  (remote API only)
┌─ Docker: local-lessons-gpt/docker-compose.apps.yml ─────────────────────┐
│  remoteLessonsGPT :8081  →  Postgres + OpenSearch                         │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │  REMOTE_API_URL=http://localhost:8081
┌─ Your Mac (host) ──────────────────┴─────────────────────────────────────┐
│  extractorLessonsGPT :8080   local PDFs, jobs, Ollama/Codex               │
│  adminLessonsGPT :5173       → :8081 auth/catalog/search                    │
│                              → :8080 PDF upload, jobs, SSE                  │
└────────────────────────────────────────────────────────────────────────────┘
```

### Admin API routing

| Admin action | Backend | Dev proxy |
|--------------|---------|-----------|
| Login, catalog, search, admin users | remoteLessonsGPT `:8081` | `/remote-api` |
| PDF upload, jobs, progress stream | extractorLessonsGPT `:8080` | `/api` |

---

## Monorepo packages

| Product | Folder | Port | Runs in |
|---------|--------|------|---------|
| **infra** | [infra/](infra/) | 5432, 9200, … | Docker |
| **localLessonsGPT** | [local-lessons-gpt/](local-lessons-gpt/) | — | Docker CLI |
| **remoteLessonsGPT** | [remote-lessons-gpt/](remote-lessons-gpt/) | 8081 | Docker |
| **extractorLessonsGPT** | [extractor-lessons-gpt/](extractor-lessons-gpt/) | 8080 | Host |
| **adminLessonsGPT** | [admin-lessons-gpt/](admin-lessons-gpt/) | 5173 | Host |

Naming: folders `kebab-case`, Python `snake_case`, docs `camelCase` (e.g. remoteLessonsGPT).

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running)
- **Python 3.11–3.13** (not 3.14)
- **Node.js 20+**
- **[Ollama](https://ollama.com)** — local VLM (`qwen2.5vl:7b`)
- **ChatGPT.app** (optional) — Codex at `/Applications/ChatGPT.app/Contents/Resources/codex`

---

## Step-by-step: run the full stack

All commands assume the repo root is `lessons-gpt-v3/`.

### Step 0 — One-time env setup

Each package has its own `.env`. Copy the examples once:

```bash
# Docker orchestration (port mapping only)
cd local-lessons-gpt
cp .env.example .env
chmod +x scripts/local scripts/start-dev.sh

# Remote API (auth, Postgres, OpenSearch, workers) — required for Docker apps
cp ../remote-lessons-gpt/.env.example ../remote-lessons-gpt/.env

# Local extractor (Ollama/Codex + REMOTE_API_URL)
cp ../extractor-lessons-gpt/.env.example ../extractor-lessons-gpt/.env

# Admin UI (dual API proxies — leave VITE_* empty for dev)
cp ../admin-lessons-gpt/.env.example ../admin-lessons-gpt/.env
```

Edit `extractor-lessons-gpt/.env` and set:

```env
REMOTE_API_URL=http://localhost:8081
```

Auth credentials (`JWT_SECRET`, `SUPER_ADMIN_*`) live in **`remote-lessons-gpt/.env`** only.

---

### Step 1 — Start infrastructure (Docker)

```bash
cd local-lessons-gpt
./scripts/local up infra
```

| Service | URL | Credentials |
|---------|-----|-------------|
| Postgres | `localhost:5432` | `postgres` / `postgres`, db `lessons_gpt` |
| OpenSearch | http://localhost:9200 | no auth (local dev) |
| OpenSearch Dashboards | http://localhost:5601 | |
| pgAdmin | http://localhost:5050 | `admin@lessonsgpt.local` / `admin` |

In pgAdmin, add server: Host `postgres`, Port `5432`, User `postgres`, Password `postgres`.

---

### Step 2 — Start remoteLessonsGPT (Docker)

Requires Step 1 and `remote-lessons-gpt/.env`.

```bash
cd local-lessons-gpt
./scripts/local up apps
```

API docs: http://localhost:8081/docs

Shortcut (Steps 1 + 2):

```bash
cd local-lessons-gpt
./scripts/start-dev.sh    # same as ./scripts/local up all
```

---

### Step 3 — Start extractorLessonsGPT (host)

**Do not run the extractor in Docker** — it needs Ollama/Codex on your machine.

```bash
cd extractor-lessons-gpt
python3.13 -m venv .venv
source .venv/bin/activate
pip install -U pip && pip install -r requirements.txt
ollama pull qwen2.5vl:7b
python run_api.py
```

Extractor API: http://localhost:8080/docs

- Stores PDFs and jobs under `API_DATA_ROOT` (default `./data`) on disk
- Publishes each extracted page to `REMOTE_API_URL` via secure ingest API
- For Codex: set `EXTRACTOR_BACKEND=codex` in `.env`

---

### Step 4 — Start adminLessonsGPT (host)

```bash
cd admin-lessons-gpt
npm install
npm run dev
```

Admin UI: http://localhost:5173

Leave `VITE_REMOTE_API_BASE_URL` and `VITE_EXTRACTOR_API_BASE_URL` empty — Vite proxies:

- `/remote-api` → remote API `:8081`
- `/api` → extractor `:8080`

---

### Step 5 — Log in and extract a book

1. Open http://localhost:5173/login
2. Sign in with credentials from `remote-lessons-gpt/.env`:
   - Email: `superadmin@lessonsgpt.com`
   - Password: `SuperAdmin123!`
3. Choose a catalog subject (remote API), upload a PDF (extractor), start extraction.
4. Each page is ingested by remoteLessonsGPT → Postgres + OpenSearch (check Dashboards / pgAdmin).

---

## Stop the stack

```bash
cd local-lessons-gpt
./scripts/local down all
```

Stop extractor and admin with `Ctrl+C` in their terminals.

---

## Quick reference — URLs

| Service | URL | Runs in |
|---------|-----|---------|
| adminLessonsGPT | http://localhost:5173 | Host |
| extractorLessonsGPT | http://localhost:8080/docs | Host |
| remoteLessonsGPT | http://localhost:8081/docs | Docker |
| OpenSearch | http://localhost:9200 | Docker |
| OpenSearch Dashboards | http://localhost:5601 | Docker |
| pgAdmin | http://localhost:5050 | Docker |

---

## localLessonsGPT CLI

From `local-lessons-gpt/`:

```bash
./scripts/local up infra      # Postgres + OpenSearch + Dashboards + pgAdmin
./scripts/local up apps       # remote API (needs infra + remote-lessons-gpt/.env)
./scripts/local up all        # infra + apps
./scripts/local status
./scripts/local host          # print extractor + admin commands
./scripts/local down all
./scripts/local help
```

---

## Environment files

| File | Purpose |
|------|---------|
| [infra/](infra/) | Docker compose for Postgres + OpenSearch (no `.env` needed) |
| [local-lessons-gpt/.env.example](local-lessons-gpt/.env.example) | Docker port mapping (`REMOTE_API_HOST_PORT`) |
| [remote-lessons-gpt/.env.example](remote-lessons-gpt/.env.example) | Auth, `DATABASE_URL`, `OPENSEARCH_*`, API workers |
| [extractor-lessons-gpt/.env.example](extractor-lessons-gpt/.env.example) | `REMOTE_API_URL`, Ollama/Codex, local API |
| [admin-lessons-gpt/.env.example](admin-lessons-gpt/.env.example) | Vite proxy bases for remote + extractor |

When running remote API in Docker, `docker-compose.apps.yml` overrides `DATABASE_URL` and `OPENSEARCH_URL` to Docker hostnames (`postgres`, `opensearch`).

---

## Key variables (local dev)

| Variable | Package | Value |
|----------|---------|-------|
| `REMOTE_API_URL` | extractor | `http://localhost:8081` |
| `JWT_SECRET`, `SUPER_ADMIN_*` | remote | in `remote-lessons-gpt/.env` |
| `DATABASE_URL` | remote (Docker) | set by compose → `postgres:5432` |
| `OPENSEARCH_URL` | remote (Docker) | set by compose → `opensearch:9200` |
| `VITE_REMOTE_API_BASE_URL` | admin | empty → `/remote-api` proxy |
| `VITE_EXTRACTOR_API_BASE_URL` | admin | empty → `/api` proxy |
| `VLM_BASE_URL` | extractor | `http://localhost:11434/v1` |
| `CODEX_BIN` | extractor | `/Applications/ChatGPT.app/Contents/Resources/codex` |

---

## Package READMEs

- [infra/README.md](infra/README.md) — Postgres + OpenSearch Docker stack
- [local-lessons-gpt/README.md](local-lessons-gpt/README.md) — Docker orchestration CLI
- [remote-lessons-gpt/README.md](remote-lessons-gpt/README.md) — production API + ingest
- [extractor-lessons-gpt/README.md](extractor-lessons-gpt/README.md) — Ollama / Codex extraction
- [admin-lessons-gpt/README.md](admin-lessons-gpt/README.md) — admin UI

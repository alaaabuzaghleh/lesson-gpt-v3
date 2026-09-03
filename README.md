# Lessons GPT

Textbook ingestion platform for Arabic and mixed-language school books.

## How the project runs

Three layers — **what runs in Docker** vs **what runs on your Mac**:

| Layer | What | Where | Why |
|-------|------|-------|-----|
| **1. Infrastructure** | Postgres, OpenSearch, OpenSearch Dashboards, pgAdmin | **Docker** | Shared DB and search index (same as production) |
| **2. remoteLessonsGPT** | Production API (auth, catalog, ingest, workers) | **Docker** | Mimics production deployment |
| **3. extractorLessonsGPT + adminLessonsGPT** | PDF extraction + admin UI | **Your machine (not Docker)** | Direct access to **Ollama** and **Codex** installed locally |

```
┌─ Docker: infrastructure (infra/docker-compose.yml) ─────────────────────┐
│  Postgres :5432  │  OpenSearch :9200  │  Dashboards :5601  │  pgAdmin :5050 │
└────────────────────────────────────┬──────────────────────────────────────┘
                                     │  (only remote API connects here)
┌─ Docker: remote API (local-lessons-gpt/docker-compose.apps.yml) ────────┐
│  remoteLessonsGPT  :8081  →  Postgres + OpenSearch via secure APIs       │
└────────────────────────────────────┬──────────────────────────────────────┘
                                     │  REMOTE_API_URL=http://localhost:8081
┌─ Your Mac (host) ──────────────────┴───────────────────────────────────┐
│  extractorLessonsGPT :8080  (Ollama/Codex, file store, remote ingest)   │
│  adminLessonsGPT :5173  → remote (auth/catalog/search) + extractor      │
└──────────────────────────────────────────────────────────────────────────┘
```

## Monorepo packages

| Product name | Folder | Port | Runs in |
|--------------|--------|------|---------|
| **localLessonsGPT** | [local-lessons-gpt/](local-lessons-gpt/) | — | Docker CLI only |
| **remoteLessonsGPT** | [remote-lessons-gpt/](remote-lessons-gpt/) | 8081 | Docker |
| **extractorLessonsGPT** | [extractor-lessons-gpt/](extractor-lessons-gpt/) | 8080 | Host |
| **adminLessonsGPT** | [admin-lessons-gpt/](admin-lessons-gpt/) | 5173 | Host |

Naming: folders `kebab-case`, Python `snake_case`, docs `camelCase` (e.g. remoteLessonsGPT).

---

## Prerequisites

Install on your Mac before starting:

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running)
- **Python 3.11–3.13** (not 3.14)
- **Node.js 20+**
- **[Ollama](https://ollama.com)** — for local VLM extraction (`qwen2.5vl:7b`)
- **ChatGPT.app** (optional) — for Codex extraction at `/Applications/ChatGPT.app/Contents/Resources/codex`

---

## Step-by-step: run the full stack

All commands assume you cloned the repo and are at its root (`lessons-gpt-v3/`).

### Step 0 — One-time CLI setup

```bash
cd local-lessons-gpt
cp .env.example .env                    # optional: REMOTE_API_HOST_PORT only
cp ../remote-lessons-gpt/.env.example ../remote-lessons-gpt/.env
chmod +x scripts/local scripts/start-dev.sh
```

---

### Step 1 — Start infrastructure (Docker)

Postgres, OpenSearch, OpenSearch Dashboards, and pgAdmin.

```bash
cd local-lessons-gpt
./scripts/local up infra
```

| Service | URL | Credentials |
|---------|-----|-------------|
| Postgres | `localhost:5432` | user `postgres`, password `postgres`, database `lessons_gpt` |
| OpenSearch | http://localhost:9200 | no auth (local dev) |
| OpenSearch Dashboards | http://localhost:5601 | |
| pgAdmin | http://localhost:5050 | `admin@lessonsgpt.local` / `admin` |

**pgAdmin:** add server → Host `postgres`, Port `5432`, Username `postgres`, Password `postgres`.

Check status:

```bash
./scripts/local status
```

---

### Step 2 — Start remoteLessonsGPT (Docker)

Production API container — uses the infra from Step 1.

```bash
cd local-lessons-gpt
./scripts/local up apps
```

API docs: http://localhost:8081/docs

This builds and runs the same API image used in production, connected to Docker Postgres and OpenSearch.

Shortcut (Steps 1 + 2 together):

```bash
cd local-lessons-gpt
./scripts/start-dev.sh
# equivalent to: ./scripts/local up all
```

---

### Step 3 — Start extractorLessonsGPT (on your Mac)

**Do not run the extractor in Docker** — it must call Ollama and Codex on your machine.

**One-time setup:**

```bash
cd extractor-lessons-gpt
cp .env.example .env
```

Edit `.env` and set at minimum:

```env
REMOTE_API_URL=http://localhost:8081
EXTRACTOR_BACKEND=local
VLM_BASE_URL=http://localhost:11434/v1
VLM_MODEL=qwen2.5vl:7b
```

The extractor stores PDFs and job state on disk only. It publishes pages to the remote API — **no direct PostgreSQL or OpenSearch access**.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -U pip && pip install -r requirements.txt
ollama pull qwen2.5vl:7b
```

**Every time (new terminal):**

```bash
cd extractor-lessons-gpt
source .venv/bin/activate
python run_api.py
```

Extractor API: http://localhost:8080/docs

For **Codex** instead of Ollama, set `EXTRACTOR_BACKEND=codex` in `.env` (ChatGPT.app must be installed).

---

### Step 4 — Start adminLessonsGPT (on your Mac)

**Do not run the admin UI in Docker** — it talks to the remote API (auth, catalog, search) and the local extractor (PDFs, jobs).

**One-time setup:**

```bash
cd admin-lessons-gpt
npm install
cp .env.example .env
```

**Every time (new terminal):**

```bash
cd admin-lessons-gpt
npm run dev
```

Admin UI: http://localhost:5173

Leave `VITE_REMOTE_API_BASE_URL` and `VITE_EXTRACTOR_API_BASE_URL` empty so Vite proxies `/remote-api` → `:8081` and `/api` → `:8080`.

---

### Step 5 — Log in and extract a book

1. Open http://localhost:5173/login  
2. Sign in with **remote** admin credentials (from Docker remote API seed):  
   - Email: `superadmin@lessonsgpt.com`  
   - Password: `SuperAdmin123!`  
3. Pick a catalog subject, upload a PDF, start extraction with **remote sync** enabled.  
4. Each page is published to remoteLessonsGPT → Postgres + OpenSearch (visible in Dashboards / pgAdmin).

---

## Stop the stack

```bash
cd local-lessons-gpt
./scripts/local down all      # stop remote API + infrastructure
```

Stop extractor and admin with `Ctrl+C` in their terminals.

---

## Quick reference — all URLs

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
./scripts/local up infra      # Step 1 only
./scripts/local up apps       # Step 2 only (requires infra)
./scripts/local up all        # Steps 1 + 2
./scripts/local status
./scripts/local host          # print Step 3 + 4 commands
./scripts/local down all
./scripts/local help
```

---

## Package READMEs

- [local-lessons-gpt/README.md](local-lessons-gpt/README.md) — Docker compose details
- [remote-lessons-gpt/README.md](remote-lessons-gpt/README.md) — production API + ingest
- [extractor-lessons-gpt/README.md](extractor-lessons-gpt/README.md) — Ollama / Codex extraction
- [admin-lessons-gpt/README.md](admin-lessons-gpt/README.md) — admin UI

---

## Key environment variables

| Variable | Used by | Value (local dev) |
|----------|---------|-------------------|
| `REMOTE_API_URL` | extractor (host) | `http://localhost:8081` |
| `DATABASE_URL` | remote API (Docker only) | `postgresql://postgres:postgres@postgres:5432/lessons_gpt` |
| `OPENSEARCH_URL` | remote API (Docker only) | `http://opensearch:9200` |
| `VITE_REMOTE_API_BASE_URL` | admin (host) | empty (use Vite proxy `/remote-api`) |
| `VITE_EXTRACTOR_API_BASE_URL` | admin (host) | empty (use Vite proxy `/api`) |
| `VLM_BASE_URL` | extractor (host) | `http://localhost:11434/v1` |
| `CODEX_BIN` | extractor (host) | `/Applications/ChatGPT.app/Contents/Resources/codex` |

See [remote-lessons-gpt/.env.example](remote-lessons-gpt/.env.example), [extractor-lessons-gpt/.env.example](extractor-lessons-gpt/.env.example), and [local-lessons-gpt/.env.example](local-lessons-gpt/.env.example) (Docker port only).

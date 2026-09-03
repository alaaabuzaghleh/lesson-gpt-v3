# Lessons GPT

Textbook ingestion platform for Arabic and mixed-language school books.

Admins upload PDFs locally, extract pages with **Ollama** or **Codex**, and publish structured content to students through a **remote API** backed by PostgreSQL and OpenSearch.

---

## Architecture

| Component | PostgreSQL / OpenSearch | Role |
|-----------|-------------------------|------|
| **infra/** (Docker) | Hosts Postgres + OpenSearch | Database layer |
| **remote-lessons-gpt/** (Docker) | **Only direct client** | Auth, catalog, search, ingest |
| **extractor-lessons-gpt/** (host) | No access | Local PDFs; pages via HTTP ingest |
| **admin-lessons-gpt/** (host) | No access | UI → remote + extractor APIs |

```
infra/ (Docker)          Postgres + OpenSearch
remote-lessons-gpt/      API :8081  ──connects──▶ infra
extractor-lessons-gpt/   :8080  ──ingest HTTP──▶ remote
admin-lessons-gpt/       :5173  ──▶ remote (auth/catalog) + extractor (PDFs/jobs)
```

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- **Python 3.11–3.13**
- **Node.js 20+**
- **[Ollama](https://ollama.com)** (`qwen2.5vl:7b`)
- **ChatGPT.app** (optional, for Codex)

---

## Run locally

### 1. Infrastructure

```bash
cd infra
chmod +x up.sh down.sh
./up.sh
```

Postgres `:5432`, OpenSearch `:9200`, Dashboards `:5601`, pgAdmin `:5050`.

### 2. Remote API

```bash
cd remote-lessons-gpt
cp .env.example .env
chmod +x up.sh down.sh
./up.sh
```

API docs: http://localhost:8081/docs

Stop Docker:

```bash
cd remote-lessons-gpt && ./down.sh
cd ../infra && ./down.sh
```

### 3. Extractor (host)

```bash
cd extractor-lessons-gpt
cp .env.example .env          # set REMOTE_API_URL=http://localhost:8081
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ollama pull qwen2.5vl:7b
python run_api.py
```

http://localhost:8080/docs — stores PDFs on disk; **no** Postgres/OpenSearch.

### 4. Admin UI (host)

```bash
cd admin-lessons-gpt
npm install && npm run dev
```

http://localhost:5173 — leave `VITE_*` empty (Vite proxies `/remote-api` → `:8081`, `/api` → `:8080`).

### 5. Log in

- URL: http://localhost:5173/login
- Email: `superadmin@lessonsgpt.com`
- Password: `SuperAdmin123!` (from `remote-lessons-gpt/.env`)

Upload a PDF, start extraction — each page is ingested into Postgres + OpenSearch on the remote server.

---

## Packages

| Folder | Port | Runs in |
|--------|------|---------|
| [infra/](infra/) | 5432, 9200, … | Docker |
| [remote-lessons-gpt/](remote-lessons-gpt/) | 8081 | Docker |
| [extractor-lessons-gpt/](extractor-lessons-gpt/) | 8080 | Host |
| [admin-lessons-gpt/](admin-lessons-gpt/) | 5173 | Host |

---

## Environment files

| File | Used for |
|------|----------|
| `remote-lessons-gpt/.env` | Auth, DB, OpenSearch, `REMOTE_API_HOST_PORT` |
| `extractor-lessons-gpt/.env` | `REMOTE_API_URL`, Ollama/Codex |
| `admin-lessons-gpt/.env` | Vite proxy bases (empty in dev) |

Docker overrides `DATABASE_URL` / `OPENSEARCH_URL` to `postgres` / `opensearch` hostnames automatically.

---

## Package READMEs

- [infra/README.md](infra/README.md)
- [remote-lessons-gpt/README.md](remote-lessons-gpt/README.md)
- [extractor-lessons-gpt/README.md](extractor-lessons-gpt/README.md)
- [admin-lessons-gpt/README.md](admin-lessons-gpt/README.md)

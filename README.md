# Lessons GPT v3

Textbook ingestion platform for Arabic and mixed-language school books: a **local admin** extracts PDFs on your machine and publishes each page to a **remote production server** (PostgreSQL + OpenSearch) so students can study with the AI teacher app.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Local machine (admin)                                          │
│                                                                 │
│  lessonsGPTAdmin (:5173)                                        │
│       │ login (email/password → remote)                         │
│       ▼                                                         │
│  pdf_codex_extractor API (:8080)                                │
│       │ PDF upload + extraction (Ollama or Codex)               │
│       │ after each page → POST /api/v1/ingest/jobs/{id}/pages   │
│       ▼                                                         │
│  Local PostgreSQL (jobs, uploaded PDFs)                         │
│  Local OpenSearch (optional dev search)                         │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS + admin JWT
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Remote production server                                       │
│                                                                 │
│  ai_book_ingestor_v4 API                                        │
│       ├── Auth (users, JWT)                                     │
│       ├── Catalog (country → system → grade → subject)          │
│       ├── Ingest API (/api/v1/ingest/*)                         │
│       ├── PostgreSQL (books, jobs, book_pages)                  │
│       └── OpenSearch (school_book_content_v3) ← student search    │
└─────────────────────────────────────────────────────────────────┘
```

| Component | Role |
|-----------|------|
| [lessonsGPTAdmin](lessonsGPTAdmin/) | Arabic RTL admin UI |
| [pdf_codex_extractor](pdf_codex_extractor/) | Local extraction API + worker |
| [ai_book_ingestor_v4](ai_book_ingestor_v4/) | Remote production API, catalog, ingest |

## Prerequisites

- **Python 3.11–3.13** (not 3.14)
- **Node.js 20+**
- **Docker Desktop** (Postgres + OpenSearch)
- **Ollama** with `qwen2.5vl:7b` for local extraction, **or** ChatGPT.app Codex CLI for cloud extraction

## Quick start (local admin → remote server)

### 1. Start Postgres and OpenSearch

Use either project's compose file (same services):

```bash
cd pdf_codex_extractor
docker compose up -d postgres opensearch
```

Or from `ai_book_ingestor_v4` if you run the remote API locally too.

| Service | URL |
|---------|-----|
| Postgres | `localhost:5432` — db `lessons_gpt`, user/password `postgres` |
| OpenSearch | http://localhost:9200 |

### 2. Remote production API

Deploy `ai_book_ingestor_v4` on your server (or run locally on another port for testing):

```bash
cd ai_book_ingestor_v4
cp .env.example .env
python3.13 -m venv .venv && source .venv/bin/activate
pip install -U pip && pip install -r requirements.txt
python run_api.py
```

Default: http://localhost:8080 — use **8081** locally if the local extractor also uses 8080 (set `API_PORT=8081` in remote `.env`).

On first start the API seeds a super-admin from `.env`:

- Email: `superadmin@lessonsgpt.com`
- Password: `SuperAdmin123!`

### 3. Local extractor API

```bash
cd pdf_codex_extractor
cp .env.example .env
python3.13 -m venv .venv && source .venv/bin/activate
pip install -U pip && pip install -r requirements.txt
```

Edit `.env` — set the remote server URL:

```env
REMOTE_API_URL=http://localhost:8081
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/lessons_gpt
OPENSEARCH_URL=http://localhost:9200
EXTRACTOR_BACKEND=local
VLM_BASE_URL=http://localhost:11434/v1
VLM_MODEL=qwen2.5vl:7b
```

Pull the vision model (local backend):

```bash
ollama pull qwen2.5vl:7b
```

Start the API:

```bash
python run_api.py
```

Local API: http://localhost:8080/docs

### 4. Admin UI

```bash
cd lessonsGPTAdmin
npm install
npm run dev
```

Open http://localhost:5173/login — sign in with your **remote** admin email and password.

The Vite dev server proxies `/api` and `/health` to the local extractor on `:8080`. Login, catalog, and search are forwarded to the remote server when `REMOTE_API_URL` is set on the local API.

### 5. Extract and publish a book

1. In the admin UI, pick a subject from the remote catalog.
2. Upload a PDF (stored locally; metadata registered on remote).
3. Start extraction with **“نشر كل صفحة على الخادم البعيد”** enabled (default).
4. Each finished page is indexed to remote OpenSearch and saved in remote `book_pages`.
5. Use **Search** in the admin UI to verify content on the remote index.

## Ports (typical local setup)

| App | Port | URL |
|-----|------|-----|
| Admin UI | 5173 | http://localhost:5173 |
| Local extractor API | 8080 | http://localhost:8080/docs |
| Remote production API | 8081 | http://localhost:8081/docs |
| OpenSearch | 9200 | http://localhost:9200 |
| Ollama | 11434 | http://localhost:11434 |

## Extraction backends

| Backend | When to use | Admin / API setting |
|---------|-------------|---------------------|
| **Local (Ollama)** | Offline, free, slower (~minutes/page) | `extractor_backend: "local"` |
| **Codex** | ChatGPT.app installed, faster structured JSON | `extractor_backend: "codex"` |

Codex binary default: `/Applications/ChatGPT.app/Contents/Resources/codex`

CLI (without admin UI):

```bash
cd pdf_codex_extractor
source .venv/bin/activate
python run_extract.py run /path/to/book.pdf --backend local --resume
```

## Remote ingest API (production)

Authenticated admin routes on `ai_book_ingestor_v4`:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/ingest/books` | Register book metadata from local admin |
| POST | `/api/v1/ingest/jobs` | Create a remote receiving job |
| POST | `/api/v1/ingest/jobs/{id}/pages` | Index page docs + save `book_pages` row |
| POST | `/api/v1/ingest/jobs/{id}/complete` | Mark job completed |
| GET | `/api/v1/ingest/books/{book_id}/pages` | List ingested pages |

## Environment variables

| Variable | Where | Purpose |
|----------|-------|---------|
| `REMOTE_API_URL` | `pdf_codex_extractor/.env` | Remote production API base URL |
| `DATABASE_URL` | both backends | PostgreSQL connection |
| `OPENSEARCH_URL` | both backends | OpenSearch cluster |
| `JWT_SECRET` | remote API | Must match if validating tokens locally |
| `VLM_*` | local extractor | Ollama / local VLM settings |
| `CODEX_*` | local extractor | Codex CLI rate-limit and retry settings |

See `.env.example` in each project for the full list.

## Project layout

```
lessons-gpt-v3/
├── README.md                 ← this file
├── lessonsGPTAdmin/          ← React admin UI
├── pdf_codex_extractor/      ← local extraction + remote sync
└── ai_book_ingestor_v4/      ← remote production API + ingest
```

Runtime data (not committed): `pdf_codex_extractor/data/`, `output/`, `ai_book_ingestor_v4/data/`.

## Further reading

- [pdf_codex_extractor/README.md](pdf_codex_extractor/README.md) — local API, CLI, Docker
- [ai_book_ingestor_v4/README.md](ai_book_ingestor_v4/README.md) — production server, MinerU pipeline (legacy full-server extraction)
- [lessonsGPTAdmin/README.md](lessonsGPTAdmin/README.md) — frontend development

## Troubleshooting

**Login fails** — Check `REMOTE_API_URL` on the local extractor points to a running remote API. Use remote admin credentials, not local DB users.

**Remote sync fails mid-job** — Token may have expired; log in again and resume the job. Check remote API logs and OpenSearch connectivity.

**Subject not found on upload** — Catalog lives on the remote server; create subjects there first or verify `REMOTE_API_URL`.

**Port conflict** — Run remote API on `8081` and local extractor on `8080`, or adjust `API_PORT` in each `.env`.

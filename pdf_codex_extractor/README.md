# PDF Codex Extractor

Local admin API for textbook extraction. Uploads PDFs locally, extracts pages with **Ollama (local VLM)** or **Codex**, and publishes each page to the remote production server via the secure ingest API.

Works with [lessonsGPTAdmin](../lessonsGPTAdmin) on port 5173.

## Architecture

```
Admin UI (:5173)
    → Local API (:8080)  — PDF storage, extraction worker
    → Remote API         — auth, catalog, PostgreSQL, OpenSearch (students)
```

Set `REMOTE_API_URL` in `.env` to your `ai_book_ingestor_v4` deployment. Login uses remote credentials; each extracted page calls `POST /api/v1/ingest/jobs/{id}/pages`.

## Quick start

```bash
# Dependencies
cd pdf_codex_extractor
python3.13 -m venv .venv && source .venv/bin/activate
pip install -U pip && pip install -r requirements.txt
cp .env.example .env

# Edit .env: REMOTE_API_URL, DATABASE_URL, OPENSEARCH_URL

# Infrastructure
docker compose up -d postgres opensearch

# Local VLM
ollama pull qwen2.5vl:7b

# API
python run_api.py

# Admin UI (separate terminal)
cd ../lessonsGPTAdmin && npm install && npm run dev
```

Open http://localhost:5173 and log in with your **remote** admin account.

## Key `.env` settings

```env
REMOTE_API_URL=https://your-production-api.example.com
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/lessons_gpt
OPENSEARCH_URL=http://localhost:9200
OPENSEARCH_INDEX=school_book_content_v3
EXTRACTOR_BACKEND=local
VLM_BASE_URL=http://localhost:11434/v1
VLM_MODEL=qwen2.5vl:7b
CODEX_BIN=/Applications/ChatGPT.app/Contents/Resources/codex
```

## Extraction backends

| Backend | API field | Notes |
|---------|-----------|-------|
| Ollama | `extractor_backend: "local"` | Default; ~few min/page |
| Codex | `extractor_backend: "codex"` | Requires ChatGPT.app; use rate-limit settings in `.env` |

## Admin workflow

1. Upload PDF → registered locally + on remote (`/api/v1/ingest/books`).
2. Start job with **sync to remote** enabled (default in UI).
3. Worker extracts each page → indexes locally (optional) → **publishes to remote** per page.
4. Job completes → remote job marked complete.

## CLI (optional)

```bash
python run_extract.py run book.pdf --backend local --resume
python run_extract.py doctor --backend local
```

## Job output

```
data/jobs/{job_id}/
  pages/           rendered PNGs
  pages_json/      structured JSON per page
  manifest.json
  outline.json
```

## Docker

```bash
docker compose up -d
```

Builds the local API with Postgres and OpenSearch. Set `REMOTE_API_URL` in compose env or `.env` for remote sync.

## API docs

http://localhost:8080/docs

Same routes as the ingestor admin API for books/jobs, plus `extractor_backend`, `sync_to_remote`, and remote sync status fields on jobs.

See the [root README](../README.md) for the full system setup.

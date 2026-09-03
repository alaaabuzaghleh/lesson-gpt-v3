# extractorLessonsGPT

Local admin API for PDF textbook extraction. Uploads PDFs locally, extracts pages with **Ollama (local VLM)** or **Codex**, and publishes each page to **remoteLessonsGPT** via the secure ingest API.

Works with [adminLessonsGPT](../admin-lessons-gpt) on port 5173.

## Architecture

```
adminLessonsGPT (:5173)
    → extractorLessonsGPT (:8080)  — PDF storage, extraction worker
    → remoteLessonsGPT             — auth, catalog, PostgreSQL, OpenSearch
```

Set `REMOTE_API_URL` in `.env` to your remoteLessonsGPT deployment.

## Quick start

```bash
cd extractor-lessons-gpt
python3.13 -m venv .venv && source .venv/bin/activate
pip install -U pip && pip install -r requirements.txt
cp .env.example .env
# Edit .env: REMOTE_API_URL, DATABASE_URL, OPENSEARCH_URL

docker compose up -d postgres opensearch   # or use local-lessons-gpt compose
ollama pull qwen2.5vl:7b
python run_api.py
```

API docs: http://localhost:8080/docs

## Key `.env` settings

```env
REMOTE_API_URL=http://localhost:8081
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/lessons_gpt
OPENSEARCH_URL=http://localhost:9200
EXTRACTOR_BACKEND=local
VLM_BASE_URL=http://localhost:11434/v1
VLM_MODEL=qwen2.5vl:7b
```

## CLI (optional)

```bash
python run_extract.py run book.pdf --backend local --resume
python run_extract.py doctor --backend local
```

See the [root README](../README.md) and [local-lessons-gpt](../local-lessons-gpt/README.md) for the full system setup.

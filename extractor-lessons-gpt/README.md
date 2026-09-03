# extractorLessonsGPT

Local admin API for PDF textbook extraction. Uploads PDFs locally, extracts pages with **Ollama (local VLM)** or **Codex**, and publishes each page to **remoteLessonsGPT** via the secure ingest API.

Works with [adminLessonsGPT](../admin-lessons-gpt) on port 5173.

## Architecture

```
adminLessonsGPT (:5173)
    → remoteLessonsGPT (:8081)     — auth, catalog, search, PostgreSQL, OpenSearch
    → extractorLessonsGPT (:8080)  — local PDFs, extraction worker, remote ingest only
```

Set `REMOTE_API_URL` in `.env` to your remoteLessonsGPT deployment. The extractor **never** connects to PostgreSQL or OpenSearch directly.

## Quick start

Start infrastructure and remote API via [localLessonsGPT](../local-lessons-gpt/README.md):

```bash
cd ../local-lessons-gpt
./scripts/local up all
```

Then run the extractor on your host:

```bash
cd extractor-lessons-gpt
python3.13 -m venv .venv && source .venv/bin/activate
pip install -U pip && pip install -r requirements.txt
cp .env.example .env   # REMOTE_API_URL=http://localhost:8081
ollama pull qwen2.5vl:7b
python run_api.py
```

API docs: http://localhost:8080/docs

## Key `.env` settings

```env
REMOTE_API_URL=http://localhost:8081
EXTRACTOR_BACKEND=local
VLM_BASE_URL=http://localhost:11434/v1
VLM_MODEL=qwen2.5vl:7b
API_DATA_ROOT=./data
```

## CLI (optional)

```bash
python run_extract.py run book.pdf --backend local --resume
python run_extract.py doctor --backend local
```

See the [root README](../README.md) and [local-lessons-gpt](../local-lessons-gpt/README.md) for the full system setup.

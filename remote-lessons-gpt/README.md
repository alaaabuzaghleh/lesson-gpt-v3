# remoteLessonsGPT

> **Production server** for Lessons GPT: auth, catalog, secure ingest API, PostgreSQL, and OpenSearch. Receives per-page content from [extractorLessonsGPT](../extractor-lessons-gpt) running on admin machines.

Universal Arabic/English textbook ingestion framework with REST API, background jobs, and OpenSearch indexing for agentic AI teachers.

## Role in the monorepo

| Package | Port | Purpose |
|---------|------|---------|
| **remoteLessonsGPT** (this) | 8081 | Production API + student search index |
| [extractorLessonsGPT](../extractor-lessons-gpt) | 8080 | Local PDF extraction |
| [adminLessonsGPT](../admin-lessons-gpt) | 5173 | Admin UI |
| [localLessonsGPT](../local-lessons-gpt) | — | Dev orchestration |

## Quick start

```bash
cd remote-lessons-gpt
cp .env.example .env
python3.13 -m venv .venv && source .venv/bin/activate
pip install -U pip && pip install -r requirements.txt

docker compose up -d postgres opensearch
python run_api.py
```

Default: http://localhost:8080 — use `API_PORT=8081` when extractor also runs on 8080.

## Secure ingest API (local admin)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/ingest/books` | Register book metadata |
| POST | `/api/v1/ingest/jobs` | Create remote receiving job |
| POST | `/api/v1/ingest/jobs/{id}/pages` | Index page + save `book_pages` |
| POST | `/api/v1/ingest/jobs/{id}/complete` | Mark job completed |

Requires admin JWT from `POST /api/v1/auth/login`.

## Legacy MinerU pipeline

This package still supports the full MinerU + VLM server-side extraction pipeline (see original docs below). The recommended admin workflow uses **extractorLessonsGPT** on a local machine instead.

---

## REST API + background jobs

The extraction pipeline can run as a long-lived REST service. Jobs are persisted in PostgreSQL and claimed by worker threads.

See `python run_api.py` and http://localhost:8080/docs for the full API reference.

Default admin: `superadmin@lessonsgpt.com` / `SuperAdmin123!`

For detailed MinerU setup, OpenSearch tuning, and CLI usage, see the extended sections in this file's history or run `python main.py --help`.

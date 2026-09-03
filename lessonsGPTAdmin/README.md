# LessonsGPT Admin

Arabic RTL admin dashboard for the **AI Book Ingestor v4** REST API.

Manage the catalog hierarchy (country → education system → grade → subject), upload textbooks, monitor extraction jobs with live SSE progress, and search indexed content.

## How to run frontend and backend

Use Docker for **Postgres** and **OpenSearch** only. Run MinerU, the API, and this UI on the host.

Python **3.11–3.13** is required for the API + MinerU (3.14 is not supported).

### 1. Postgres + OpenSearch

```bash
cd ai_book_ingestor_v4
docker compose up -d postgres opensearch dashboards
```

| Service | URL |
|---------|-----|
| Postgres | `localhost:5432` / `lessons_gpt` / `postgres` / `postgres` |
| OpenSearch | http://localhost:9200 |
| Dashboards | http://localhost:5601 |

### 2. Backend `.env` and Python env

`ai_book_ingestor_v4/.env` is already configured for those Compose services and MinerU at `http://127.0.0.1:8000`. Recreate it with `cp .env.example .env` if needed.

```bash
cd ai_book_ingestor_v4
python3.13 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
pip install "mineru[pipeline]"
```

### 3. MinerU

```bash
cd ai_book_ingestor_v4
source .venv/bin/activate
mineru-api --host 127.0.0.1 --port 8000
```

http://127.0.0.1:8000/health

### 4. Book ingestion API

```bash
cd ai_book_ingestor_v4
source .venv/bin/activate
python run_api.py
```

http://localhost:8080/docs

### 5. Admin UI

```bash
cd lessonsGPTAdmin
cp .env.example .env
npm install
npm run dev
```

Open **http://localhost:5173/login**

| Field | Value |
|-------|-------|
| Email | `superadmin@lessonsgpt.com` |
| Password | `SuperAdmin123!` |

`lessonsGPTAdmin/.env` should keep `VITE_API_BASE_URL` empty so Vite proxies `/api` and `/health` to `http://localhost:8080`.

Page extraction also needs a local VLM (Ollama by default): `ollama pull qwen2.5vl:7b` and `ollama serve`.

Only **admin** and **super_admin** roles can sign in. **super_admin** can create additional admin users from the Admins page.

## Features

| Page | Description |
|------|-------------|
| **Login** | JWT authentication; student accounts are rejected |
| **Dashboard** | API health, job stats, active extractions |
| **Catalog** | Manage country → education system → grade → subject hierarchy |
| **Books** | Upload PDF textbooks (subject required from catalog) |
| **Jobs** | Filter by status, live progress polling |
| **Job detail** | SSE event stream, cancel/retry, quality/manifest/errors |
| **Admins** | Super admin: create admin users |
| **Search** | Query OpenSearch indexed textbook content |

## Production build

```bash
npm run build
npm run preview
```

Set `VITE_API_BASE_URL` to your deployed API URL when not using the dev proxy:

```env
VITE_API_BASE_URL=https://your-api.example.com
```

## Stack

- React 18 + TypeScript
- Vite 6
- React Router 7
- Lucide icons
- Custom CSS with RTL support

## Related

- API docs: http://localhost:8080/docs
- Ingestor README: [../ai_book_ingestor_v4/README.md](../ai_book_ingestor_v4/README.md)

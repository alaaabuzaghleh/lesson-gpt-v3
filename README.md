# Lessons GPT

Textbook ingestion API, MinerU document parser, OpenSearch index, and Arabic RTL admin UI.

## How to run frontend and backend

Docker is used only for **Postgres** and **OpenSearch**. MinerU, the API, and the admin UI run on the host.

Requires **Python 3.11–3.13** (not 3.14), Node.js 20+, Docker Desktop, and optionally [Ollama](https://ollama.com) for vision extraction.

### 1. Postgres + OpenSearch

```bash
cd ai_book_ingestor_v4
docker compose up -d postgres opensearch dashboards
```

### 2. Backend env + dependencies

`ai_book_ingestor_v4/.env` already points at Compose Postgres/OpenSearch and MinerU on port 8000.

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
source .venv/bin/activate
mineru-api --host 127.0.0.1 --port 8000
```

### 4. API

```bash
source .venv/bin/activate
python run_api.py
```

### 5. Admin UI

```bash
cd lessonsGPTAdmin
npm install
npm run dev
```

| App | URL |
|-----|-----|
| Admin login | http://localhost:5173/login |
| API docs | http://localhost:8080/docs |
| MinerU | http://127.0.0.1:8000/docs |
| OpenSearch | http://localhost:9200 |
| Dashboards | http://localhost:5601 |

Default admin: `superadmin@lessonsgpt.com` / `SuperAdmin123!`

More detail: [ai_book_ingestor_v4/README.md](ai_book_ingestor_v4/README.md) and [lessonsGPTAdmin/README.md](lessonsGPTAdmin/README.md).

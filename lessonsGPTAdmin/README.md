# LessonsGPT Admin

Arabic RTL admin dashboard for the **AI Book Ingestor v4** REST API.

Manage the catalog hierarchy (country → education system → grade → subject), upload textbooks, monitor extraction jobs with live SSE progress, and search indexed content.

## Prerequisites

- Node.js 20+
- PostgreSQL running (via Docker Compose in `ai_book_ingestor_v4`)
- [AI Book Ingestor API](../ai_book_ingestor_v4/) running on `http://localhost:8080`
- OpenSearch (optional, for search features)

## Quick start

```bash
# Terminal 1 — PostgreSQL + OpenSearch
cd ai_book_ingestor_v4
docker compose up postgres opensearch -d

# Terminal 2 — API
source .venv/bin/activate
pip install -r requirements.txt
python run_api.py

# Terminal 3 — Admin UI
cd lessonsGPTAdmin
npm install
npm run dev
```

Open **http://localhost:5173/login**

Default super admin (from `.env`):

| Field | Value |
|-------|-------|
| Email | `superadmin@lessonsgpt.com` |
| Password | `SuperAdmin123!` |

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

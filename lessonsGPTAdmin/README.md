# LessonsGPT Admin

React admin dashboard for the **AI Book Ingestor v4** REST API.

Manage textbook uploads, monitor extraction jobs with live SSE progress, inspect quality reports, and search indexed content in OpenSearch.

## Prerequisites

- Node.js 20+
- [AI Book Ingestor API](../ai_book_ingestor_v4/) running on `http://localhost:8080`
- OpenSearch (optional, for search features) via Docker Compose

## Quick start

```bash
cd lessonsGPTAdmin
npm install
cp .env.example .env   # optional — dev proxy works without it
npm run dev
```

Open **http://localhost:5173**

The Vite dev server proxies `/api` and `/health` to the ingestor API on port 8080.

## Features

| Page | Description |
|------|-------------|
| **Dashboard** | API health, job stats, active extractions |
| **Books** | Upload PDF textbooks with metadata JSON |
| **Book detail** | View metadata, start extraction jobs |
| **Jobs** | Filter by status, live progress polling |
| **Job detail** | SSE event stream, cancel/retry, quality/manifest/errors |
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

- React 19 + TypeScript
- Vite 8
- React Router 7
- Lucide icons
- Custom CSS (no UI framework — easy to extend)

## Related

- API docs: http://localhost:8080/docs
- Ingestor README: [../ai_book_ingestor_v4/README.md](../ai_book_ingestor_v4/README.md)

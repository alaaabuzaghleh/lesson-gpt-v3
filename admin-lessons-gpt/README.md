# adminLessonsGPT

Arabic RTL admin dashboard for **extractorLessonsGPT** (local) and **remoteLessonsGPT** (production).

## What it connects to

| Traffic | Target |
|---------|--------|
| Login, catalog, search | remoteLessonsGPT (via extractor proxy) |
| Books, jobs, uploads | extractorLessonsGPT API (:8080) |

## Run

See [local-lessons-gpt](../local-lessons-gpt/README.md) for the full stack, or:

```bash
cd admin-lessons-gpt
npm install
npm run dev
```

Open http://localhost:5173/login

Leave `VITE_API_BASE_URL` empty so Vite proxies `/api` and `/health` to `http://localhost:8080`.

## Features

- Remote admin login (email/password)
- Catalog hierarchy (country → system → grade → subject)
- PDF upload and extraction job control
- Live job progress (SSE)
- Search indexed content on remote OpenSearch
- Per-page remote publish status on job detail

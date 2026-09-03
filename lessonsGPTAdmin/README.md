# LessonsGPT Admin

Arabic RTL admin dashboard for local PDF extraction and remote textbook publishing.

## What it connects to

| Traffic | Target |
|---------|--------|
| Login, catalog, search | Remote production API (via local extractor proxy) |
| Books, jobs, uploads | Local `pdf_codex_extractor` API (:8080) |

## Run

Start the stack as described in the [root README](../README.md), then:

```bash
cd lessonsGPTAdmin
npm install
npm run dev
```

Open http://localhost:5173/login

Leave `VITE_API_BASE_URL` empty in `.env` so Vite proxies `/api` and `/health` to `http://localhost:8080`.

## Features

- Remote admin login (email/password)
- Catalog hierarchy (country → system → grade → subject)
- PDF upload and extraction job control
- Live job progress (SSE)
- Search indexed content on the remote OpenSearch cluster
- Per-page remote publish status on job detail

Default credentials come from the **remote** server's `.env` (e.g. `superadmin@lessonsgpt.com` / `SuperAdmin123!`).

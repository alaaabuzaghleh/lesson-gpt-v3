# adminLessonsGPT

Arabic RTL admin dashboard for **extractorLessonsGPT** (local) and **remoteLessonsGPT** (production).

## What it connects to

| Traffic | Target | Dev proxy |
|---------|--------|-----------|
| Login, catalog, search | remoteLessonsGPT `:8081` | `/remote-api` |
| Books, jobs, uploads | extractorLessonsGPT `:8080` | `/api` |

## Run

Start Docker first ([infra](../infra) + [remote-lessons-gpt](../remote-lessons-gpt)), then:

```bash
cd admin-lessons-gpt
npm install
npm run dev
```

Open http://localhost:5173/login

Leave `VITE_REMOTE_API_BASE_URL` and `VITE_EXTRACTOR_API_BASE_URL` empty in `.env`.

See the [root README](../README.md) for the full stack.

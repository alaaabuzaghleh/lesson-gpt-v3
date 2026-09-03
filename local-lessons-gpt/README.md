# localLessonsGPT

Dev orchestration for the Lessons GPT monorepo. Runs **infrastructure in Docker** and **remoteLessonsGPT in Docker**; runs **extractorLessonsGPT** and **adminLessonsGPT** on your host (Ollama/Codex need local access).

## Two Docker stacks

| Stack | File | Services |
|-------|------|----------|
| **External (infra)** | `../infra/docker-compose.yml` | Postgres, OpenSearch, OpenSearch Dashboards, pgAdmin |
| **Internal (apps)** | `docker-compose.apps.yml` | remoteLessonsGPT API |

Both share the Docker network `lessons-gpt`.

## CLI (from your machine)

```bash
cd local-lessons-gpt
cp .env.example .env                              # optional orchestration overrides
cp ../remote-lessons-gpt/.env.example ../remote-lessons-gpt/.env
chmod +x scripts/local scripts/start-dev.sh

./scripts/local up infra        # Postgres + OpenSearch + Dashboards + pgAdmin
./scripts/local up apps         # remoteLessonsGPT API (requires infra)
./scripts/local up all          # infra + apps + host instructions
./scripts/local status
./scripts/local down all
./scripts/local host            # print extractor + admin commands
```

One-liner full Docker bootstrap:

```bash
./scripts/start-dev.sh
```

## URLs after `up all`

| Service | URL | Credentials |
|---------|-----|-------------|
| **remoteLessonsGPT** | http://localhost:8081/docs | API login below |
| **OpenSearch** | http://localhost:9200 | (no auth, local dev) |
| **OpenSearch Dashboards** | http://localhost:5601 | |
| **pgAdmin** (PostgreSQL UI) | http://localhost:5050 | `admin@lessonsgpt.local` / `admin` |
| **Postgres** (direct) | `localhost:5432` | `postgres` / `postgres`, db `lessons_gpt` |

### pgAdmin — connect to Postgres

1. Open http://localhost:5050
2. Add server → **Host:** `postgres`, **Port:** `5432`, **Username:** `postgres`, **Password:** `postgres`

## Host apps (not in Docker)

After Docker is up, start extraction and admin on your Mac:

```bash
./scripts/local host
```

Or manually:

```bash
# extractorLessonsGPT (:8080)
cd ../extractor-lessons-gpt
cp .env.example .env   # REMOTE_API_URL=http://localhost:8081
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ollama pull qwen2.5vl:7b
python run_api.py

# adminLessonsGPT (:5173)
cd ../admin-lessons-gpt
npm install && npm run dev
```

Login: http://localhost:5173/login — `superadmin@lessonsgpt.com` / `SuperAdmin123!`

## Architecture

```
┌─ infra/docker-compose.yml (external) ─────────────────────┐
│  Postgres :5432  │  OpenSearch :9200  │  Dashboards :5601 │
│  pgAdmin :5050                                            │
└───────────────────────────┬───────────────────────────────┘
                            │ network: lessons-gpt
┌─ docker-compose.apps.yml (internal) ──────────────────────┐
│  remoteLessonsGPT API :8081                               │
└───────────────────────────┬───────────────────────────────┘
                            │
┌─ your host ───────────────────────────────────────────────┐
│  extractorLessonsGPT :8080  │  adminLessonsGPT :5173      │
└───────────────────────────────────────────────────────────┘
```

## Package map

| Product | Where it runs | Port |
|---------|---------------|------|
| remoteLessonsGPT | Docker (`docker-compose.apps.yml`) | 8081 |
| extractorLessonsGPT | Host | 8080 |
| adminLessonsGPT | Host | 5173 |

See the [root README](../README.md) for the full system overview.

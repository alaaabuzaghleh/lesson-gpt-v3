# localLessonsGPT

Dev orchestration for the Lessons GPT monorepo: shared Docker infrastructure and start scripts.

## What this package is

**localLessonsGPT** is not an application server. It runs the shared services and documents how to start the three apps together:

| Product | Folder | Port |
|---------|--------|------|
| remoteLessonsGPT | [remote-lessons-gpt](../remote-lessons-gpt) | 8081 |
| extractorLessonsGPT | [extractor-lessons-gpt](../extractor-lessons-gpt) | 8080 |
| adminLessonsGPT | [admin-lessons-gpt](../admin-lessons-gpt) | 5173 |

## Quick start (5 minutes)

### 1. Infrastructure

```bash
cd local-lessons-gpt
docker compose up -d
```

Starts Postgres (`5432`) and OpenSearch (`9200`).

### 2. Python environments

```bash
# Remote API
cd ../remote-lessons-gpt
cp .env.example .env
python3.13 -m venv .venv && source .venv/bin/activate
pip install -U pip && pip install -r requirements.txt

# Extractor API
cd ../extractor-lessons-gpt
cp .env.example .env
# Set REMOTE_API_URL=http://localhost:8081 in .env
python3.13 -m venv .venv && source .venv/bin/activate
pip install -U pip && pip install -r requirements.txt
ollama pull qwen2.5vl:7b
```

### 3. Admin UI

```bash
cd ../admin-lessons-gpt
npm install
```

### 4. Start everything

```bash
./local-lessons-gpt/scripts/start-dev.sh
```

Then run the three commands it prints (remote → extractor → admin).

### 5. Log in

http://localhost:5173/login — use remote admin credentials (`superadmin@lessonsgpt.com` / `SuperAdmin123!` by default).

## Environment template

See [.env.example](.env.example) for variables shared across packages.

## Architecture

See the [root README](../README.md) for the full system diagram.

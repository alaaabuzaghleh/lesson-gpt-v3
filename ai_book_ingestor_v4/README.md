# Universal AI Textbook Ingestor v4 — REST API + Background Jobs — Arabic + English

A production-oriented Python ingestion framework for converting **Arabic, English, or mixed-language textbooks** into structured, page-grounded records for **OpenSearch + Agentic Search**.

It is intentionally **not built around a fixed subject taxonomy**. The same pipeline can process mathematics, physics, chemistry, biology, geography, history, literature, Arabic, English, religious/cultural studies, computer science, art, economics, vocational material, or unfamiliar future textbook formats.

## New in v4: REST API + persistent background extraction jobs

The extraction pipeline can now run as a long-lived REST service. Uploading a textbook and extracting it are separate resources: the PDF is registered once, then one or more extraction jobs can be created for it.

Jobs are **not** implemented with FastAPI's in-memory `BackgroundTasks`. They are persisted in SQLite and claimed by worker threads, which provides:

- durable queued/running/completed/failed/cancelled status;
- continuous stage/progress/current-page updates;
- event history and Server-Sent Events (SSE) live progress;
- cooperative cancellation between pages/major stages;
- retry with resume from already-extracted page artifacts;
- recovery of interrupted `running` jobs after a service restart;
- separate extraction and OpenSearch-indexing stages;
- retained `manifest.json`, `quality_report.json`, `structure.json`, `errors.jsonl`, page images, crops and JSONL output;
- the existing CLI remains available.

### Job state flow

```text
queued
  |
  v
running
  |
  +--> cancel_requested --> cancelled
  |
  +--> failed -----------+--> retry --> queued
  |
  v
completed
```

### Processing stages exposed by the API

```text
metadata
  -> page_extraction
  -> question_intelligence
  -> visual_analysis
  -> artifact_generation
  -> quality_report
  -> extraction_complete
  -> opensearch_indexing (optional)
  -> completed
```

### Run the API locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run_api.py
```

The service listens on:

```text
http://localhost:8080
```

Interactive OpenAPI documentation is available at:

```text
http://localhost:8080/docs
```

and the raw OpenAPI schema at:

```text
http://localhost:8080/openapi.json
```

### REST workflow

#### 1. Upload/register a textbook

`metadata` is optional JSON and can contain known values such as country, curriculum, education system, grade, subject, semester, academic year and language. Unknown fields are harmless because the ingestion model remains open-ended.

```bash
curl -X POST http://localhost:8080/api/v1/books \
  -F 'file=@./books/science-grade-8.pdf' \
  -F 'metadata={"country":"Jordan","curriculum":"Jordan National Curriculum","grade":"Grade 8","subject":"Science","language":"ar"}'
```

Example response:

```json
{
  "resource_id": "4f260b97...",
  "filename": "science-grade-8.pdf",
  "size_bytes": 23144231,
  "sha256": "...",
  "metadata": {
    "country": "Jordan",
    "grade": "Grade 8",
    "subject": "Science"
  },
  "created_at": "2026-08-30T...+00:00"
}
```

#### 2. Start an asynchronous extraction job

```bash
curl -X POST http://localhost:8080/api/v1/books/4f260b97.../extraction-jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "start_page": 1,
    "end_page": null,
    "resume": true,
    "index_to_opensearch": true,
    "recreate_index": false,
    "metadata_overrides": {}
  }'
```

The API immediately returns `202 Accepted` with a `job_id`; extraction continues in a worker.

#### 3. Poll job status

```bash
curl http://localhost:8080/api/v1/jobs/JOB_ID
```

A running job contains information such as:

```json
{
  "job_id": "...",
  "status": "running",
  "progress": 37.08,
  "stage": "page_extraction",
  "message": "Extracted page 87 of 240",
  "current_page": 87,
  "total_pages": 240
}
```

#### 4. Stream live progress with SSE

```bash
curl -N http://localhost:8080/api/v1/jobs/JOB_ID/events/stream
```

Each event is persisted, so a client can also use normal polling:

```bash
curl 'http://localhost:8080/api/v1/jobs/JOB_ID/events?after_id=0'
```

#### 5. Cancel

```bash
curl -X POST http://localhost:8080/api/v1/jobs/JOB_ID/cancel
```

Cancellation is cooperative: the current VLM request is allowed to finish, then the pipeline stops at the next cancellation checkpoint. Existing page extraction files remain intact for a later retry.

#### 6. Retry a failed/cancelled job

```bash
curl -X POST http://localhost:8080/api/v1/jobs/JOB_ID/retry
```

A retry receives a **new job ID** but reuses the previous output directory with `resume=true`, avoiding unnecessary re-extraction of completed pages.

#### 7. Read quality/manifest/errors

```bash
curl http://localhost:8080/api/v1/jobs/JOB_ID/quality-report
curl http://localhost:8080/api/v1/jobs/JOB_ID/manifest
curl http://localhost:8080/api/v1/jobs/JOB_ID/structure
curl http://localhost:8080/api/v1/jobs/JOB_ID/errors
```

Any generated file can be retrieved through the guarded artifact endpoint, for example:

```text
GET /api/v1/jobs/JOB_ID/artifacts/index/documents.jsonl
GET /api/v1/jobs/JOB_ID/artifacts/pages/page_0001.png
GET /api/v1/jobs/JOB_ID/artifacts/assets/BOOK_ID/ASSET.png
```

Path traversal outside the job output directory is blocked.

### Search REST endpoints

After indexing into OpenSearch, the same service exposes REST wrappers useful to an AI Teacher/Agent:

```text
POST /api/v1/search
GET  /api/v1/indexed-books/{book_id}/pages/{page}
GET  /api/v1/indexed-books/{book_id}/questions/{page}/{number}
POST /api/v1/indexed-books/{book_id}/questions/search
GET  /api/v1/indexed-questions/{question_id}/context
GET  /api/v1/indexed-assets/{asset_id}
```

Example lexical search:

```bash
curl -X POST http://localhost:8080/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "قانون نيوتن الثاني",
    "filters": {"book_id":"BOOK_ID"},
    "size": 10
  }'
```

Example question search:

```bash
curl -X POST http://localhost:8080/api/v1/indexed-books/BOOK_ID/questions/search \
  -H 'Content-Type: application/json' \
  -d '{
    "scope":"lesson_end",
    "purpose":"critical_thinking",
    "requires_visual":true,
    "size":100
  }'
```

### REST-related configuration

```env
API_HOST=0.0.0.0
API_PORT=8080
API_DATA_ROOT=./data
API_JOB_DB=./data/jobs.sqlite3
API_WORKER_COUNT=2
API_WORKER_POLL_SECONDS=0.5
API_MAX_UPLOAD_MB=1024
API_CORS_ORIGINS=*
```

`API_WORKER_COUNT` controls how many books can be processed concurrently inside one API process. For expensive VLM deployments, start conservatively (often 1–2) so you do not overwhelm the model server.

### Docker Compose

The included Compose file can start OpenSearch, Dashboards and the REST service:

```bash
docker compose up -d --build
```

By default, the API container expects a VLM on the host at:

```text
http://host.docker.internal:8000/v1
```

Override it with:

```env
DOCKER_VLM_BASE_URL=http://your-vlm-host:8000/v1
```

Persistent book uploads, job state and extraction artifacts are stored in the `book-api-data` Docker volume.

---

## What this version does

Every PDF is processed in two layers:

1. **Page understanding** — detects headings, lessons, text, definitions, theories, laws, examples, questions, activities, tables, images, maps, diagrams, charts and other meaningful page blocks.
2. **Question Intelligence** — every question is normalized to a universal question schema that separates where it appears (`scope`) from how it is answered (`format`), why it is asked (`purpose`), Bloom level, dependencies, and compound subquestions. Arabic and English review/checkpoint headings are recognized, and neighboring lesson/chapter/unit boundaries are used as deterministic evidence.
3. **Universal visual understanding** — every detected visual asset is cropped and sent through a second high-resolution VLM pass. The visual analyzer uses an **open-ended `visual_type`** rather than forcing every image into biology/geography/etc.

A final optional pass **verifies every visual extraction** and automatically retries material errors.

## Core guarantees of the data model

The framework preserves:

- PDF page number and printed textbook page number separately.
- Country, curriculum, education system, grade, subject and semester metadata.
- Unit → chapter → lesson → section hierarchy.
- Original Arabic/English wording (`verbatim_text`).
- Search-normalized wording separately (`normalized_text`).
- Full-page image and exact visual crop paths.
- Page-level bounding box for every detected visual.
- Asset-level bounding boxes for visible labels, objects and regions.
- Field/evidence provenance and confidence for visual claims.
- Verification status for visual assets.
- Question scope: inside lesson, checkpoint, lesson end, chapter end, unit end, exam/review, activity/experiment/reading questions, or open-ended future values.
- Question format independently from scope: multiple choice, true/false, fill blank, calculate, explain, justify, compare, interpret graph/map/table/image, reading comprehension, and open-ended future formats.
- Question purpose, Bloom level, difficulty, compound parent/child structure, and references to figures/tables/maps/passages/equations.

It never intentionally solves textbook questions during ingestion.

---

## Universal Question Intelligence

Every student-facing exercise/problem is normalized to `content_type = "question"`. Legacy question types remain accepted at ingestion for backward compatibility, but the post-processing layer converts them to a consistent structure.

Example:

```json
{
  "question_id": "BOOK-p0038-q004",
  "number": "5",
  "group_title": "أسئلة الدرس",
  "scope": "lesson_end",
  "format": "explain",
  "purpose": "understanding",
  "bloom_level": "understand",
  "difficulty": "medium",
  "stem": "فسر لماذا ...",
  "choices": [],
  "requires_visual": false,
  "requires_table": false,
  "requires_graph": false,
  "requires_map": false,
  "requires_passage": false,
  "requires_equation": false,
  "references": [],
  "children": [],
  "classification_confidence": 0.94,
  "classification_evidence": [
    "group_heading:أسئلة الدرس",
    "scope_from_visible_text:lesson_end"
  ]
}
```

The important separation is:

```text
question_scope   = WHERE the question appears
question_format  = HOW the student answers
question_purpose = WHY the question is asked
Bloom level      = cognitive demand
```

Common scopes include:

```text
inside_lesson
checkpoint
worked_example_followup
section_end
lesson_end
chapter_end
unit_end
book_review
semester_review
final_review
exam
practice_test
previous_exam
activity_question
experiment_question
reading_passage_question
```

Compound questions are preserved hierarchically and **also flattened into independently searchable OpenSearch documents**. A question such as `5 (a) (b) (c)` therefore keeps the parent and exposes each subquestion to filters/search separately.

If the question explicitly references a graph, table, map, figure, passage, or equation, the pipeline records that dependency. When it can conservatively resolve the corresponding visual asset on the same page, it stores the target `asset_id`, allowing the AI Teacher to load the evidence before answering.

Classification uses both VLM-visible evidence and deterministic structure. For example, a question cluster immediately before a new lesson heading can be classified as `lesson_end` even if the VLM did not explicitly provide the scope. Visible headings such as `أسئلة الوحدة`, `تحقق من فهمك`, `Chapter Review`, and `Check your understanding` receive higher confidence than inferred structure.

---

## Universal visual representation

A visual asset can be anything: photograph, map, diagram, table, chart, graph, circuit, geometry figure, chemical structure, painting, historical image, manuscript, timeline, flowchart, screenshot, infographic, symbolic illustration, or a type not anticipated by the code.

Example:

```json
{
  "asset_id": "BOOK-p0045-a003",
  "visual_type": "process_diagram",
  "visual_subtype": "open-ended subtype",
  "summary": "...",
  "visible_text": [],
  "labels": [],
  "entities": [],
  "regions": [],
  "arrows": [],
  "relationships": [],
  "legend": [],
  "axes": [],
  "measurements": [],
  "steps": [],
  "colors_with_meaning": [],
  "symbols": [],
  "equations": [],
  "data_points": [],
  "concepts": [],
  "keywords": [],
  "raw_attributes": {},
  "confidence_by_field": {},
  "overall_confidence": 0.91,
  "verification": {
    "status": "passed",
    "confidence": 0.95,
    "unsupported_claims": [],
    "contradictions": []
  }
}
```

The model is instructed to distinguish **visible evidence** from **context-derived interpretation**. Surrounding text can help explain a visual but cannot be falsely reported as text visible inside the image.

---

## Architecture

```text
PDF textbook
    |
    +--> Render every page at high resolution
    |       |
    |       +--> PDF text layer (when available)
    |       +--> Full page image
    |
    +--> PAGE PASS (VLM)
    |       |
    |       +--> headings / hierarchy changes
    |       +--> definitions / theories / explanations
    |       +--> examples / exercises / questions
    |       +--> activities / experiments / literary text
    |       +--> visual regions + page bbox
    |
    +--> QUESTION INTELLIGENCE PASS
    |       |
    |       +--> scope / group / format / purpose / Bloom
    |       +--> compound parent/child questions
    |       +--> visual/table/map/passage/equation dependencies
    |       +--> neighboring lesson/chapter/unit boundary inference
    |
    +--> VISUAL PASS for EVERY visual region
    |       |
    |       +--> crop exact asset
    |       +--> read Arabic/English visible labels
    |       +--> detect open-ended visual type
    |       +--> objects / regions / symbols
    |       +--> arrows / relationships / steps
    |       +--> legend / axes / units / measurements
    |       +--> colors/patterns with meaning
    |       +--> equations / visible data points
    |
    +--> VERIFICATION PASS
    |       |
    |       +--> adversarially inspect crop
    |       +--> reject hallucinated labels/relations
    |       +--> detect context-as-visible mistakes
    |       +--> retry when necessary
    |
    +--> Hierarchy + provenance + quality
    |
    +--> documents.jsonl
    |
    +--> OpenSearch lexical/BM25 index
    |
    +--> Agentic Search / AI Teacher tools
```

---

## Requirements

- Python 3.11+
- An OpenAI-compatible **vision-language model endpoint**.
- OpenSearch if you want indexing/search.

A Qwen2.5-VL deployment through vLLM is one suitable option, but the code is provider-agnostic as long as the endpoint accepts OpenAI-style image messages and returns JSON.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Windows:

```powershell
.venv\Scripts\activate
```

## VLM configuration

```env
VLM_BASE_URL=http://localhost:8000/v1
VLM_API_KEY=EMPTY
VLM_MODEL=Qwen/Qwen2.5-VL-7B-Instruct
```

The server must expose:

```text
POST /v1/chat/completions
```

and accept `image_url` content in OpenAI-compatible chat messages.

For difficult maps, diagrams and very small labels, increase `RENDER_DPI` and use a stronger/larger VLM when hardware allows.

---

## Start OpenSearch

```bash
docker compose up -d
```

Create/recreate the v3 index:

```bash
python main.py create-index --recreate
```

---

## Ingest an Arabic book

```bash
python main.py ingest ./books/science8.pdf \
  --output ./output/science8 \
  --country "الأردن" \
  --curriculum "المنهاج الوطني الأردني" \
  --grade "الصف الثامن" \
  --subject "العلوم" \
  --semester "الفصل الأول"
```

## Ingest an English book

```bash
python main.py ingest ./books/geography10.pdf \
  --output ./output/geography10 \
  --country "United Kingdom" \
  --curriculum "School Curriculum" \
  --grade "Grade 10" \
  --subject "Geography" \
  --language "en"
```

Metadata options are overrides. When omitted, the VLM tries to detect them from the first pages. For official production books, supplying authoritative metadata from your catalog/database is recommended.

---

## Output

```text
output/book/
├── pages/                    # full rendered pages
├── raw/                      # raw page VLM JSON
├── extracted_pages/          # validated page extractions
├── assets/<book_id>/         # exact visual crops
├── asset_analysis/           # deep structured visual JSON
├── asset_verification/       # visual verifier JSON
├── index/documents.jsonl     # OpenSearch-ready records
├── book_metadata.final.json
├── quality_report.json
├── manifest.json
└── errors.jsonl              # only when failures occur
```

---

## Search Arabic or English

```bash
python main.py search "قانون نيوتن الثاني" --book-id BOOK_ID
```

```bash
python main.py search "water cycle" --book-id BOOK_ID
```

Search is lexical/BM25, not vector RAG. Search fields include lesson/chapter titles, text, concepts, aliases, question groups/references, captions, visual labels, visible visual text, visual concepts and visual summaries. Question scope/format/purpose/Bloom are exact filterable keyword fields.

## Exact page lookup

```bash
python main.py page BOOK_ID 35
```

The query checks both the printed page and PDF page number.

## Exact question lookup

```bash
python main.py question BOOK_ID 35 5
```

## Question Intelligence search

All lesson-end questions:

```bash
python main.py questions BOOK_ID --scope lesson_end
```

All critical-thinking questions in a unit:

```bash
python main.py questions BOOK_ID \
  --unit-title "الوحدة الثانية" \
  --purpose critical_thinking
```

All calculation questions:

```bash
python main.py questions BOOK_ID --format calculate
```

Questions that depend on a visual:

```bash
python main.py questions BOOK_ID --requires-visual
```

Retrieve the question plus resolved referenced assets and neighboring textbook blocks:

```bash
python main.py question-context QUESTION_ID
```

Generic search can also filter by:

```bash
python main.py search "التسارع" --book-id BOOK_ID \
  --question-scope lesson_end \
  --question-format calculate
```

## Visual lookup

All visuals on a page:

```bash
python main.py visuals BOOK_ID --page 52
```

Search visuals by their extracted content:

```bash
python main.py visuals BOOK_ID --query "rainfall legend"
```

Filter an open-ended visual type when you know it:

```bash
python main.py visuals BOOK_ID --visual-type map
```

---

## Recommended Agentic Search tools

Expose these application-level tools to your AI Teacher:

```text
search_book(query, filters)
get_page(book_id, page)
find_question(book_id, page, number)
find_questions(book_id, query?, scope?, format?, purpose?, bloom_level?, ...)
get_question_context(question_id)
find_visuals(book_id, page?, visual_type?, query?)
get_asset(asset_id)
get_lesson(...)
get_previous_block(...)
get_next_block(...)
```

The teacher should retrieve evidence first, re-open the original visual crop when a question depends on the visual, and answer only after it has enough book evidence.

---

## Important production limitation

No OCR/VLM pipeline can truthfully guarantee perfect extraction from **every possible textbook** or guarantee student grades. This framework is designed to make errors detectable rather than hidden: original page/crop preservation, exact provenance, per-asset verification, retry, quality scoring and a `recommended_for_live_index` gate are included so low-confidence books can be reviewed before students rely on them.

For production, keep a **staging index** and promote a book to the live student index only after its quality report passes your thresholds.

---

## Run tests

```bash
pytest -q
```

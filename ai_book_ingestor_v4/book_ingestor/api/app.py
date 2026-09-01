from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from ..config import settings
from .job_store import JobStore
from .models import ExtractionJobRequest, QuestionSearchRequest, SearchRequest
from .worker import ExtractionWorkerPool


DATA_ROOT = Path(settings.api_data_root).resolve()
BOOKS_ROOT = DATA_ROOT / "books"
JOBS_ROOT = DATA_ROOT / "jobs"
BOOKS_ROOT.mkdir(parents=True, exist_ok=True)
JOBS_ROOT.mkdir(parents=True, exist_ok=True)

store = JobStore(settings.api_job_db)
workers = ExtractionWorkerPool(store)

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def _public_book(book: dict[str, Any]) -> dict[str, Any]:
    return {
        "resource_id": book["resource_id"],
        "filename": book["original_filename"],
        "size_bytes": book["size_bytes"],
        "sha256": book["sha256"],
        "metadata": book.get("metadata") or {},
        "created_at": book["created_at"],
    }


def _public_job(job: dict[str, Any]) -> dict[str, Any]:
    result = dict(job.get("result") or {}) if isinstance(job.get("result"), dict) else job.get("result")
    return {
        "job_id": job["job_id"],
        "book_resource_id": job["book_resource_id"],
        "status": job["status"],
        "progress": job["progress"],
        "stage": job.get("stage"),
        "message": job.get("message"),
        "current_page": job.get("current_page"),
        "total_pages": job.get("total_pages"),
        "start_page": job["start_page"],
        "end_page": job.get("end_page"),
        "resume": job["resume"],
        "index_to_opensearch": job["index_to_opensearch"],
        "recreate_index": job["recreate_index"],
        "metadata_overrides": job.get("metadata_overrides") or {},
        "book_id": job.get("book_id"),
        "extracted_records": job.get("extracted_records"),
        "visual_assets": job.get("visual_assets"),
        "indexed_records": job.get("indexed_records"),
        "result": result,
        "error": job.get("error"),
        "retry_of": job.get("retry_of"),
        "created_at": job["created_at"],
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "updated_at": job["updated_at"],
        "links": {
            "self": f"/api/v1/jobs/{job['job_id']}",
            "events": f"/api/v1/jobs/{job['job_id']}/events",
            "event_stream": f"/api/v1/jobs/{job['job_id']}/events/stream",
            "quality": f"/api/v1/jobs/{job['job_id']}/quality-report",
            "manifest": f"/api/v1/jobs/{job['job_id']}/manifest",
            "errors": f"/api/v1/jobs/{job['job_id']}/errors",
        },
    }


def _load_json_artifact(job_id: str, filename: str) -> dict[str, Any]:
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    path = Path(job["output_dir"]) / filename
    if not path.exists():
        raise HTTPException(404, f"Artifact not available yet: {filename}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(500, f"Unable to read artifact: {exc}") from exc


def _search_service():
    from ..opensearch_index import create_client
    from ..search import BookSearchService

    return BookSearchService(create_client(), settings.opensearch_index)


@asynccontextmanager
async def lifespan(app: FastAPI):
    workers.start()
    yield
    workers.stop()


app = FastAPI(
    title="Universal Textbook Ingestion API",
    version="4.0.0",
    description=(
        "Persistent background extraction API for Arabic, English and mixed-language textbooks. "
        "Tracks page extraction, question intelligence, universal visual analysis, quality validation and OpenSearch indexing."
    ),
    lifespan=lifespan,
)

origins = [x.strip() for x in settings.api_cors_origins.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ai-book-ingestor",
        "version": "4.0.0",
        "workers": settings.api_worker_count,
        "opensearch_index": settings.opensearch_index,
    }


@app.post("/api/v1/books", status_code=201)
async def upload_book(
    file: UploadFile = File(..., description="Arabic, English, or mixed-language textbook PDF"),
    metadata: str = Form("{}", description="Optional JSON: country/curriculum/grade/subject/semester/etc."),
):
    filename = Path(file.filename or "book.pdf").name
    if not filename.casefold().endswith(".pdf"):
        raise HTTPException(415, "Only PDF textbook uploads are accepted")
    try:
        metadata_obj = json.loads(metadata or "{}")
        if not isinstance(metadata_obj, dict):
            raise ValueError("metadata must be a JSON object")
    except Exception as exc:
        raise HTTPException(422, f"Invalid metadata JSON: {exc}") from exc

    resource_id = uuid.uuid4().hex
    book_dir = BOOKS_ROOT / resource_id
    book_dir.mkdir(parents=True, exist_ok=False)
    destination = book_dir / "source.pdf"
    h = hashlib.sha256()
    total = 0
    limit = settings.api_max_upload_mb * 1024 * 1024
    try:
        with destination.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > limit:
                    raise HTTPException(413, f"Upload exceeds {settings.api_max_upload_mb} MB limit")
                h.update(chunk)
                out.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        try:
            book_dir.rmdir()
        except OSError:
            pass
        raise
    finally:
        await file.close()

    # Basic PDF signature guard before a worker spends time on the file.
    with destination.open("rb") as check_file:
        signature = check_file.read(5)
    if signature != b"%PDF-":
        destination.unlink(missing_ok=True)
        raise HTTPException(415, "Uploaded file does not appear to be a valid PDF")

    book = store.create_book(
        resource_id=resource_id,
        original_filename=filename,
        stored_path=str(destination),
        size_bytes=total,
        sha256=h.hexdigest(),
        metadata=metadata_obj,
    )
    return _public_book(book)


@app.get("/api/v1/books")
def list_books(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    return {"items": [_public_book(x) for x in store.list_books(limit=limit, offset=offset)]}


@app.get("/api/v1/books/{resource_id}")
def get_book(resource_id: str):
    book = store.get_book(resource_id)
    if not book:
        raise HTTPException(404, "Book not found")
    return _public_book(book)


@app.post("/api/v1/books/{resource_id}/extraction-jobs", status_code=202)
def create_extraction_job(resource_id: str, request: ExtractionJobRequest):
    book = store.get_book(resource_id)
    if not book:
        raise HTTPException(404, "Book not found")
    job_id = uuid.uuid4().hex
    output_dir = JOBS_ROOT / job_id
    output_dir.mkdir(parents=True, exist_ok=False)
    job = store.create_job(
        job_id=job_id,
        book_resource_id=resource_id,
        output_dir=str(output_dir),
        start_page=request.start_page,
        end_page=request.end_page,
        resume=request.resume,
        index_to_opensearch=request.index_to_opensearch,
        recreate_index=request.recreate_index,
        metadata_overrides=request.metadata_overrides,
    )
    return _public_job(job)


@app.get("/api/v1/jobs")
def list_jobs(
    status: str | None = None,
    book_resource_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    items = store.list_jobs(
        status=status, book_resource_id=book_resource_id, limit=limit, offset=offset
    )
    return {"items": [_public_job(x) for x in items]}


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str):
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return _public_job(job)


@app.post("/api/v1/jobs/{job_id}/cancel", status_code=202)
def cancel_job(job_id: str):
    job = store.request_cancel(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] in {"completed", "failed"}:
        raise HTTPException(409, f"Cannot cancel a {job['status']} job")
    return _public_job(job)


@app.post("/api/v1/jobs/{job_id}/retry", status_code=202)
def retry_job(job_id: str):
    old = store.get_job(job_id)
    if not old:
        raise HTTPException(404, "Job not found")
    if old["status"] not in {"failed", "cancelled"}:
        raise HTTPException(409, "Only failed or cancelled jobs can be retried")
    new_id = uuid.uuid4().hex
    # Reuse the old output directory so resume=True can continue from extracted page artifacts.
    job = store.create_job(
        job_id=new_id,
        book_resource_id=old["book_resource_id"],
        output_dir=old["output_dir"],
        start_page=old["start_page"],
        end_page=old.get("end_page"),
        resume=True,
        index_to_opensearch=old["index_to_opensearch"],
        recreate_index=False,
        metadata_overrides=old.get("metadata_overrides") or {},
        retry_of=job_id,
    )
    return _public_job(job)


@app.get("/api/v1/jobs/{job_id}/events")
def get_job_events(
    job_id: str,
    after_id: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
):
    if not store.get_job(job_id):
        raise HTTPException(404, "Job not found")
    return {"items": store.list_events(job_id, after_id=after_id, limit=limit)}


@app.get("/api/v1/jobs/{job_id}/events/stream")
async def stream_job_events(job_id: str, request: Request, after_id: int = Query(0, ge=0)):
    if not store.get_job(job_id):
        raise HTTPException(404, "Job not found")

    async def generator():
        cursor = after_id
        while True:
            if await request.is_disconnected():
                return
            events = store.list_events(job_id, after_id=cursor, limit=200)
            for event in events:
                cursor = max(cursor, int(event["id"]))
                payload = json.dumps(event, ensure_ascii=False, default=str)
                yield f"id: {event['id']}\nevent: {event['event_type']}\ndata: {payload}\n\n"
            job = store.get_job(job_id)
            if job and job["status"] in TERMINAL_STATUSES and not events:
                yield f"event: end\ndata: {json.dumps({'status': job['status']})}\n\n"
                return
            if not events:
                yield ": keep-alive\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.get("/api/v1/jobs/{job_id}/quality-report")
def quality_report(job_id: str):
    return _load_json_artifact(job_id, "quality_report.json")


@app.get("/api/v1/jobs/{job_id}/manifest")
def manifest(job_id: str):
    return _load_json_artifact(job_id, "manifest.json")


@app.get("/api/v1/jobs/{job_id}/structure")
def structure(job_id: str):
    return _load_json_artifact(job_id, "structure.json")


@app.get("/api/v1/jobs/{job_id}/errors")
def job_errors(job_id: str):
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    path = Path(job["output_dir"]) / "errors.jsonl"
    if not path.exists():
        return {"items": []}
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                items.append(json.loads(line))
            except Exception:
                items.append({"raw": line})
    return {"items": items}


@app.get("/api/v1/jobs/{job_id}/artifacts/{relative_path:path}")
def get_artifact(job_id: str, relative_path: str):
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    root = Path(job["output_dir"]).resolve()
    requested = (root / relative_path).resolve()
    if root != requested and root not in requested.parents:
        raise HTTPException(400, "Invalid artifact path")
    if not requested.exists() or not requested.is_file():
        raise HTTPException(404, "Artifact not found")
    return FileResponse(requested)


@app.post("/api/v1/search")
def search_content(request: SearchRequest):
    try:
        items = _search_service().search(request.query, request.filters, size=request.size)
        return {"items": items}
    except Exception as exc:
        raise HTTPException(503, f"OpenSearch query failed: {exc}") from exc


@app.get("/api/v1/indexed-books/{book_id}/pages/{page}")
def indexed_page(book_id: str, page: str):
    try:
        return {"items": _search_service().exact_page(book_id, page)}
    except Exception as exc:
        raise HTTPException(503, f"OpenSearch query failed: {exc}") from exc


@app.get("/api/v1/indexed-books/{book_id}/questions/{page}/{number}")
def indexed_question(book_id: str, page: str, number: str):
    try:
        return {"items": _search_service().find_question(book_id, page, number)}
    except Exception as exc:
        raise HTTPException(503, f"OpenSearch query failed: {exc}") from exc


@app.post("/api/v1/indexed-books/{book_id}/questions/search")
def indexed_question_search(book_id: str, request: QuestionSearchRequest):
    try:
        items = _search_service().find_questions(
            book_id=book_id,
            query=request.query,
            scope=request.scope,
            question_format=request.question_format,
            purpose=request.purpose,
            bloom_level=request.bloom_level,
            difficulty=request.difficulty,
            lesson_title=request.lesson_title,
            chapter_title=request.chapter_title,
            unit_title=request.unit_title,
            requires_visual=request.requires_visual,
            size=request.size,
        )
        return {"items": items}
    except Exception as exc:
        raise HTTPException(503, f"OpenSearch query failed: {exc}") from exc


@app.get("/api/v1/indexed-questions/{question_id}/context")
def indexed_question_context(question_id: str, radius: int = Query(2, ge=0, le=10)):
    try:
        result = _search_service().get_question_context(question_id, radius=radius)
        if result is None:
            raise HTTPException(404, "Question not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, f"OpenSearch query failed: {exc}") from exc


@app.get("/api/v1/indexed-assets/{asset_id}")
def indexed_asset(asset_id: str):
    try:
        result = _search_service().get_asset(asset_id)
        if result is None:
            raise HTTPException(404, "Asset not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, f"OpenSearch query failed: {exc}") from exc

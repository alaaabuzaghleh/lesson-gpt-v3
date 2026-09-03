from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from extractor_lessons_gpt.api.deps import require_admin, require_admin_sse
from extractor_lessons_gpt.api.local_job_store import LocalFileJobStore
from extractor_lessons_gpt.api.models import ExtractionJobRequest
from extractor_lessons_gpt.api.remote_catalog import remote_catalog_metadata
from extractor_lessons_gpt.api.remote_client import RemoteApiError, RemoteIngestClient, remote_api_configured
from extractor_lessons_gpt.api.worker import ExtractionWorkerPool
from extractor_lessons_gpt.config import settings


DATA_ROOT = Path(settings.api_data_root).resolve()
BOOKS_ROOT = DATA_ROOT / "books"
JOBS_ROOT = DATA_ROOT / "jobs"
BOOKS_ROOT.mkdir(parents=True, exist_ok=True)
JOBS_ROOT.mkdir(parents=True, exist_ok=True)

store = LocalFileJobStore(DATA_ROOT)
workers = ExtractionWorkerPool(store)

TERMINAL_STATUSES = {"completed", "failed", "cancelled", "paused"}


def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


def _remote_client_from_request(request: Request) -> RemoteIngestClient:
    token = _bearer_token(request)
    if not token:
        raise HTTPException(401, "Authentication required for remote operations")
    return RemoteIngestClient(token)


def _public_book(book: dict[str, Any]) -> dict[str, Any]:
    return {
        "resource_id": book["resource_id"],
        "subject_id": book.get("subject_id"),
        "catalog_path": book.get("catalog_path"),
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
        "extractor_backend": job.get("extractor_backend") or "local",
        "sync_to_remote": bool(job.get("sync_to_remote")),
        "remote_sync_status": job.get("remote_sync_status"),
        "remote_synced_records": job.get("remote_synced_records"),
        "metadata_overrides": job.get("metadata_overrides") or {},
        "book_id": job.get("book_id"),
        "extracted_records": job.get("extracted_records"),
        "visual_assets": job.get("visual_assets"),
        "indexed_records": job.get("indexed_records"),
        "result": result,
        "error": job.get("error"),
        "traceback": job.get("traceback"),
        "retry_of": job.get("retry_of"),
        "checkpoint": job.get("checkpoint"),
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not remote_api_configured():
        raise RuntimeError(
            "REMOTE_API_URL is required. The local extractor publishes pages through "
            "remote-lessons-gpt secure APIs only (no direct PostgreSQL or OpenSearch access)."
        )
    store.initialize()
    workers.start()
    yield
    workers.stop()
    store.close()


app = FastAPI(
    title="extractorLessonsGPT API",
    version="2.0.0",
    description=(
        "Local PDF extraction API (Ollama/Codex). Persists books and jobs on disk; "
        "publishes extracted pages to remoteLessonsGPT via secure HTTP ingest only."
    ),
    lifespan=lifespan,
)

origins = [x.strip() for x in settings.api_cors_origins.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "extractor-lessons-gpt",
        "version": "2.0.0",
        "workers": settings.api_worker_count,
        "storage": "local-files",
        "remote_api_configured": remote_api_configured(),
        "remote_api_url": settings.remote_api_url or None,
    }


@app.post("/api/v1/books", status_code=201)
async def upload_book(
    request: Request,
    _: Annotated[dict, Depends(require_admin)],
    file: UploadFile = File(...),
    subject_id: str = Form(...),
    metadata: str = Form("{}"),
):
    try:
        _remote_client_from_request(request).request_json("GET", f"/api/v1/catalog/subjects/{subject_id}")
    except RemoteApiError as exc:
        raise HTTPException(404, f"Subject not found on remote catalog: {exc}") from exc

    filename = Path(file.filename or "book.pdf").name
    if not filename.casefold().endswith(".pdf"):
        raise HTTPException(415, "Only PDF textbook uploads are accepted")
    try:
        metadata_obj = json.loads(metadata or "{}")
        if not isinstance(metadata_obj, dict):
            raise ValueError("metadata must be a JSON object")
    except Exception as exc:
        raise HTTPException(422, f"Invalid metadata JSON: {exc}") from exc

    try:
        metadata_obj.update(remote_catalog_metadata(_remote_client_from_request(request), subject_id))
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc

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
        subject_id=subject_id,
        created_by=None,
    )
    try:
        _remote_client_from_request(request).register_book(
            resource_id=resource_id,
            subject_id=subject_id,
            original_filename=filename,
            size_bytes=total,
            sha256=h.hexdigest(),
            metadata=metadata_obj,
        )
    except RemoteApiError as exc:
        store.delete_book(resource_id)
        shutil.rmtree(book_dir, ignore_errors=True)
        raise HTTPException(502, f"Failed to register book on remote server: {exc}") from exc
    return _public_book(book)


@app.get("/api/v1/books")
def list_books(
    _: Annotated[dict, Depends(require_admin)],
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    subject_id: str | None = None,
    grade_id: str | None = None,
    country_id: str | None = None,
):
    items = store.list_books(limit=limit, offset=offset, subject_id=subject_id, grade_id=grade_id, country_id=country_id)
    return {"items": [_public_book(x) for x in items]}


@app.get("/api/v1/books/{resource_id}")
def get_book(resource_id: str, _: Annotated[dict, Depends(require_admin)]):
    book = store.get_book(resource_id)
    if not book:
        raise HTTPException(404, "Book not found")
    return _public_book(book)


@app.delete("/api/v1/books/{resource_id}")
def delete_book(resource_id: str, _: Annotated[dict, Depends(require_admin)]):
    result = store.delete_book(resource_id)
    if not result:
        raise HTTPException(404, "Book not found")
    book = result["book"]
    jobs = result["jobs"]
    stored = Path(str(book.get("stored_path") or BOOKS_ROOT / resource_id / "source.pdf"))
    shutil.rmtree(stored.parent, ignore_errors=True)
    for job in jobs:
        output_dir = job.get("output_dir")
        if output_dir:
            shutil.rmtree(output_dir, ignore_errors=True)
    return {"deleted": True, "deleted_jobs": len(jobs)}


@app.post("/api/v1/books/{resource_id}/extraction-jobs", status_code=202)
def create_extraction_job(
    resource_id: str,
    request: ExtractionJobRequest,
    http_request: Request,
    _: Annotated[dict, Depends(require_admin)],
):
    book = store.get_book(resource_id)
    if not book:
        raise HTTPException(404, "Book not found")

    remote_token = _bearer_token(http_request)
    if not remote_token:
        raise HTTPException(401, "Remote ingest requires a valid login token")

    job_id = uuid.uuid4().hex
    output_dir = JOBS_ROOT / job_id
    output_dir.mkdir(parents=True, exist_ok=False)
    metadata = dict(request.metadata_overrides or {})
    metadata["language_hint"] = request.language_hint

    from remote_lessons_gpt.schemas import BookMetadata
    from extractor_lessons_gpt.opensearch_indexer import book_id_for_pdf

    book_metadata = BookMetadata.model_validate(dict(book.get("metadata") or {}))
    book_metadata_data = book_metadata.model_dump()
    book_metadata_data.update(metadata)
    book_metadata = BookMetadata.model_validate(book_metadata_data)
    book_id = book_id_for_pdf(Path(book["stored_path"]), book_metadata)
    try:
        RemoteIngestClient(remote_token).create_job(
            job_id=job_id,
            book_resource_id=resource_id,
            book_id=book_id,
            start_page=request.start_page,
            end_page=request.end_page,
            extractor_backend=request.extractor_backend,
            metadata=metadata,
        )
    except RemoteApiError as exc:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise HTTPException(502, f"Failed to create remote ingestion job: {exc}") from exc

    job = store.create_job(
        job_id=job_id,
        book_resource_id=resource_id,
        output_dir=str(output_dir),
        start_page=request.start_page,
        end_page=request.end_page,
        resume=request.resume,
        index_to_opensearch=False,
        recreate_index=False,
        metadata_overrides=metadata,
        extractor_backend=request.extractor_backend,
        sync_to_remote=True,
        remote_job_id=job_id,
        remote_auth_token=remote_token,
    )
    return _public_job(job)


@app.get("/api/v1/jobs")
def list_jobs(
    _: Annotated[dict, Depends(require_admin)],
    status: str | None = None,
    book_resource_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    items = store.list_jobs(status=status, book_resource_id=book_resource_id, limit=limit, offset=offset)
    return {"items": [_public_job(x) for x in items]}


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str, _: Annotated[dict, Depends(require_admin)]):
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return _public_job(job)


@app.post("/api/v1/jobs/{job_id}/stop", status_code=202)
def stop_job(job_id: str, _: Annotated[dict, Depends(require_admin)]):
    job = store.request_stop(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] in {"completed", "failed"}:
        raise HTTPException(409, f"Cannot stop a {job['status']} job")
    return _public_job(job)


@app.post("/api/v1/jobs/{job_id}/cancel", status_code=202)
def cancel_job(job_id: str, _: Annotated[dict, Depends(require_admin)]):
    return stop_job(job_id, _)


@app.post("/api/v1/jobs/{job_id}/resume", status_code=202)
def resume_job(job_id: str, _: Annotated[dict, Depends(require_admin)]):
    old = store.get_job(job_id)
    if not old:
        raise HTTPException(404, "Job not found")
    if old["status"] not in {"paused", "failed", "cancelled"}:
        raise HTTPException(409, "Only paused, failed, or cancelled jobs can be resumed")
    job = store.resume_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return _public_job(job)


@app.post("/api/v1/jobs/{job_id}/retry", status_code=202)
def retry_job(job_id: str, _: Annotated[dict, Depends(require_admin)]):
    return resume_job(job_id, _)


@app.delete("/api/v1/jobs/{job_id}")
def delete_job(job_id: str, _: Annotated[dict, Depends(require_admin)]):
    if not store.get_job(job_id):
        raise HTTPException(404, "Job not found")
    result = store.delete_job(job_id)
    if not result:
        raise HTTPException(404, "Job not found")
    if result.get("error") == "job_active":
        raise HTTPException(409, "Stop the job before deleting it")
    deleted_job = result["job"]
    output_dir = deleted_job.get("output_dir")
    if output_dir:
        shutil.rmtree(output_dir, ignore_errors=True)
    return {"deleted": True, "job_id": job_id}


@app.get("/api/v1/jobs/{job_id}/events")
def get_job_events(
    job_id: str,
    _: Annotated[dict, Depends(require_admin)],
    after_id: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
):
    if not store.get_job(job_id):
        raise HTTPException(404, "Job not found")
    return {"items": store.list_events(job_id, after_id=after_id, limit=limit)}


@app.get("/api/v1/jobs/{job_id}/events/stream")
async def stream_job_events(
    job_id: str,
    request: Request,
    _: Annotated[dict, Depends(require_admin_sse)],
    after_id: int = Query(0, ge=0),
):
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
def quality_report(job_id: str, _: Annotated[dict, Depends(require_admin)]):
    return _load_json_artifact(job_id, "quality_report.json")


@app.get("/api/v1/jobs/{job_id}/manifest")
def manifest(job_id: str, _: Annotated[dict, Depends(require_admin)]):
    return _load_json_artifact(job_id, "manifest.json")


@app.get("/api/v1/jobs/{job_id}/structure")
def structure(job_id: str, _: Annotated[dict, Depends(require_admin)]):
    return _load_json_artifact(job_id, "structure.json")


@app.get("/api/v1/jobs/{job_id}/errors")
def job_errors(job_id: str, _: Annotated[dict, Depends(require_admin)]):
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    items: list[dict[str, Any]] = []
    if job.get("error"):
        items.append({
            "source": "job",
            "stage": job.get("stage") or "failed",
            "error": job["error"],
            "message": job.get("message"),
            "traceback": job.get("traceback"),
        })
    path = Path(job["output_dir"]) / "errors.jsonl"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    items.append(json.loads(line))
                except Exception:
                    items.append({"raw": line})
    return {"items": items}


@app.get("/api/v1/jobs/{job_id}/artifacts/{relative_path:path}")
def get_artifact(job_id: str, relative_path: str, _: Annotated[dict, Depends(require_admin)]):
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

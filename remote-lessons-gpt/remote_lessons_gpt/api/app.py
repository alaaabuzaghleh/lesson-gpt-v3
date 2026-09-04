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

from ..config import settings
from .auth_utils import ADMIN_ROLES, create_access_token, decode_access_token, verify_password
from .catalog_seo import CATALOG_ENTITY_TYPES, CatalogDuplicateError, default_hero_file
from .deps import require_admin, require_admin_sse, require_super_admin
from .job_store import JobStore
from .models import (
    CreateAdminRequest,
    CreateCountryRequest,
    CreateEducationSystemRequest,
    CreateGradeRequest,
    CreateSubjectRequest,
    UpdateCatalogItemRequest,
    ExtractionJobRequest,
    LoginRequest,
    QuestionSearchRequest,
    SearchRequest,
)
from .worker import ExtractionWorkerPool
from .ingest_routes import router as ingest_router


DATA_ROOT = Path(settings.api_data_root).resolve()
BOOKS_ROOT = DATA_ROOT / "books"
JOBS_ROOT = DATA_ROOT / "jobs"
HERO_ROOT = DATA_ROOT / "catalog" / "heroes"
BOOKS_ROOT.mkdir(parents=True, exist_ok=True)
JOBS_ROOT.mkdir(parents=True, exist_ok=True)
HERO_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_HERO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".svg"}

store = JobStore(settings.database_url)
workers = ExtractionWorkerPool(store)

TERMINAL_STATUSES = {"completed", "failed", "cancelled", "paused"}


def _catalog_entity_exists(entity_type: str, entity_id: str) -> bool:
    getters = {
        "country": store.get_country,
        "system": store.get_education_system,
        "grade": store.get_grade,
        "subject": store.get_subject,
    }
    getter = getters.get(entity_type)
    return bool(getter and getter(entity_id))


def _hero_media_type(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }.get(ext, "application/octet-stream")


def _catalog_write(action):
    try:
        return action()
    except CatalogDuplicateError as exc:
        raise HTTPException(409, str(exc)) from exc


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


def _catalog_metadata(subject_id: str) -> dict[str, Any]:
    path = store.get_subject_path(subject_id)
    if not path:
        return {}
    return {
        "country": path.get("country_name"),
        "country_id": path.get("country_id"),
        "country_code": path.get("country_code"),
        "education_system": path.get("education_system_name"),
        "education_system_id": path.get("education_system_id"),
        "grade": path.get("grade_name"),
        "grade_id": path.get("grade_id"),
        "subject": path.get("subject_name"),
        "subject_id": path.get("subject_id"),
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
    store.initialize()
    workers.start()
    yield
    workers.stop()
    store.close()


app = FastAPI(
    title="remoteLessonsGPT API",
    version="4.1.0",
    description=(
        "Production API for Lessons GPT: auth, catalog, secure ingest, PostgreSQL, and OpenSearch."
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

app.include_router(ingest_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "remote-lessons-gpt",
        "version": "4.1.0",
        "workers": settings.api_worker_count,
        "opensearch_index": settings.opensearch_index,
        "database": "postgresql",
    }


# --- Auth ---

@app.post("/api/v1/auth/login")
def login(body: LoginRequest):
    user = store.get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(403, "Only admin users can access the admin panel")
    if not user.get("is_active", True):
        raise HTTPException(403, "Account is disabled")
    token = create_access_token({"sub": user["id"], "role": user["role"], "email": user["email"]})
    public_user = store.get_user(user["id"])
    return {"access_token": token, "token_type": "bearer", "user": public_user}


@app.get("/api/v1/auth/me")
def auth_me(user: Annotated[dict, Depends(require_admin)]):
    return user


# --- Admin users (super_admin only) ---

@app.get("/api/v1/admin/users")
def list_admin_users(_: Annotated[dict, Depends(require_super_admin)]):
    return {"items": store.list_users(roles=["admin", "super_admin"])}


@app.post("/api/v1/admin/users", status_code=201)
def create_admin_user(body: CreateAdminRequest, current: Annotated[dict, Depends(require_super_admin)]):
    if store.get_user_by_email(body.email):
        raise HTTPException(409, "Email already registered")
    user = store.create_user(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        role="admin",
        created_by=current["id"],
    )
    return user


# --- Catalog hierarchy ---

@app.get("/api/v1/catalog/tree")
def catalog_tree(_: Annotated[dict, Depends(require_admin)]):
    return {"items": store.get_catalog_tree()}


@app.get("/api/v1/public/catalog/tree")
def public_catalog_tree():
    return {"items": store.get_catalog_tree()}


@app.get("/api/v1/catalog/hero/{entity_type}/{entity_id}")
def get_catalog_hero(entity_type: str, entity_id: str):
    if entity_type not in CATALOG_ENTITY_TYPES:
        raise HTTPException(404, "Unknown catalog entity type")
    if not _catalog_entity_exists(entity_type, entity_id):
        raise HTTPException(404, "Catalog item not found")
    custom_path = store.get_catalog_hero_path(entity_type, entity_id)
    if custom_path:
        hero_file = Path(custom_path)
        if hero_file.is_file():
            return FileResponse(hero_file, media_type=_hero_media_type(hero_file))
    default_file = default_hero_file(entity_type)
    return FileResponse(default_file, media_type="image/svg+xml")


@app.post("/api/v1/catalog/{entity_type}/{entity_id}/hero")
async def upload_catalog_hero(
    entity_type: str,
    entity_id: str,
    _: Annotated[dict, Depends(require_admin)],
    file: UploadFile = File(...),
):
    if entity_type not in CATALOG_ENTITY_TYPES:
        raise HTTPException(404, "Unknown catalog entity type")
    if not _catalog_entity_exists(entity_type, entity_id):
        raise HTTPException(404, "Catalog item not found")

    filename = Path(file.filename or "hero.jpg").name
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_HERO_EXTENSIONS:
        raise HTTPException(415, "Hero image must be JPG, PNG, WebP, or SVG")

    entity_dir = HERO_ROOT / entity_type
    entity_dir.mkdir(parents=True, exist_ok=True)
    destination = entity_dir / f"{entity_id}{ext}"

    limit = 10 * 1024 * 1024
    total = 0
    try:
        with destination.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > limit:
                    raise HTTPException(413, "Hero image exceeds 10 MB limit")
                out.write(chunk)
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(500, f"Failed to save hero image: {exc}") from exc

    for other_ext in ALLOWED_HERO_EXTENSIONS:
        if other_ext != ext:
            (entity_dir / f"{entity_id}{other_ext}").unlink(missing_ok=True)

    updated = store.set_catalog_hero_path(entity_type, entity_id, str(destination))
    if not updated:
        destination.unlink(missing_ok=True)
        raise HTTPException(404, "Catalog item not found")
    return updated


@app.delete("/api/v1/catalog/{entity_type}/{entity_id}/hero")
def delete_catalog_hero(
    entity_type: str,
    entity_id: str,
    _: Annotated[dict, Depends(require_admin)],
):
    if entity_type not in CATALOG_ENTITY_TYPES:
        raise HTTPException(404, "Unknown catalog entity type")
    custom_path = store.get_catalog_hero_path(entity_type, entity_id)
    if custom_path:
        Path(custom_path).unlink(missing_ok=True)
    updated = store.set_catalog_hero_path(entity_type, entity_id, None)
    if not updated:
        raise HTTPException(404, "Catalog item not found")
    return updated


@app.get("/api/v1/catalog/countries")
def list_countries(_: Annotated[dict, Depends(require_admin)]):
    return {"items": store.list_countries()}


@app.get("/api/v1/catalog/countries/{country_id}")
def get_country(country_id: str, _: Annotated[dict, Depends(require_admin)]):
    country = store.get_country(country_id)
    if not country:
        raise HTTPException(404, "Country not found")
    return country


@app.post("/api/v1/catalog/countries", status_code=201)
def create_country(body: CreateCountryRequest, _: Annotated[dict, Depends(require_admin)]):
    return _catalog_write(
        lambda: store.create_country(
            name=body.name,
            name_ar=body.name_ar,
            code=body.code,
            seo=body.seo_payload(),
        )
    )


@app.patch("/api/v1/catalog/countries/{country_id}")
def update_country(country_id: str, body: UpdateCatalogItemRequest, _: Annotated[dict, Depends(require_admin)]):
    if not body.has_catalog_updates():
        raise HTTPException(422, "No fields to update")
    updated = _catalog_write(
        lambda: store.update_country(
            country_id,
            name=body.name,
            name_ar=body.name_ar,
            code=body.code,
            seo=body.seo_updates(),
        )
    )
    if not updated:
        raise HTTPException(404, "Country not found")
    return updated


@app.delete("/api/v1/catalog/countries/{country_id}", status_code=204)
def delete_country(country_id: str, _: Annotated[dict, Depends(require_admin)]):
    if not store.deactivate_country(country_id):
        raise HTTPException(404, "Country not found")


@app.get("/api/v1/catalog/education-systems")
def list_education_systems(
    _: Annotated[dict, Depends(require_admin)],
    country_id: str | None = None,
):
    return {"items": store.list_education_systems(country_id=country_id)}


@app.get("/api/v1/catalog/education-systems/{system_id}")
def get_education_system(system_id: str, _: Annotated[dict, Depends(require_admin)]):
    system = store.get_education_system(system_id)
    if not system:
        raise HTTPException(404, "Education system not found")
    return system


@app.post("/api/v1/catalog/education-systems", status_code=201)
def create_education_system(body: CreateEducationSystemRequest, _: Annotated[dict, Depends(require_admin)]):
    if not store.get_country(body.country_id):
        raise HTTPException(404, "Country not found")
    return _catalog_write(
        lambda: store.create_education_system(
            country_id=body.country_id,
            name=body.name,
            name_ar=body.name_ar,
            seo=body.seo_payload(),
        )
    )


@app.patch("/api/v1/catalog/education-systems/{system_id}")
def update_education_system(
    system_id: str, body: UpdateCatalogItemRequest, _: Annotated[dict, Depends(require_admin)]
):
    if not body.has_catalog_updates():
        raise HTTPException(422, "No fields to update")
    updated = _catalog_write(
        lambda: store.update_education_system(
            system_id,
            name=body.name,
            name_ar=body.name_ar,
            seo=body.seo_updates(),
        )
    )
    if not updated:
        raise HTTPException(404, "Education system not found")
    return updated


@app.delete("/api/v1/catalog/education-systems/{system_id}", status_code=204)
def delete_education_system(system_id: str, _: Annotated[dict, Depends(require_admin)]):
    if not store.deactivate_education_system(system_id):
        raise HTTPException(404, "Education system not found")


@app.get("/api/v1/catalog/grades")
def list_grades(
    _: Annotated[dict, Depends(require_admin)],
    education_system_id: str | None = None,
):
    return {"items": store.list_grades(education_system_id=education_system_id)}


@app.get("/api/v1/catalog/grades/{grade_id}")
def get_grade(grade_id: str, _: Annotated[dict, Depends(require_admin)]):
    grade = store.get_grade(grade_id)
    if not grade:
        raise HTTPException(404, "Grade not found")
    return grade


@app.post("/api/v1/catalog/grades", status_code=201)
def create_grade(body: CreateGradeRequest, _: Annotated[dict, Depends(require_admin)]):
    if not store.get_education_system(body.education_system_id):
        raise HTTPException(404, "Education system not found")
    return _catalog_write(
        lambda: store.create_grade(
            education_system_id=body.education_system_id,
            name=body.name,
            name_ar=body.name_ar,
            sort_order=body.sort_order,
            seo=body.seo_payload(),
        )
    )


@app.patch("/api/v1/catalog/grades/{grade_id}")
def update_grade(grade_id: str, body: UpdateCatalogItemRequest, _: Annotated[dict, Depends(require_admin)]):
    if not body.has_catalog_updates():
        raise HTTPException(422, "No fields to update")
    updated = _catalog_write(
        lambda: store.update_grade(
            grade_id,
            name=body.name,
            name_ar=body.name_ar,
            sort_order=body.sort_order,
            seo=body.seo_updates(),
        )
    )
    if not updated:
        raise HTTPException(404, "Grade not found")
    return updated


@app.delete("/api/v1/catalog/grades/{grade_id}", status_code=204)
def delete_grade(grade_id: str, _: Annotated[dict, Depends(require_admin)]):
    if not store.deactivate_grade(grade_id):
        raise HTTPException(404, "Grade not found")


@app.get("/api/v1/catalog/subjects")
def list_subjects(_: Annotated[dict, Depends(require_admin)], grade_id: str | None = None):
    return {"items": store.list_subjects(grade_id=grade_id)}


@app.get("/api/v1/catalog/subjects/{subject_id}")
def get_subject(subject_id: str, _: Annotated[dict, Depends(require_admin)]):
    subject = store.get_subject(subject_id)
    if not subject:
        raise HTTPException(404, "Subject not found")
    return subject


@app.post("/api/v1/catalog/subjects", status_code=201)
def create_subject(body: CreateSubjectRequest, _: Annotated[dict, Depends(require_admin)]):
    if not store.get_grade(body.grade_id):
        raise HTTPException(404, "Grade not found")
    return _catalog_write(
        lambda: store.create_subject(
            grade_id=body.grade_id,
            name=body.name,
            name_ar=body.name_ar,
            seo=body.seo_payload(),
        )
    )


@app.patch("/api/v1/catalog/subjects/{subject_id}")
def update_subject(subject_id: str, body: UpdateCatalogItemRequest, _: Annotated[dict, Depends(require_admin)]):
    if not body.has_catalog_updates():
        raise HTTPException(422, "No fields to update")
    updated = _catalog_write(
        lambda: store.update_subject(
            subject_id,
            name=body.name,
            name_ar=body.name_ar,
            seo=body.seo_updates(),
        )
    )
    if not updated:
        raise HTTPException(404, "Subject not found")
    return updated


@app.delete("/api/v1/catalog/subjects/{subject_id}")
def delete_subject(subject_id: str, _: Annotated[dict, Depends(require_admin)]):
    if not store.get_subject(subject_id):
        raise HTTPException(404, "Subject not found")
    book_count = store.count_books_for_subject(subject_id)
    if not store.deactivate_subject(subject_id):
        raise HTTPException(404, "Subject not found")
    return {"deleted": True, "linked_books": book_count}


# --- Books ---

@app.post("/api/v1/books", status_code=201)
async def upload_book(
    user: Annotated[dict, Depends(require_admin)],
    file: UploadFile = File(...),
    subject_id: str = Form(...),
    metadata: str = Form("{}"),
):
    if not store.get_subject(subject_id):
        raise HTTPException(404, "Subject not found in catalog")
    filename = Path(file.filename or "book.pdf").name
    if not filename.casefold().endswith(".pdf"):
        raise HTTPException(415, "Only PDF textbook uploads are accepted")
    try:
        metadata_obj = json.loads(metadata or "{}")
        if not isinstance(metadata_obj, dict):
            raise ValueError("metadata must be a JSON object")
    except Exception as exc:
        raise HTTPException(422, f"Invalid metadata JSON: {exc}") from exc

    metadata_obj.update(_catalog_metadata(subject_id))

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
        created_by=user["id"],
    )
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
    book_ids = [job.get("book_id") for job in jobs if job.get("book_id")]
    if book_ids:
        try:
            from ..opensearch_index import create_client

            create_client().delete_by_query(
                index=settings.opensearch_index,
                body={"query": {"terms": {"book_id": book_ids}}},
                refresh=True,
            )
        except Exception:
            pass
    return {"deleted": True, "deleted_jobs": len(jobs)}


@app.post("/api/v1/books/{resource_id}/extraction-jobs", status_code=202)
def create_extraction_job(
    resource_id: str,
    request: ExtractionJobRequest,
    _: Annotated[dict, Depends(require_admin)],
):
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
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    result = store.delete_job(job_id)
    if not result:
        raise HTTPException(404, "Job not found")
    if result.get("error") == "job_active":
        raise HTTPException(409, "Stop the job before deleting it")
    deleted_job = result["job"]
    output_dir = deleted_job.get("output_dir")
    doc_ids: list[str] = []
    jsonl_path = Path(str(output_dir)) / "index" / "documents.jsonl" if output_dir else None
    if jsonl_path and jsonl_path.exists():
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("id"):
                doc_ids.append(str(payload["id"]))
    if output_dir:
        shutil.rmtree(output_dir, ignore_errors=True)
    if doc_ids:
        try:
            from ..opensearch_index import create_client, delete_documents

            delete_documents(create_client(), settings.opensearch_index, doc_ids)
        except Exception:
            pass
    return {"deleted": True, "job_id": job_id, "deleted_index_docs": len(doc_ids)}


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


@app.post("/api/v1/search")
def search_content(request: SearchRequest, _: Annotated[dict, Depends(require_admin)]):
    try:
        filters = dict(request.filters or {})
        book_key = filters.get("book_id")
        if book_key:
            ids = [str(book_key)]
            jobs = store.list_jobs(book_resource_id=str(book_key), limit=50)
            for job in jobs:
                if job.get("book_id"):
                    ids.append(str(job["book_id"]))
            filters["book_id"] = list(dict.fromkeys(ids))
        items = _search_service().search(request.query, filters, size=request.size)
        return {"items": items}
    except Exception as exc:
        raise HTTPException(503, f"OpenSearch query failed: {exc}") from exc


@app.get("/api/v1/indexed-books/{book_id}/pages/{page}")
def indexed_page(book_id: str, page: str, _: Annotated[dict, Depends(require_admin)]):
    try:
        return {"items": _search_service().exact_page(book_id, page)}
    except Exception as exc:
        raise HTTPException(503, f"OpenSearch query failed: {exc}") from exc


@app.get("/api/v1/indexed-books/{book_id}/outline")
def indexed_book_outline(book_id: str, _: Annotated[dict, Depends(require_admin)]):
    try:
        ids = [book_id]
        jobs = store.list_jobs(book_resource_id=book_id, limit=50)
        for job in jobs:
            if job.get("book_id"):
                ids.append(str(job["book_id"]))
        for candidate in dict.fromkeys(ids):
            outline = _search_service().book_outline(str(candidate))
            if outline.get("chapters"):
                outline["book_id"] = book_id
                return outline
        return {"book_id": book_id, "chapters": []}
    except Exception as exc:
        raise HTTPException(503, f"OpenSearch query failed: {exc}") from exc


@app.get("/api/v1/indexed-books/{book_id}/questions/{page}/{number}")
def indexed_question(book_id: str, page: str, number: str, _: Annotated[dict, Depends(require_admin)]):
    try:
        return {"items": _search_service().find_question(book_id, page, number)}
    except Exception as exc:
        raise HTTPException(503, f"OpenSearch query failed: {exc}") from exc


@app.post("/api/v1/indexed-books/{book_id}/questions/search")
def indexed_question_search(book_id: str, request: QuestionSearchRequest, _: Annotated[dict, Depends(require_admin)]):
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
def indexed_question_context(question_id: str, _: Annotated[dict, Depends(require_admin)], radius: int = Query(2, ge=0, le=10)):
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
def indexed_asset(asset_id: str, _: Annotated[dict, Depends(require_admin)]):
    try:
        result = _search_service().get_asset(asset_id)
        if result is None:
            raise HTTPException(404, "Asset not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, f"OpenSearch query failed: {exc}") from exc

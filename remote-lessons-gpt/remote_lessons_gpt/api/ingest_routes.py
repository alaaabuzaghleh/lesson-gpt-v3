from __future__ import annotations

import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from ..config import settings
from .deps import require_admin
from .ingest_models import (
    CompleteRemoteJobRequest,
    CreateRemoteJobRequest,
    IngestPageRequest,
    RegisterRemoteBookRequest,
)

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])


def _store():
    from .app import store

    return store


@router.post("/books", status_code=201)
def register_book(
    body: RegisterRemoteBookRequest,
    user: Annotated[dict, Depends(require_admin)],
):
    store = _store()
    if body.subject_id and not store.get_subject(body.subject_id):
        raise HTTPException(404, "Subject not found in catalog")
    book = store.register_remote_book(
        resource_id=body.resource_id,
        subject_id=body.subject_id,
        original_filename=body.original_filename,
        size_bytes=body.size_bytes,
        sha256=body.sha256,
        metadata=body.metadata,
        created_by=user["id"],
    )
    return {
        "resource_id": book["resource_id"],
        "subject_id": book.get("subject_id"),
        "filename": book["original_filename"],
        "size_bytes": book["size_bytes"],
        "sha256": book["sha256"],
        "metadata": book.get("metadata") or {},
        "created_at": book["created_at"],
    }


@router.post("/jobs", status_code=201)
def create_remote_job(body: CreateRemoteJobRequest, _: Annotated[dict, Depends(require_admin)]):
    store = _store()
    if not store.get_book(body.book_resource_id):
        raise HTTPException(404, "Book not registered on remote server")
    output_dir = f"remote://local-admin/jobs/{body.job_id}"
    job = store.create_remote_job_record(
        job_id=body.job_id,
        book_resource_id=body.book_resource_id,
        book_id=body.book_id,
        output_dir=output_dir,
        start_page=body.start_page,
        end_page=body.end_page,
        extractor_backend=body.extractor_backend,
        metadata_overrides={**(body.metadata or {}), "book_id": body.book_id},
    )
    return {"job_id": job["job_id"], "status": job["status"]}


@router.post("/jobs/{job_id}/pages", status_code=201)
def ingest_page(job_id: str, body: IngestPageRequest, _: Annotated[dict, Depends(require_admin)]):
    store = _store()
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if not body.documents:
        raise HTTPException(422, "At least one OpenSearch document is required")

    from ..opensearch_index import bulk_index, create_client, ensure_index

    client = create_client()
    ensure_index(client, settings.opensearch_index, recreate=False)
    success, errors = bulk_index(client, settings.opensearch_index, body.documents, refresh=True)
    if errors:
        raise HTTPException(502, f"OpenSearch indexing failed for {len(errors)} document(s)")

    page_id = hashlib.sha256(f"{body.book_id}|{body.pdf_page_number}".encode()).hexdigest()[:32]
    store.upsert_book_page(
        page_id=page_id,
        book_id=body.book_id,
        book_resource_id=body.book_resource_id,
        job_id=job_id,
        pdf_page_number=body.pdf_page_number,
        printed_page_number=body.printed_page_number,
        document_count=int(success),
        page_json=body.page_json,
    )

    if body.progress is not None:
        store.update_progress(
            job_id,
            progress=float(body.progress),
            stage=body.stage or "remote_ingest",
            message=body.message or f"Ingested page {body.pdf_page_number}",
            current_page=body.pdf_page_number,
            total_pages=body.total_pages,
            add_event=True,
        )

    indexed = int(job.get("indexed_records") or 0) + int(success)
    with store.pool.connection() as conn:
        conn.execute(
            "UPDATE jobs SET indexed_records=%s, book_id=COALESCE(book_id, %s), updated_at=NOW() WHERE job_id=%s",
            (indexed, body.book_id, job_id),
        )
        conn.commit()

    store.add_event(
        job_id,
        "page_ingested",
        stage=body.stage or "remote_ingest",
        progress=body.progress,
        message=f"Page {body.pdf_page_number} available on remote",
        payload={"pdf_page_number": body.pdf_page_number, "indexed_documents": int(success)},
    )
    return {
        "job_id": job_id,
        "pdf_page_number": body.pdf_page_number,
        "indexed_documents": int(success),
        "page_id": page_id,
    }


@router.post("/jobs/{job_id}/complete")
def complete_remote_job(job_id: str, body: CompleteRemoteJobRequest, _: Annotated[dict, Depends(require_admin)]):
    store = _store()
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    result = dict(body.result or {})
    result.setdefault("book_id", body.book_id)
    result.setdefault("indexed_records", body.indexed_records)
    result.setdefault("extracted_records", body.extracted_records)
    store.complete_job(job_id, result=result)
    return {"job_id": job_id, "status": "completed"}


@router.get("/books/{book_id}/pages")
def list_remote_book_pages(book_id: str, _: Annotated[dict, Depends(require_admin)]):
    store = _store()
    return {"items": store.list_book_pages(book_id)}

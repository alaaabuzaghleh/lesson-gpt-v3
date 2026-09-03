from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RegisterRemoteBookRequest(BaseModel):
    resource_id: str
    subject_id: str | None = None
    original_filename: str
    size_bytes: int
    sha256: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateRemoteJobRequest(BaseModel):
    job_id: str
    book_resource_id: str
    book_id: str | None = None
    start_page: int = Field(default=1, ge=1)
    end_page: int | None = Field(default=None, ge=1)
    extractor_backend: str = "local"
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestPageRequest(BaseModel):
    book_id: str
    book_resource_id: str
    pdf_page_number: int = Field(ge=1)
    printed_page_number: str | None = None
    page_json: dict[str, Any] = Field(default_factory=dict)
    documents: list[dict[str, Any]] = Field(default_factory=list)
    progress: float | None = None
    total_pages: int | None = None
    stage: str | None = None
    message: str | None = None


class CompleteRemoteJobRequest(BaseModel):
    result: dict[str, Any] = Field(default_factory=dict)
    book_id: str | None = None
    extracted_records: int | None = None
    indexed_records: int | None = None

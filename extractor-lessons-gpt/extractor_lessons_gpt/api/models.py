from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from remote_lessons_gpt.api.models import (
    CreateAdminRequest,
    CreateCountryRequest,
    CreateEducationSystemRequest,
    CreateGradeRequest,
    CreateSubjectRequest,
    LoginRequest,
    QuestionSearchRequest,
    SearchRequest,
    UpdateCatalogItemRequest,
)

ExtractorBackend = Literal["local", "codex"]


class ExtractionJobRequest(BaseModel):
    start_page: int = Field(default=1, ge=1)
    end_page: int | None = Field(default=None, ge=1)
    resume: bool = True
    index_to_opensearch: bool = True
    recreate_index: bool = False
    metadata_overrides: dict[str, Any] = Field(default_factory=dict)
    extractor_backend: ExtractorBackend = "local"
    sync_to_remote: bool = False
    language_hint: str = "Arabic mathematics textbook content"

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_page is not None and self.end_page < self.start_page:
            raise ValueError("end_page must be greater than or equal to start_page")
        return self


class RemoteSyncRequest(BaseModel):
    book_id: str
    recreate_index: bool = False

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class ExtractionJobRequest(BaseModel):
    start_page: int = Field(default=1, ge=1)
    end_page: int | None = Field(default=None, ge=1)
    resume: bool = True
    index_to_opensearch: bool = True
    recreate_index: bool = False
    metadata_overrides: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_page is not None and self.end_page < self.start_page:
            raise ValueError("end_page must be greater than or equal to start_page")
        return self


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    filters: dict[str, Any] = Field(default_factory=dict)
    size: int = Field(default=15, ge=1, le=100)


class QuestionSearchRequest(BaseModel):
    query: str | None = None
    scope: str | None = None
    question_format: str | None = None
    purpose: str | None = None
    bloom_level: str | None = None
    difficulty: str | None = None
    lesson_title: str | None = None
    chapter_title: str | None = None
    unit_title: str | None = None
    requires_visual: bool | None = None
    size: int = Field(default=100, ge=1, le=500)

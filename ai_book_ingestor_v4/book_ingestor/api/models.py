from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class CreateAdminRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=200)


class CreateCountryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    name_ar: str | None = None
    code: str | None = Field(default=None, max_length=10)


class CreateEducationSystemRequest(BaseModel):
    country_id: str
    name: str = Field(min_length=1, max_length=200)
    name_ar: str | None = None


class CreateGradeRequest(BaseModel):
    education_system_id: str
    name: str = Field(min_length=1, max_length=200)
    name_ar: str | None = None
    sort_order: int = 0


class CreateSubjectRequest(BaseModel):
    grade_id: str
    name: str = Field(min_length=1, max_length=200)
    name_ar: str | None = None


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


UserRole = Literal["super_admin", "admin", "student"]

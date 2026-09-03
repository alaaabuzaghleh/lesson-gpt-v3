from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

from .catalog_seo import SEO_FIELD_NAMES


class CatalogSeoInput(BaseModel):
    seo_title_en: str | None = Field(default=None, max_length=500)
    seo_title_ar: str | None = Field(default=None, max_length=500)
    seo_meta_description_en: str | None = Field(default=None, max_length=1000)
    seo_meta_description_ar: str | None = Field(default=None, max_length=1000)
    seo_keywords_en: str | None = Field(default=None, max_length=1000)
    seo_keywords_ar: str | None = Field(default=None, max_length=1000)
    seo_description_en: str | None = None
    seo_description_ar: str | None = None
    slug_en: str | None = Field(default=None, max_length=120)
    slug_ar: str | None = Field(default=None, max_length=120)

    def seo_payload(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in SEO_FIELD_NAMES if k != "hero_image_path" and getattr(self, k) is not None}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class CreateAdminRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=200)


class CreateCountryRequest(CatalogSeoInput):
    name: str = Field(min_length=1, max_length=200)
    name_ar: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=10)


class CreateEducationSystemRequest(CatalogSeoInput):
    country_id: str
    name: str = Field(min_length=1, max_length=200)
    name_ar: str = Field(min_length=1, max_length=200)


class CreateGradeRequest(CatalogSeoInput):
    education_system_id: str
    name: str = Field(min_length=1, max_length=200)
    name_ar: str = Field(min_length=1, max_length=200)
    sort_order: int = 0


class CreateSubjectRequest(CatalogSeoInput):
    grade_id: str
    name: str = Field(min_length=1, max_length=200)
    name_ar: str = Field(min_length=1, max_length=200)


class UpdateCatalogItemRequest(CatalogSeoInput):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    name_ar: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=10)
    sort_order: int | None = None

    def seo_updates(self) -> dict[str, Any]:
        return self.seo_payload()

    def has_catalog_updates(self) -> bool:
        basic = (
            self.name is not None
            or self.name_ar is not None
            or self.code is not None
            or self.sort_order is not None
        )
        return basic or bool(self.seo_updates())


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
    query: str = ""
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

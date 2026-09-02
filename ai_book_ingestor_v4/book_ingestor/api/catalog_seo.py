from __future__ import annotations

import re
from pathlib import Path
from typing import Any

CATALOG_ENTITY_TYPES = frozenset({"country", "system", "grade", "subject"})

ENTITY_TABLE = {
    "country": "countries",
    "system": "education_systems",
    "grade": "grades",
    "subject": "subjects",
}

SEO_COLUMN_DEFS: list[tuple[str, str]] = [
    ("seo_title_en", "TEXT"),
    ("seo_title_ar", "TEXT"),
    ("seo_meta_description_en", "TEXT"),
    ("seo_meta_description_ar", "TEXT"),
    ("seo_keywords_en", "TEXT"),
    ("seo_keywords_ar", "TEXT"),
    ("seo_description_en", "TEXT"),
    ("seo_description_ar", "TEXT"),
    ("slug_en", "TEXT"),
    ("slug_ar", "TEXT"),
    ("hero_image_path", "TEXT"),
]

SEO_FIELD_NAMES = [c[0] for c in SEO_COLUMN_DEFS]

CATALOG_TABLES = ("countries", "education_systems", "grades", "subjects")

# Parent scope column for slug/name uniqueness within hierarchy.
ENTITY_PARENT_SCOPE: dict[str, str | None] = {
    "country": None,
    "system": "country_id",
    "grade": "education_system_id",
    "subject": "grade_id",
}

UNIQUE_CATALOG_COLUMNS = ("name", "name_ar", "slug_en", "slug_ar")


class CatalogDuplicateError(ValueError):
    """Raised when a catalog name or slug conflicts within its scope."""

    def __init__(self, message: str, *, field: str | None = None):
        super().__init__(message)
        self.field = field

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HERO_DIR = PACKAGE_ROOT / "static" / "catalog_heroes"
DEFAULT_HERO_FILES = {
    "country": DEFAULT_HERO_DIR / "country-default.svg",
    "system": DEFAULT_HERO_DIR / "system-default.svg",
    "grade": DEFAULT_HERO_DIR / "grade-default.svg",
    "subject": DEFAULT_HERO_DIR / "subject-default.svg",
}


def slugify_en(text: str) -> str:
    cleaned = text.strip().lower()
    cleaned = re.sub(r"[^a-z0-9\u0600-\u06FF\s-]", "", cleaned)
    cleaned = re.sub(r"[\s_]+", "-", cleaned).strip("-")
    if re.search(r"[a-z0-9]", cleaned):
        return cleaned[:120] or "item"
    return "item"


def slugify_ar(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"[\s_]+", "-", cleaned)
    cleaned = re.sub(r"[^\w\u0600-\u06FF-]", "", cleaned, flags=re.UNICODE).strip("-")
    return (cleaned[:120] or "عنصر")


def seo_defaults(name: str, name_ar: str | None = None) -> dict[str, str]:
    ar = (name_ar or name).strip() or name
    en = name.strip() or ar
    return {
        "seo_title_en": en,
        "seo_title_ar": ar,
        "seo_meta_description_en": en,
        "seo_meta_description_ar": ar,
        "seo_keywords_en": "",
        "seo_keywords_ar": "",
        "seo_description_en": "",
        "seo_description_ar": "",
        "slug_en": slugify_en(en),
        "slug_ar": slugify_ar(ar),
    }


def prepare_seo_payload(name: str, name_ar: str | None, overrides: dict[str, Any] | None = None) -> dict[str, str]:
    data = seo_defaults(name, name_ar)
    if overrides:
        for key in SEO_FIELD_NAMES:
            if key == "hero_image_path":
                continue
            if key in overrides and overrides[key] is not None:
                data[key] = str(overrides[key]).strip()
    if data.get("slug_en"):
        data["slug_en"] = slugify_en(data["slug_en"]) or slugify_en(name)
    else:
        data["slug_en"] = slugify_en(name)
    if data.get("slug_ar"):
        data["slug_ar"] = slugify_ar(data["slug_ar"]) or slugify_ar(name_ar or name)
    else:
        data["slug_ar"] = slugify_ar(name_ar or name)
    return data


def hero_api_path(entity_type: str, entity_id: str) -> str:
    return f"/api/v1/catalog/hero/{entity_type}/{entity_id}"


def enrich_catalog_item(item: dict[str, Any], entity_type: str) -> dict[str, Any]:
    item = dict(item)
    seo: dict[str, Any] = {}
    for field in SEO_FIELD_NAMES:
        if field in item:
            seo[field] = item.pop(field)
    item["seo"] = seo
    item["has_custom_hero"] = bool(seo.get("hero_image_path"))
    item["hero_image_url"] = hero_api_path(entity_type, item["id"])
    return item


def default_hero_file(entity_type: str) -> Path:
    path = DEFAULT_HERO_FILES.get(entity_type)
    if path and path.exists():
        return path
    return DEFAULT_HERO_FILES["subject"]

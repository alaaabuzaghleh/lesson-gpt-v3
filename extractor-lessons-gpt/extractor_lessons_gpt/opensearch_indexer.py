from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from remote_lessons_gpt.hierarchy import HierarchyResolver, hierarchy_path_from, infer_structure_headings
from remote_lessons_gpt.normalizer import build_search_text, normalize_general
from remote_lessons_gpt.opensearch_index import bulk_index, create_client, ensure_index
from remote_lessons_gpt.schemas import BookMetadata, ContentType, IndexDocument

from .config import Settings


def stable_book_id(pdf_path: Path, meta: BookMetadata) -> str:
    digest = hashlib.sha256()
    with pdf_path.open("rb") as handle:
        digest.update(handle.read(4_000_000))
    digest.update(str(pdf_path.stat().st_size).encode())
    digest.update((meta.title or pdf_path.stem).encode("utf-8", errors="ignore"))
    return digest.hexdigest()[:24]


def stable_block_id(book_id: str, page_no: int, seq: int, text: str, ctype: str) -> str:
    raw = f"{book_id}|{page_no}|{seq}|{ctype}|{text[:300]}".encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()[:32]


_HEADING_TYPES = {
    "unit": ContentType.UNIT_TITLE.value,
    "chapter": ContentType.CHAPTER_TITLE.value,
    "lesson": ContentType.LESSON_TITLE.value,
    "section": ContentType.SECTION_HEADING.value,
    "other": ContentType.SECTION_HEADING.value,
}


def _apply_env(settings: Settings) -> None:
    os.environ["OPENSEARCH_URL"] = settings.opensearch_url
    os.environ["OPENSEARCH_USERNAME"] = settings.opensearch_username
    os.environ["OPENSEARCH_PASSWORD"] = settings.opensearch_password
    os.environ["OPENSEARCH_VERIFY_CERTS"] = str(settings.opensearch_verify_certs).lower()
    os.environ["OPENSEARCH_INDEX"] = settings.opensearch_index


def metadata_from_pdf(pdf_path: Path, **overrides: Any) -> BookMetadata:
    stem = pdf_path.stem
    defaults = {
        "title": stem.replace("-", " ").replace("_", " "),
        "country": "Saudi Arabia",
        "education_system": "National",
        "grade": "2",
        "subject": "Mathematics",
        "semester": "1",
        "language": "ar",
    }
    if "math" in stem.lower():
        defaults["subject"] = "Mathematics"
    if ".1." in stem or "sm1" in stem.lower():
        defaults["semester"] = "1"
    defaults.update({k: v for k, v in overrides.items() if v is not None and str(v).strip()})
    return BookMetadata.model_validate(defaults)


class OpenSearchIndexer:
    def __init__(self, settings: Settings):
        _apply_env(settings)
        self.settings = settings
        self.index_name = settings.opensearch_index
        self.client = create_client()
        ensure_index(self.client, self.index_name, recreate=False)

    def index_documents(self, docs: list[IndexDocument]) -> tuple[int, list[Any]]:
        if not docs:
            return 0, []
        payloads = [doc.model_dump(mode="json") for doc in docs]
        success, errors = bulk_index(self.client, self.index_name, payloads, refresh=False)
        if errors:
            print(f"OpenSearch bulk warnings: {len(errors)} item(s)")
        return int(success), errors


def build_page_documents(
    *,
    page_data: dict[str, Any],
    metadata: BookMetadata,
    book_id: str,
    pdf_path: Path,
    page_image_path: Path,
    hierarchy: HierarchyResolver,
    text_source: str = "codex",
) -> list[IndexDocument]:
    page_no = int(page_data.get("pdf_page_number") or 0)
    body_text = str(page_data.get("body_text") or "").strip()
    printed_page = page_data.get("printed_page_number")
    language = str(page_data.get("language") or metadata.language or "ar")
    notes = [str(page_data.get("notes") or "").strip()] if page_data.get("notes") else []
    notes.append(f"{text_source}_extraction")

    for heading in page_data.get("headings") or []:
        level = str(heading.get("level") or "other")
        title = str(heading.get("title") or "").strip()
        if not title:
            continue
        if level == "unit":
            hierarchy.apply_titles(unit=title)
        elif level == "chapter":
            hierarchy.apply_titles(chapter=title)
        elif level == "lesson":
            hierarchy.apply_titles(lesson=title)
        elif level == "section":
            hierarchy.apply_titles(section=title)

    inferred = infer_structure_headings(body_text)
    ctx = hierarchy.fill_missing(
        unit=inferred.get("unit"),
        chapter=inferred.get("chapter"),
        lesson=inferred.get("lesson"),
    )
    path = hierarchy_path_from(ctx)
    hierarchy_fields = {
        "unit_title": ctx.unit_title,
        "chapter_title": ctx.chapter_title,
        "lesson_title": ctx.lesson_title,
        "section_title": ctx.section_title,
        "unit_id": ctx.unit_id,
        "chapter_id": ctx.chapter_id,
        "lesson_id": ctx.lesson_id,
        "hierarchy_path": path,
    }

    docs: list[IndexDocument] = []
    search_text = build_search_text(metadata.title, metadata.subject, metadata.grade, path, body_text)
    normalized = normalize_general(body_text)
    quality = min(1.0, 0.35 + min(len(normalized), 1200) / 1200 * 0.65)

    docs.append(
        IndexDocument(
            id=stable_block_id(book_id, page_no, 0, body_text or f"{text_source}-page-{page_no}", ContentType.OCR_PAGE.value),
            book_id=book_id,
            book_title=metadata.title or pdf_path.stem,
            country=metadata.country,
            curriculum=metadata.curriculum,
            education_system=metadata.education_system,
            grade=metadata.grade,
            subject=metadata.subject,
            semester=metadata.semester,
            academic_year=metadata.academic_year,
            language=language,
            pdf_page_number=page_no,
            printed_page_number=str(printed_page) if printed_page else None,
            **hierarchy_fields,
            sequence=0,
            content_type=ContentType.OCR_PAGE.value,
            subtype=f"{text_source}_page",
            title=f"Page {page_no}",
            text=body_text,
            normalized_text=normalized,
            search_text=search_text,
            ocr_text=body_text,
            ocr_source=text_source,
            text_source=text_source,
            page_image_path=str(page_image_path),
            source_pdf_path=str(pdf_path),
            confidence=quality,
            quality_score=quality,
            extraction_notes=[n for n in notes if n],
        )
    )

    seq = 0
    for heading in page_data.get("headings") or []:
        title = str(heading.get("title") or "").strip()
        if not title:
            continue
        seq += 1
        level = str(heading.get("level") or "other")
        ctype = _HEADING_TYPES.get(level, ContentType.SECTION_HEADING.value)
        docs.append(
            _block_doc(
                book_id=book_id,
                metadata=metadata,
                pdf_path=pdf_path,
                page_no=page_no,
                printed_page=printed_page,
                hierarchy_fields=hierarchy_fields,
                language=language,
                page_image_path=page_image_path,
                seq=seq,
                ctype=ctype,
                text=title,
                title=title,
                path=path,
                text_source=text_source,
            )
        )

    for formula in page_data.get("formulas") or []:
        text = str(formula or "").strip()
        if not text:
            continue
        seq += 1
        docs.append(
            _block_doc(
                book_id=book_id,
                metadata=metadata,
                pdf_path=pdf_path,
                page_no=page_no,
                printed_page=printed_page,
                hierarchy_fields=hierarchy_fields,
                language=language,
                page_image_path=page_image_path,
                seq=seq,
                ctype=ContentType.FORMULA.value,
                text=text,
                path=path,
                text_source=text_source,
            )
        )

    for table_md in page_data.get("tables_markdown") or []:
        text = str(table_md or "").strip()
        if not text:
            continue
        seq += 1
        docs.append(
            _block_doc(
                book_id=book_id,
                metadata=metadata,
                pdf_path=pdf_path,
                page_no=page_no,
                printed_page=printed_page,
                hierarchy_fields=hierarchy_fields,
                language=language,
                page_image_path=page_image_path,
                seq=seq,
                ctype=ContentType.TABLE.value,
                text=text,
                path=path,
                text_source=text_source,
            )
        )

    for figure in page_data.get("figures") or []:
        caption = str(figure.get("caption") or "").strip()
        description = str(figure.get("description") or "").strip()
        text = "\n".join(part for part in (caption, description) if part)
        if not text:
            continue
        seq += 1
        docs.append(
            _block_doc(
                book_id=book_id,
                metadata=metadata,
                pdf_path=pdf_path,
                page_no=page_no,
                printed_page=printed_page,
                hierarchy_fields=hierarchy_fields,
                language=language,
                page_image_path=page_image_path,
                seq=seq,
                ctype=ContentType.FIGURE.value,
                text=text,
                title=caption or None,
                caption=caption or None,
                path=path,
                text_source=text_source,
            )
        )

    return docs


def _block_doc(
    *,
    book_id: str,
    metadata: BookMetadata,
    pdf_path: Path,
    page_no: int,
    printed_page: str | None,
    hierarchy_fields: dict[str, Any],
    language: str,
    page_image_path: Path,
    seq: int,
    ctype: str,
    text: str,
    path: list[str],
    title: str | None = None,
    caption: str | None = None,
    text_source: str = "codex",
) -> IndexDocument:
    normalized = normalize_general(text)
    search_text = build_search_text(metadata.title, metadata.subject, metadata.grade, path, ctype, text)
    quality = min(1.0, 0.4 + min(len(normalized), 600) / 600 * 0.6)
    return IndexDocument(
        id=stable_block_id(book_id, page_no, seq, f"{text_source}|{text}", ctype),
        book_id=book_id,
        book_title=metadata.title or pdf_path.stem,
        country=metadata.country,
        curriculum=metadata.curriculum,
        education_system=metadata.education_system,
        grade=metadata.grade,
        subject=metadata.subject,
        semester=metadata.semester,
        academic_year=metadata.academic_year,
        language=language,
        pdf_page_number=page_no,
        printed_page_number=str(printed_page) if printed_page else None,
        **hierarchy_fields,
        sequence=seq,
        content_type=ctype,
        subtype=f"{text_source}_block",
        title=title,
        text=text,
        normalized_text=normalized,
        search_text=search_text,
        ocr_text=text,
        ocr_source=text_source,
        text_source=text_source,
        caption=caption,
        page_image_path=str(page_image_path),
        source_pdf_path=str(pdf_path),
        confidence=quality,
        quality_score=quality,
        extraction_notes=[f"{text_source}_extraction"],
    )


def book_id_for_pdf(pdf_path: Path, metadata: BookMetadata) -> str:
    return stable_book_id(pdf_path, metadata)
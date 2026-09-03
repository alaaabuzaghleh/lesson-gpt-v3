from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .normalizer import normalize_general
from .schemas import HierarchyContext, IndexDocument, PageExtraction

_UNIT_RE = re.compile(
    r"(?<![\u0600-\u06FF])(الوحدة|وحدة)\s*(?:[:.\-–])?\s*([0-9٠-٩]+|[^\n]{1,40})",
)
_CHAPTER_RE = re.compile(
    r"(الفصل|فصل)\s*(?:[:.\-–])?\s*([0-9٠-٩]+|[^\n]{1,40})",
)
_LESSON_RE = re.compile(
    r"(الدرس|درس)\s*(?:[:.\-–])?\s*([0-9٠-٩]+(?:\s*[-–]\s*[0-9٠-٩]+)?|[^\n]{1,40})",
)


def _clip_heading(prefix: str, rest: str) -> str:
    rest = (rest or "").strip(" :.-–،,")
    rest = re.split(r"[\n|/]", rest, maxsplit=1)[0].strip()
    if len(rest) > 80:
        rest = rest[:80].rstrip()
    if not rest:
        return prefix
    if rest.startswith(prefix):
        return rest
    return f"{prefix} {rest}".strip()


def infer_structure_headings(text: str) -> dict[str, str | None]:
    blob = text or ""
    found: dict[str, str | None] = {"unit": None, "chapter": None, "lesson": None}
    unit = _UNIT_RE.search(blob)
    if unit and not unit.group(0).startswith("بوحدة"):
        found["unit"] = _clip_heading(unit.group(1), unit.group(2))
    chapter = _CHAPTER_RE.search(blob)
    if chapter:
        found["chapter"] = _clip_heading(chapter.group(1), chapter.group(2))
    lesson = _LESSON_RE.search(blob)
    if lesson:
        found["lesson"] = _clip_heading(lesson.group(1), lesson.group(2))
    return found


def hierarchy_path_from(ctx: HierarchyContext) -> list[str]:
    return [part for part in (ctx.unit_title, ctx.chapter_title, ctx.lesson_title, ctx.section_title) if part]


def heading_id(book_id: str, kind: str, title: str | None) -> str | None:
    key = normalize_general(title or "")
    if not key:
        return None
    raw = f"{book_id}|{kind}|{key}".encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()[:16]


def apply_heading_ids(ctx: HierarchyContext, book_id: str) -> HierarchyContext:
    ctx.unit_id = heading_id(book_id, "unit", ctx.unit_title)
    ctx.chapter_id = heading_id(book_id, "chapter", ctx.chapter_title)
    ctx.lesson_id = heading_id(book_id, "lesson", ctx.lesson_title)
    return ctx


def build_content_tree(book_id: str, docs: list[IndexDocument]) -> dict[str, Any]:
    chapters: dict[str, dict[str, Any]] = {}
    chapter_order: list[str] = []
    for doc in sorted(docs, key=lambda item: (item.pdf_page_number, item.sequence)):
        chapter_key = doc.chapter_id or "_uncategorized"
        if chapter_key not in chapters:
            chapters[chapter_key] = {
                "id": doc.chapter_id,
                "type": "chapter",
                "title": doc.chapter_title or "بدون فصل",
                "unit_id": doc.unit_id,
                "unit_title": doc.unit_title,
                "start_page": doc.pdf_page_number,
                "end_page": doc.pdf_page_number,
                "lessons": {},
                "lesson_order": [],
            }
            chapter_order.append(chapter_key)
        chapter = chapters[chapter_key]
        chapter["end_page"] = max(int(chapter["end_page"]), doc.pdf_page_number)
        lesson_key = doc.lesson_id or "_chapter_body"
        lessons: dict[str, dict[str, Any]] = chapter["lessons"]
        if lesson_key not in lessons:
            lessons[lesson_key] = {
                "id": doc.lesson_id,
                "type": "lesson",
                "title": doc.lesson_title or "محتوى الفصل",
                "chapter_id": doc.chapter_id,
                "chapter_title": doc.chapter_title,
                "unit_id": doc.unit_id,
                "unit_title": doc.unit_title,
                "start_page": doc.pdf_page_number,
                "end_page": doc.pdf_page_number,
                "content_count": 0,
                "content_types": defaultdict(int),
            }
            chapter["lesson_order"].append(lesson_key)
        lesson = lessons[lesson_key]
        lesson["end_page"] = max(int(lesson["end_page"]), doc.pdf_page_number)
        lesson["content_count"] += 1
        lesson["content_types"][doc.content_type] += 1

    tree = []
    for chapter_key in chapter_order:
        chapter = chapters[chapter_key]
        tree.append(
            {
                "id": chapter["id"],
                "type": "chapter",
                "title": chapter["title"],
                "unit_id": chapter["unit_id"],
                "unit_title": chapter["unit_title"],
                "start_page": chapter["start_page"],
                "end_page": chapter["end_page"],
                "lessons": [
                    {
                        **chapter["lessons"][lesson_key],
                        "content_types": dict(chapter["lessons"][lesson_key]["content_types"]),
                    }
                    for lesson_key in chapter["lesson_order"]
                ],
            }
        )
    return {"book_id": book_id, "chapters": tree}


@dataclass
class HierarchyResolver:
    book_id: str = ""
    current: HierarchyContext = field(default_factory=HierarchyContext)

    def _sync_ids(self) -> HierarchyContext:
        apply_heading_ids(self.current, self.book_id)
        return HierarchyContext.model_validate(self.current.model_dump())

    def apply_titles(
        self,
        *,
        unit: str | None = None,
        chapter: str | None = None,
        lesson: str | None = None,
        section: str | None = None,
    ) -> HierarchyContext:
        if unit:
            self.current.unit_title = unit.strip()
            self.current.chapter_title = None
            self.current.lesson_title = None
            self.current.section_title = None
        if chapter:
            self.current.chapter_title = chapter.strip()
            self.current.lesson_title = None
            self.current.section_title = None
        if lesson:
            self.current.lesson_title = lesson.strip()
            self.current.section_title = None
        if section:
            self.current.section_title = section.strip()
        return self._sync_ids()

    def fill_missing(
        self,
        *,
        unit: str | None = None,
        chapter: str | None = None,
        lesson: str | None = None,
        section: str | None = None,
    ) -> HierarchyContext:
        if unit and not self.current.unit_title:
            self.current.unit_title = unit.strip()
        if chapter and not self.current.chapter_title:
            self.current.chapter_title = chapter.strip()
        if lesson and not self.current.lesson_title:
            self.current.lesson_title = lesson.strip()
        if section and not self.current.section_title:
            self.current.section_title = section.strip()
        return self._sync_ids()

    def apply_page(self, page: PageExtraction) -> HierarchyContext:
        self.apply_titles(
            unit=page.explicit_unit_title,
            chapter=page.explicit_chapter_title,
            lesson=page.explicit_lesson_title,
            section=page.explicit_section_title,
        )
        inferred = infer_structure_headings(
            "\n".join(
                part
                for part in (
                    page.explicit_unit_title,
                    page.explicit_chapter_title,
                    page.explicit_lesson_title,
                    *(f"{b.title or ''}\n{(b.verbatim_text or '')[:200]}" for b in page.blocks[:6]),
                )
                if part
            )
        )
        return self.fill_missing(
            unit=inferred.get("unit"),
            chapter=inferred.get("chapter"),
            lesson=inferred.get("lesson"),
        )

    def apply_ocr_text(self, text: str, *, content_type: str | None = None, title: str | None = None) -> HierarchyContext:
        heading = (title or text or "").strip()
        inferred = infer_structure_headings(heading)
        # Only promote MinerU "title" blocks when the wording is actually a unit/chapter/lesson.
        if content_type == "unit_title" and inferred.get("unit"):
            return self.apply_titles(unit=inferred["unit"])
        if content_type == "chapter_title" and inferred.get("chapter"):
            return self.apply_titles(chapter=inferred["chapter"])
        if content_type == "lesson_title" and inferred.get("lesson"):
            return self.apply_titles(lesson=inferred["lesson"])
        return self.fill_missing(
            unit=inferred.get("unit"),
            chapter=inferred.get("chapter"),
            lesson=inferred.get("lesson"),
        )

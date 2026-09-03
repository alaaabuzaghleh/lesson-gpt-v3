from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import orjson
from rich.console import Console
from rich.progress import Progress

from .checkpoint import JobCheckpoint, checkpoint_path
from .config import settings
from .hierarchy import HierarchyResolver, build_content_tree, hierarchy_path_from
from .ocr_cleanup import repair_arabic_ocr
from .mineru_parser import (
    MinerUError,
    MinerUPage,
    load_incremental_mineru_document,
    mineru_bbox_dict,
    mineru_block_is_indexable,
    mineru_content_type,
    mineru_page_artifact_dir,
    parse_pdf_with_mineru,
)
from .normalizer import build_search_text, normalize_general
from .pdf_reader import PDFReader, PageData
from .prompts import BOOK_METADATA_PROMPT, BOOK_METADATA_SYSTEM, PAGE_SYSTEM, page_prompt
from .quality import block_quality_score, ocr_completeness, ocr_page_is_sparse, ocr_page_quality_score
from .question_intelligence import QuestionIntelligenceEngine
from .schemas import BookMetadata, ContentType, HierarchyContext, IndexDocument, PageExtraction, QuestionData, VISUAL_TYPES, VisualAnalysis
from .visual_analyzer import UniversalVisualAnalyzer
from .vlm_client import OpenAICompatibleVLM

console = Console()


class JobCancelled(RuntimeError):
    """Raised when an external caller requests cooperative stop/pause."""


ProgressCallback = Callable[[dict[str, Any]], None]
CancelCheck = Callable[[], bool]
PageDocsCallback = Callable[[int, list[IndexDocument]], None]


def stable_book_id(pdf_path: Path, meta: BookMetadata) -> str:
    h = hashlib.sha256()
    with pdf_path.open("rb") as f:
        h.update(f.read(4_000_000))
    h.update(str(pdf_path.stat().st_size).encode())
    h.update((meta.title or pdf_path.stem).encode("utf-8", errors="ignore"))
    return h.hexdigest()[:24]


def stable_block_id(book_id: str, page_no: int, seq: int, text: str, ctype: str) -> str:
    raw = f"{book_id}|{page_no}|{seq}|{ctype}|{text[:300]}".encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()[:32]


def stable_asset_id(book_id: str, page_no: int, seq: int) -> str:
    return f"{book_id}-p{page_no:04d}-a{seq:03d}"


def merge_metadata(detected: BookMetadata, overrides: dict[str, Any]) -> BookMetadata:
    data = detected.model_dump()
    for k, v in overrides.items():
        if v is not None and str(v).strip() != "":
            data[k] = v
    return BookMetadata.model_validate(data)


class BookIngestionPipeline:
    def __init__(self, pdf_path: str | Path, output_dir: str | Path):
        self.pdf_path = Path(pdf_path).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir = self.output_dir / "raw"
        self.extracted_dir = self.output_dir / "extracted_pages"
        self.assets_dir = self.output_dir / "assets"
        self.index_dir = self.output_dir / "index"
        for d in (self.raw_dir, self.extracted_dir, self.assets_dir, self.index_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.reader = PDFReader(self.pdf_path, self.output_dir, dpi=settings.render_dpi)
        self.vlm = OpenAICompatibleVLM()
        self.visual_analyzer = UniversalVisualAnalyzer(self.vlm, self.output_dir)
        self.question_intelligence = QuestionIntelligenceEngine()

    def detect_metadata(self, max_pages: int = 2) -> BookMetadata:
        page_count = min(max_pages, self.reader.page_count)
        last_error: Exception | None = None
        for count in (page_count, 1):
            if count < 1:
                break
            pages = [self.reader.render_page(n) for n in range(1, count + 1)]
            prompt = BOOK_METADATA_PROMPT + "\nThe supplied images correspond to PDF pages: " + ", ".join(
                str(x.pdf_page_number) for x in pages
            )
            try:
                raw = self.vlm.chat_json(BOOK_METADATA_SYSTEM, prompt, [x.as_data_url() for x in pages])
                (self.raw_dir / "book_metadata.json").write_bytes(
                    orjson.dumps(raw, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS)
                )
                return BookMetadata.model_validate(raw)
            except Exception as exc:
                last_error = exc
                if count <= 1:
                    break
        assert last_error is not None
        raise last_error

    def extract_page(self, page: PageData, metadata: BookMetadata, resume: bool = True) -> PageExtraction:
        out = self.extracted_dir / f"page_{page.pdf_page_number:04d}.json"
        if resume and out.exists():
            return PageExtraction.model_validate_json(out.read_text(encoding="utf-8"))

        raw = self.vlm.chat_json(
            PAGE_SYSTEM,
            page_prompt(
                page.pdf_page_number,
                page.text_layer,
                metadata.model_dump(),
                text_source=page.text_source,
                structured_blocks=json.dumps(page.mineru_blocks, ensure_ascii=False, indent=2)
                if page.mineru_blocks
                else None,
                text_limit=settings.mineru_text_chars if page.text_source == "mineru" else 8000,
            ),
            [page.as_data_url()],
        )
        if isinstance(raw, dict):
            raw["pdf_page_number"] = page.pdf_page_number
        (self.raw_dir / f"page_{page.pdf_page_number:04d}.json").write_text(
            json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        extraction = PageExtraction.model_validate(raw)

        # Deterministic sequence and anti-hallucination guard for answers.
        for idx, block in enumerate(extraction.blocks, start=1):
            block.sequence = idx
            if block.question and block.question.visible_answer and not block.question.answer_is_explicitly_visible:
                block.question.visible_answer = None

        out.write_text(extraction.model_dump_json(indent=2), encoding="utf-8")
        return extraction

    def _context_for_asset(self, page_no: int, extraction: PageExtraction, block_sequence: int) -> str:
        current_parts: list[str] = []
        for b in extraction.blocks:
            if abs(b.sequence - block_sequence) <= 3:
                current_parts.append(
                    f"[current page block {b.sequence} type={b.content_type.value}] "
                    f"{b.title or ''}\n{b.verbatim_text}\n{b.caption or ''}"
                )
        parts = ["\n".join(current_parts)]

        if settings.include_neighbor_page_text:
            for n, tag in ((page_no - 1, "previous page"), (page_no + 1, "next page")):
                if 1 <= n <= self.reader.page_count:
                    p = self.reader.render_page(n)
                    if p.text_layer.strip():
                        label = "MinerU reading-order text" if p.text_source == "mineru" else "PDF text layer"
                        parts.append(f"[{tag} {label}]\n{p.text_layer[:settings.visual_context_chars]}")
        return "\n\n".join(parts)[: settings.visual_context_chars * 2]

    def crop_visual(self, page: PageData, block, book_id: str) -> Path | None:
        if not settings.save_visual_crops or block.content_type not in VISUAL_TYPES or not block.bbox:
            return None
        asset_id = stable_asset_id(book_id, page.pdf_page_number, block.sequence)
        path = self.assets_dir / book_id / f"{asset_id}.png"
        try:
            self.reader.crop_bbox(
                page,
                block.bbox.model_dump(),
                path,
                padding_px=settings.visual_crop_padding_px,
            )
            return path
        except Exception as exc:
            console.print(
                f"[yellow]Crop warning page {page.pdf_page_number}, block {block.sequence}: {exc}[/yellow]"
            )
            return None

    def _visual_search_fields(self, visual: VisualAnalysis | None) -> tuple[str | None, str | None, str | None, str, list[str], list[str], str | None]:
        if visual is None:
            return None, None, None, "", [], [], None
        text_items = [x.text for x in visual.visible_text if x.text]
        labels = [x.text for x in visual.labels if x.text]
        for entity in visual.entities:
            if entity.label:
                labels.append(entity.label)
            if entity.name:
                labels.append(entity.name)
        visual_text = " | ".join(dict.fromkeys(text_items + labels + visual.symbols + visual.equations))
        return (
            visual.visual_type,
            visual.visual_subtype,
            visual.summary,
            visual_text,
            list(dict.fromkeys(labels)),
            visual.concepts,
            visual.verification.status,
        )

    def _assign_question_ids(self, question: QuestionData, book_id: str, page_no: int, sequence: int) -> None:
        base = f"{book_id}-p{page_no:04d}-q{sequence:03d}"
        question.question_id = question.question_id or base

        def walk(parent: QuestionData, path: list[str]) -> None:
            for idx, child in enumerate(parent.children, start=1):
                token = (child.sub_number or child.number or str(idx)).strip().replace(" ", "-")
                child.question_id = child.question_id or f"{parent.question_id}-{token}"
                child.parent_question_id = parent.question_id
                walk(child, path + [token])

        walk(question, [])

    @staticmethod
    def _question_fields(question: QuestionData | None) -> dict[str, Any]:
        if question is None:
            return {
                "question_id": None,
                "question_parent_id": None,
                "question_number": None,
                "question_group": None,
                "question_scope": None,
                "question_format": None,
                "question_purpose": None,
                "question_bloom_level": None,
                "question_difficulty": None,
                "question_requires_visual": False,
                "question_requires_table": False,
                "question_requires_graph": False,
                "question_requires_map": False,
                "question_requires_passage": False,
                "question_requires_equation": False,
                "question_reference_ids": [],
                "question_reference_text": [],
            }
        return {
            "question_id": question.question_id,
            "question_parent_id": question.parent_question_id,
            "question_number": question.sub_number or question.number,
            "question_group": question.group_title,
            "question_scope": question.scope,
            "question_format": "composite" if question.children and question.format in {None, "open_ended"} else question.format,
            "question_purpose": question.purpose,
            "question_bloom_level": question.bloom_level,
            "question_difficulty": question.difficulty,
            "question_requires_visual": question.requires_visual,
            "question_requires_table": question.requires_table,
            "question_requires_graph": question.requires_graph,
            "question_requires_map": question.requires_map,
            "question_requires_passage": question.requires_passage,
            "question_requires_equation": question.requires_equation,
            "question_reference_ids": [r.target_id for r in question.references if r.target_id],
            "question_reference_text": [r.reference_text for r in question.references if r.reference_text],
        }

    def _expand_subquestions(self, base: IndexDocument, question: QuestionData) -> list[IndexDocument]:
        expanded: list[IndexDocument] = []

        def walk(parent: QuestionData) -> None:
            for child in parent.children:
                child_text = child.stem or child.instructions or ""
                qfields = self._question_fields(child)
                child_search = build_search_text(
                    base.book_title,
                    base.subject,
                    base.grade,
                    base.hierarchy_path,
                    base.title,
                    child.group_title,
                    child.scope,
                    child.format,
                    child.purpose,
                    child.bloom_level,
                    child_text,
                    [r.reference_text for r in child.references if r.reference_text],
                )
                child_doc_id = hashlib.sha256(
                    f"{base.id}|{child.question_id}|{child_text[:300]}".encode("utf-8", errors="ignore")
                ).hexdigest()[:32]
                data = base.model_dump(mode="python")
                data.update(
                    {
                        "id": child_doc_id,
                        "content_type": ContentType.QUESTION.value,
                        "subtype": "subquestion",
                        "text": child_text,
                        "normalized_text": normalize_general(child_text),
                        "search_text": child_search,
                        "question": child.model_dump(mode="json"),
                        "bloom_level": child.bloom_level or base.bloom_level,
                        "difficulty": child.difficulty or base.difficulty,
                        "asset_id": None,
                        "visual_type": None,
                        "visual_subtype": None,
                        "visual_summary": None,
                        "visual_text": "",
                        "visual_labels": [],
                        "visual_concepts": [],
                        "visual_verification_status": None,
                        "visual_analysis": None,
                        "asset_path": None,
                        **qfields,
                    }
                )
                # Child confidence combines source extraction and question classification.
                data["confidence"] = round(min(base.confidence, max(0.5, child.classification_confidence)), 4)
                data["quality_score"] = round(min(base.quality_score, 0.95), 4)
                expanded.append(IndexDocument.model_validate(data))
                walk(child)

        walk(question)
        return expanded

    def _link_question_references(self, docs: list[IndexDocument]) -> None:
        """Resolve explicit question references to asset/block IDs when possible.

        Resolution is conservative: explicit figure labels win; otherwise a unique compatible
        visual on the same page may be linked. Unresolved textual references are preserved.
        """
        by_page: dict[tuple[str, int], list[IndexDocument]] = {}
        for d in docs:
            by_page.setdefault((d.book_id, d.pdf_page_number), []).append(d)

        for d in docs:
            if not d.question:
                continue
            q = QuestionData.model_validate(d.question)
            page_docs = by_page.get((d.book_id, d.pdf_page_number), [])
            visuals = [x for x in page_docs if x.asset_id]
            changed = False
            for ref in q.references:
                if ref.target_id:
                    continue
                candidates = visuals
                rtype = (ref.reference_type or "").casefold()
                if rtype in {"graph", "table", "map", "figure", "visual_asset"}:
                    type_map = {
                        "graph": {"graph", "chart"},
                        "table": {"table"},
                        "map": {"map"},
                        "figure": {"figure", "diagram", "image", "timeline"},
                        "visual_asset": set(),
                    }
                    wanted = type_map.get(rtype, set())
                    if wanted:
                        typed = [x for x in candidates if (x.visual_type or x.content_type or "").casefold() in wanted or x.content_type in wanted]
                        if typed:
                            candidates = typed

                if ref.figure_label:
                    target = normalize_general(ref.figure_label)
                    labeled = [
                        x for x in candidates
                        if target and target in normalize_general(" ".join(filter(None, [x.figure_label, x.caption, x.title, x.visual_summary])))
                    ]
                    if len(labeled) == 1:
                        ref.target_id = labeled[0].asset_id or labeled[0].id
                        changed = True
                        continue
                if len(candidates) == 1 and rtype in {"graph", "table", "map", "figure", "visual_asset"}:
                    ref.target_id = candidates[0].asset_id or candidates[0].id
                    changed = True

            if changed:
                d.question = q.model_dump(mode="json")
            qfields = self._question_fields(q)
            for key, value in qfields.items():
                setattr(d, key, value)

    def _page_extraction_path(self, page_no: int) -> Path:
        return self.extracted_dir / f"page_{page_no:04d}.json"

    def _load_page_extraction(self, page_no: int) -> PageExtraction | None:
        path = self._page_extraction_path(page_no)
        if not path.exists():
            return None
        try:
            return PageExtraction.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _load_jsonl_documents(self, path: Path) -> list[IndexDocument]:
        docs: list[IndexDocument] = []
        if not path.exists():
            return docs
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                docs.append(IndexDocument.model_validate_json(line))
            except Exception:
                continue
        return docs

    def _append_jsonl(self, path: Path, docs: list[IndexDocument]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for doc in docs:
                f.write(doc.model_dump_json() + "\n")

    def _persist_checkpoint(self, checkpoint: JobCheckpoint) -> dict[str, Any]:
        return checkpoint.save(checkpoint_path(self.output_dir))

    def _build_page_documents(
        self,
        metadata: BookMetadata,
        book_id: str,
        page_ex: PageExtraction,
        hierarchy,
        resume: bool = True,
        cancel_check: CancelCheck | None = None,
    ) -> list[IndexDocument]:
        docs: list[IndexDocument] = []
        if cancel_check and cancel_check():
            raise JobCancelled("Extraction job was stopped")
        page_data = self.reader.render_page(page_ex.pdf_page_number)
        hierarchy_path = hierarchy_path_from(hierarchy)

        for block in page_ex.blocks:
            if cancel_check and cancel_check():
                raise JobCancelled("Extraction job was stopped")
            if block.question:
                self._assign_question_ids(block.question, book_id, page_ex.pdf_page_number, block.sequence)

            asset_path: Path | None = None
            asset_id: str | None = None
            visual: VisualAnalysis | None = None

            if block.content_type in VISUAL_TYPES and block.bbox:
                asset_id = stable_asset_id(book_id, page_ex.pdf_page_number, block.sequence)
                asset_path = self.crop_visual(page_data, block, book_id)
                if settings.deep_visual_analysis and asset_path is not None:
                    context = self._context_for_asset(page_ex.pdf_page_number, page_ex, block.sequence)
                    try:
                        visual = self.visual_analyzer.analyze(
                            asset_id=asset_id,
                            crop_path=asset_path,
                            page=page_data,
                            printed_page_number=page_ex.printed_page_number,
                            block=block,
                            metadata=metadata,
                            hierarchy=hierarchy,
                            context=context,
                            resume=resume,
                        )
                    except Exception as exc:
                        page_ex.extraction_notes.append(f"visual_analysis_failed:{asset_id}:{exc!r}")
                        console.print(f"[yellow]Visual analysis failed for {asset_id}: {exc}[/yellow]")

            visual_type, visual_subtype, visual_summary, visual_text, visual_labels, visual_concepts, verification_status = self._visual_search_fields(visual)
            text = block.verbatim_text or ""
            mineru_page = self.reader.mineru.page(page_ex.pdf_page_number) if self.reader.mineru is not None else None
            ocr_text = (mineru_page.text if mineru_page is not None else "") or page_data.text_layer
            ocr_source = "mineru" if mineru_page is not None else (page_data.text_source or "pdf")
            normalized = normalize_general(text)
            search_text = build_search_text(
                metadata.title,
                metadata.subject,
                metadata.grade,
                hierarchy_path,
                block.title,
                text,
                ocr_text,
                block.concise_description,
                block.concepts,
                block.keywords,
                block.aliases,
                block.caption,
                block.figure_label,
                visual_type,
                visual_subtype,
                visual_summary,
                visual_text,
                visual_labels,
                visual_concepts,
                block.question.group_title if block.question else None,
                block.question.scope if block.question else None,
                block.question.format if block.question else None,
                block.question.purpose if block.question else None,
                block.question.bloom_level if block.question else None,
                [r.reference_text for r in block.question.references if r.reference_text] if block.question else [],
            )
            ctype = block.content_type.value
            doc_id = stable_block_id(book_id, page_ex.pdf_page_number, block.sequence, text, ctype)
            quality = block_quality_score(block, visual)
            qfields = self._question_fields(block.question)

            docs.append(
                IndexDocument(
                    id=doc_id,
                    book_id=book_id,
                    book_title=metadata.title or self.pdf_path.stem,
                    country=metadata.country,
                    curriculum=metadata.curriculum,
                    education_system=metadata.education_system,
                    grade=metadata.grade,
                    subject=metadata.subject,
                    semester=metadata.semester,
                    academic_year=metadata.academic_year,
                    language=block.language or page_ex.page_language or metadata.language,
                    pdf_page_number=page_ex.pdf_page_number,
                    printed_page_number=page_ex.printed_page_number,
                    unit_title=hierarchy.unit_title,
                    chapter_title=hierarchy.chapter_title,
                    lesson_title=hierarchy.lesson_title,
                    section_title=hierarchy.section_title,
                    unit_id=getattr(hierarchy, "unit_id", None),
                    chapter_id=getattr(hierarchy, "chapter_id", None),
                    lesson_id=getattr(hierarchy, "lesson_id", None),
                    hierarchy_path=hierarchy_path,
                    sequence=block.sequence,
                    content_type=ctype,
                    subtype=block.subtype,
                    title=block.title,
                    text=text,
                    normalized_text=normalized,
                    search_text=search_text,
                    ocr_text=ocr_text,
                    ocr_source=ocr_source,
                    text_source=page_data.text_source,
                    concepts=block.concepts,
                    keywords=block.keywords,
                    aliases=block.aliases,
                    skills=block.skills,
                    prerequisites=block.prerequisites,
                    difficulty=block.difficulty,
                    bloom_level=block.bloom_level,
                    importance=block.importance,
                    question=block.question.model_dump(mode="json") if block.question else None,
                    **qfields,
                    graph=block.graph.model_dump() if block.graph else None,
                    table=block.table.model_dump() if block.table else None,
                    figure_label=block.figure_label,
                    caption=block.caption,
                    cross_references=block.cross_references,
                    asset_id=asset_id,
                    visual_type=visual_type,
                    visual_subtype=visual_subtype,
                    visual_summary=visual_summary,
                    visual_text=visual_text,
                    visual_labels=visual_labels,
                    visual_concepts=visual_concepts,
                    visual_verification_status=verification_status,
                    visual_analysis=visual.model_dump(mode="json") if visual else None,
                    bbox=block.bbox.model_dump() if block.bbox else None,
                    asset_path=str(asset_path) if asset_path else None,
                    page_image_path=str(page_data.image_path),
                    source_pdf_path=str(self.pdf_path),
                    confidence=block.confidence,
                    quality_score=quality,
                    extraction_notes=page_ex.extraction_notes,
                )
            )
            if block.question and block.question.children:
                docs.extend(self._expand_subquestions(docs[-1], block.question))

        self._link_question_references(docs)
        return docs

    @staticmethod
    def _is_ocr_document(doc: IndexDocument) -> bool:
        return doc.content_type == ContentType.OCR_PAGE.value or doc.subtype == "ocr_block"

    @staticmethod
    def _hierarchy_fields(ctx: HierarchyContext) -> dict[str, Any]:
        return {
            "unit_title": ctx.unit_title,
            "chapter_title": ctx.chapter_title,
            "lesson_title": ctx.lesson_title,
            "section_title": ctx.section_title,
            "unit_id": ctx.unit_id,
            "chapter_id": ctx.chapter_id,
            "lesson_id": ctx.lesson_id,
            "hierarchy_path": hierarchy_path_from(ctx),
        }

    def _build_ocr_documents(
        self,
        metadata: BookMetadata,
        book_id: str,
        page_no: int,
        hierarchy: HierarchyContext | None = None,
    ) -> list[IndexDocument]:
        mineru_page = self.reader.mineru.page(page_no) if self.reader.mineru is not None else None
        page_data = self.reader.render_page(page_no)
        if mineru_page is None:
            mineru_page = MinerUPage(pdf_page_number=page_no)

        ocr_text = repair_arabic_ocr(page_data.text_layer or mineru_page.text or "")
        indexable_blocks = [block for block in mineru_page.blocks if mineru_block_is_indexable(block)]
        ocr_source = page_data.text_source or (
            "mineru" if self.reader.mineru is not None and self.reader.mineru.page(page_no) else "pdf"
        )
        language = metadata.language
        notes = ["mineru_ocr"] if ocr_source == "mineru" else ["pdf_text_layer"]
        if ocr_page_is_sparse(ocr_text, len(indexable_blocks), settings.ocr_min_chars):
            notes.append("empty_page" if not (ocr_text or "").strip() else "sparse_ocr")
        quality = ocr_page_quality_score(ocr_text, len(indexable_blocks), ocr_source, settings.ocr_min_chars)
        ctx = hierarchy or HierarchyContext()
        path = hierarchy_path_from(ctx)
        docs: list[IndexDocument] = []
        page_id = stable_block_id(book_id, page_no, 0, ocr_text or f"ocr-page-{page_no}", ContentType.OCR_PAGE.value)
        docs.append(
            IndexDocument(
                id=page_id,
                book_id=book_id,
                book_title=metadata.title or self.pdf_path.stem,
                country=metadata.country,
                curriculum=metadata.curriculum,
                education_system=metadata.education_system,
                grade=metadata.grade,
                subject=metadata.subject,
                semester=metadata.semester,
                academic_year=metadata.academic_year,
                language=language,
                pdf_page_number=page_no,
                **self._hierarchy_fields(ctx),
                sequence=0,
                content_type=ContentType.OCR_PAGE.value,
                subtype="ocr_page",
                title=f"OCR page {page_no}",
                text=ocr_text,
                normalized_text=normalize_general(ocr_text),
                search_text=build_search_text(metadata.title, metadata.subject, metadata.grade, path, ocr_text),
                ocr_text=ocr_text,
                ocr_source=ocr_source,
                text_source=page_data.text_source,
                page_image_path=str(page_data.image_path),
                source_pdf_path=str(self.pdf_path),
                confidence=quality,
                quality_score=quality,
                extraction_notes=notes,
            )
        )
        seq = 0
        for block in indexable_blocks:
            seq += 1
            text = repair_arabic_ocr(block.text or "")
            if not text:
                continue
            ctype = mineru_content_type(block)
            caption = str(block.extra.get("caption") or "") or None
            search_text = build_search_text(metadata.title, metadata.subject, metadata.grade, path, ctype, text, caption)
            docs.append(
                IndexDocument(
                    id=stable_block_id(book_id, page_no, seq, f"ocr|{text}", ctype),
                    book_id=book_id,
                    book_title=metadata.title or self.pdf_path.stem,
                    country=metadata.country,
                    curriculum=metadata.curriculum,
                    education_system=metadata.education_system,
                    grade=metadata.grade,
                    subject=metadata.subject,
                    semester=metadata.semester,
                    academic_year=metadata.academic_year,
                    language=language,
                    pdf_page_number=page_no,
                    **self._hierarchy_fields(ctx),
                    sequence=seq,
                    content_type=ctype,
                    subtype="ocr_block",
                    title=text[:180] if ctype in {"unit_title", "chapter_title", "lesson_title", "section_heading"} else None,
                    text=text,
                    normalized_text=normalize_general(text),
                    search_text=search_text,
                    ocr_text=text,
                    ocr_source=ocr_source,
                    text_source=page_data.text_source,
                    caption=caption,
                    bbox=mineru_bbox_dict(block),
                    page_image_path=str(page_data.image_path),
                    source_pdf_path=str(self.pdf_path),
                    confidence=0.88,
                    quality_score=0.88,
                    extraction_notes=["mineru_ocr_block"],
                )
            )
        return docs

    def _page_has_sparse_ocr(self, page_no: int) -> bool:
        mineru_page = self.reader.mineru.page(page_no) if self.reader.mineru is not None else None
        if mineru_page is None:
            page_data = self.reader.render_page(page_no)
            return ocr_page_is_sparse(page_data.text_layer, 0, settings.ocr_min_chars)
        indexable = sum(1 for block in mineru_page.blocks if mineru_block_is_indexable(block))
        return ocr_page_is_sparse(mineru_page.text, indexable, settings.ocr_min_chars)

    def _ensure_mineru_page(
        self,
        page_no: int,
        *,
        language: str | None,
        resume: bool,
        emit,
        persist,
        check_cancel,
        checkpoint: JobCheckpoint,
        force: bool = False,
        progress_value: float = 6.0,
    ) -> None:
        if not settings.mineru_enabled:
            return
        if (
            not force
            and self.reader.mineru is not None
            and self.reader.mineru.page(page_no) is not None
        ):
            checkpoint.mark_mineru(page_no)
            return
        check_cancel()
        emit(
                "mineru_parse",
                progress_value,
                f"Parsing page {page_no} with MinerU",
                current_page=page_no,
        )
        try:
            document = parse_pdf_with_mineru(
                self.pdf_path,
                self.output_dir,
                start_page=page_no,
                end_page=page_no,
                language=language,
                resume=resume,
                progress=lambda message: emit("mineru_parse", progress_value, message, current_page=page_no),
                artifact_dir=mineru_page_artifact_dir(self.output_dir, page_no),
            )
        except MinerUError as exc:
            if settings.mineru_required:
                raise
            console.print(f"[yellow]MinerU unavailable on page {page_no} ({exc}); using PDF text layer[/yellow]")
            emit("mineru_parse", progress_value, f"MinerU unavailable on page {page_no}; using PDF text", current_page=page_no)
            return
        self.reader.attach_mineru(document)
        checkpoint.mark_mineru(page_no)
        persist("mineru_parse", page_no)

    def _index_mineru_ocr(
        self,
        *,
        metadata: BookMetadata,
        book_id: str,
        start_page: int,
        end_page: int,
        jsonl_path: Path,
        docs_by_page: dict[int, list[IndexDocument]],
        existing_ids: set[str],
        resume: bool,
        emit,
        persist,
        check_cancel,
        page_docs_callback: PageDocsCallback | None,
        checkpoint: JobCheckpoint,
        language: str | None,
        ocr_end_progress: float = 40.0,
    ) -> list[IndexDocument]:
        indexed: list[IndexDocument] = []
        requested = max(1, end_page - start_page + 1)
        cached = load_incremental_mineru_document(self.output_dir)
        if cached and cached.pages:
            self.reader.attach_mineru(cached)
            for page_no in cached.pages:
                checkpoint.mark_mineru(page_no)
            persist("mineru_parse")
            emit("mineru_parse", 6.0, f"Loaded {len(cached.pages)} cached MinerU pages")

        resolver = HierarchyResolver(book_id=book_id)
        ocr_span = max(1.0, float(ocr_end_progress) - 6.0)
        for ordinal, page_no in enumerate(range(start_page, end_page + 1), start=1):
            check_cancel()
            ocr_progress = 6.0 + (ocr_span * ordinal / requested)
            existing = [d for d in docs_by_page.get(page_no, []) if self._is_ocr_document(d)]
            already_ocr = resume and page_no in checkpoint.ocr_pages and bool(existing)
            if already_ocr:
                indexed.extend(existing)
                for doc in existing:
                    resolver.fill_missing(
                        unit=doc.unit_title,
                        chapter=doc.chapter_title,
                        lesson=doc.lesson_title,
                        section=doc.section_title,
                    )
                emit(
                    "ocr_index",
                    ocr_progress,
                    f"Resumed OCR page {page_no} of {end_page}",
                    current_page=page_no,
                    total_pages=requested,
                )
                continue

            self._ensure_mineru_page(
                page_no,
                language=language,
                resume=resume,
                emit=emit,
                persist=persist,
                check_cancel=check_cancel,
                checkpoint=checkpoint,
                progress_value=ocr_progress,
            )
            if settings.ocr_retry_empty and settings.mineru_enabled and self._page_has_sparse_ocr(page_no):
                self._ensure_mineru_page(
                    page_no,
                    language=language,
                    resume=False,
                    emit=emit,
                    persist=persist,
                    check_cancel=check_cancel,
                    checkpoint=checkpoint,
                    force=True,
                    progress_value=ocr_progress,
                )

            mineru_page = self.reader.mineru.page(page_no) if self.reader.mineru is not None else None
            page_data = self.reader.render_page(page_no)
            if mineru_page is not None:
                for block in mineru_page.blocks:
                    resolver.apply_ocr_text(block.text, content_type=mineru_content_type(block), title=block.text[:120])
            resolver.apply_ocr_text(page_data.text_layer)
            page_docs = existing or self._build_ocr_documents(
                metadata, book_id, page_no, hierarchy=resolver.current
            )
            new_docs = [d for d in page_docs if d.id not in existing_ids]
            if new_docs:
                self._append_jsonl(jsonl_path, new_docs)
                docs_by_page.setdefault(page_no, []).extend(new_docs)
                existing_ids.update(d.id for d in new_docs)
                page_docs = [d for d in docs_by_page.get(page_no, []) if self._is_ocr_document(d)]

            def _push_to_opensearch() -> None:
                if page_docs_callback:
                    page_docs_callback(page_no, page_docs)

            try:
                _push_to_opensearch()
            except JobCancelled:
                raise
            except Exception as exc:
                try:
                    _push_to_opensearch()
                except JobCancelled:
                    raise
                except Exception:
                    error = {"pdf_page_number": page_no, "stage": "ocr_index", "error": repr(exc)}
                    with (self.output_dir / "errors.jsonl").open("a", encoding="utf-8") as f:
                        f.write(json.dumps(error, ensure_ascii=False) + "\n")
                    console.print(f"[red]OpenSearch OCR index failed on page {page_no}: {exc}[/red]")
                    checkpoint.mark_failed(page_no)
                    persist("ocr_index", page_no)
                    continue

            checkpoint.mark_ocr(page_no)
            checkpoint.extracted_records = sum(len(v) for v in docs_by_page.values())
            persist("ocr_index", page_no)
            indexed.extend(page_docs)
            emit(
                "ocr_index",
                ocr_progress,
                f"Indexed page {page_no} of {end_page} into OpenSearch",
                current_page=page_no,
                total_pages=requested,
            )
        return indexed

    def build_documents(
        self,
        metadata: BookMetadata,
        book_id: str,
        extractions: list[PageExtraction],
        resume: bool = True,
        progress_callback: ProgressCallback | None = None,
        cancel_check: CancelCheck | None = None,
    ) -> list[IndexDocument]:
        resolver = HierarchyResolver()
        docs: list[IndexDocument] = []
        ordered_pages = sorted(extractions, key=lambda p: p.pdf_page_number)
        total_pages = max(1, len(ordered_pages))

        for page_idx, page_ex in enumerate(ordered_pages, start=1):
            if cancel_check and cancel_check():
                raise JobCancelled("Extraction job was stopped")
            hierarchy = resolver.apply_page(page_ex)
            docs.extend(
                self._build_page_documents(
                    metadata,
                    book_id,
                    page_ex,
                    hierarchy,
                    resume=resume,
                    cancel_check=cancel_check,
                )
            )

            if progress_callback:
                progress_callback({
                    "stage": "visual_analysis",
                    "progress": 65.0 + (25.0 * page_idx / total_pages),
                    "current_page": page_ex.pdf_page_number,
                    "total_pages": total_pages,
                    "message": f"Built structured records for page {page_ex.pdf_page_number}",
                })

        self._link_question_references(docs)
        return docs

    def _write_run_artifacts(
        self,
        *,
        book_id: str,
        metadata: BookMetadata,
        extractions: list[PageExtraction],
        docs: list[IndexDocument],
        start_page: int,
        end_page: int,
        jsonl_path: Path,
    ) -> None:
        content_type_counts: dict[str, int] = {}
        visual_type_counts: dict[str, int] = {}
        verification_counts: dict[str, int] = {}
        question_scope_counts: dict[str, int] = {}
        question_format_counts: dict[str, int] = {}
        question_purpose_counts: dict[str, int] = {}
        question_bloom_counts: dict[str, int] = {}
        for doc in docs:
            content_type_counts[doc.content_type] = content_type_counts.get(doc.content_type, 0) + 1
            if doc.visual_type:
                visual_type_counts[doc.visual_type] = visual_type_counts.get(doc.visual_type, 0) + 1
            if doc.visual_verification_status:
                verification_counts[doc.visual_verification_status] = verification_counts.get(
                    doc.visual_verification_status, 0
                ) + 1
            if doc.question_scope:
                question_scope_counts[doc.question_scope] = question_scope_counts.get(doc.question_scope, 0) + 1
            if doc.question_format:
                question_format_counts[doc.question_format] = question_format_counts.get(doc.question_format, 0) + 1
            if doc.question_purpose:
                question_purpose_counts[doc.question_purpose] = question_purpose_counts.get(doc.question_purpose, 0) + 1
            if doc.question_bloom_level:
                question_bloom_counts[doc.question_bloom_level] = question_bloom_counts.get(
                    doc.question_bloom_level, 0
                ) + 1

        processed_page_numbers = {p.pdf_page_number for p in extractions}
        empty_pages = [p.pdf_page_number for p in extractions if not p.blocks]
        ocr_page_docs = [d for d in docs if d.content_type == ContentType.OCR_PAGE.value]
        ocr_pages_present = {d.pdf_page_number for d in ocr_page_docs}
        empty_ocr_pages = sorted(
            d.pdf_page_number for d in ocr_page_docs if "empty_page" in (d.extraction_notes or [])
        )
        sparse_ocr_pages = sorted(
            d.pdf_page_number for d in ocr_page_docs if "sparse_ocr" in (d.extraction_notes or [])
        )
        ckpt = JobCheckpoint.load(checkpoint_path(self.output_dir))
        low_confidence = [
            {"id": d.id, "page": d.pdf_page_number, "type": d.content_type, "quality_score": d.quality_score}
            for d in docs
            if d.quality_score < 0.55
        ]
        problematic_visuals = [
            {
                "id": d.id,
                "asset_id": d.asset_id,
                "page": d.pdf_page_number,
                "visual_type": d.visual_type,
                "verification_status": d.visual_verification_status,
            }
            for d in docs
            if d.asset_id and settings.verify_visual_analysis and d.visual_verification_status != "passed"
        ]
        visual_docs = [d for d in docs if d.asset_id]
        ocr_stats = ocr_completeness(
            start_page=start_page,
            end_page=end_page,
            ocr_pages=ocr_pages_present,
            empty_pages=empty_ocr_pages,
            sparse_pages=sparse_ocr_pages,
            failed_pages=list(ckpt.failed_pages) if ckpt else [],
        )
        vlm_ran = bool(extractions)
        vlm_recommended = (
            (not vlm_ran)
            or (
                len(processed_page_numbers) == (end_page - start_page + 1)
                and len(empty_pages) == 0
                and (len(low_confidence) / max(1, len(docs))) <= 0.05
                and (len(problematic_visuals) / max(1, len(visual_docs))) <= 0.05
            )
        )
        requested = max(1, end_page - start_page + 1)
        quality_report = {
            "book_id": book_id,
            "source_page_count": self.reader.page_count,
            "processed_pages": len(processed_page_numbers),
            "processing_coverage": round(len(processed_page_numbers) / requested, 4),
            "empty_extracted_pages": empty_pages,
            "low_confidence_blocks_count": len(low_confidence),
            "low_confidence_blocks": low_confidence[:500],
            "content_type_counts": dict(sorted(content_type_counts.items())),
            "question_scope_counts": dict(sorted(question_scope_counts.items())),
            "question_format_counts": dict(sorted(question_format_counts.items())),
            "question_purpose_counts": dict(sorted(question_purpose_counts.items())),
            "question_bloom_counts": dict(sorted(question_bloom_counts.items())),
            "questions_count": sum(1 for d in docs if d.content_type == ContentType.QUESTION.value),
            "subquestions_count": sum(1 for d in docs if d.subtype == "subquestion"),
            "ocr_pages_count": sum(1 for d in docs if d.content_type == ContentType.OCR_PAGE.value),
            "ocr_blocks_count": sum(1 for d in docs if d.subtype == "ocr_block"),
            "ocr_coverage": ocr_stats["ocr_coverage"],
            "missing_ocr_pages": ocr_stats["missing_ocr_pages"],
            "empty_ocr_pages": ocr_stats["empty_ocr_pages"],
            "sparse_ocr_pages": ocr_stats["sparse_ocr_pages"],
            "failed_ocr_pages": ocr_stats["failed_ocr_pages"],
            "ocr_complete": ocr_stats["ocr_complete"],
            "visual_type_counts": dict(sorted(visual_type_counts.items())),
            "visual_verification_counts": dict(sorted(verification_counts.items())),
            "visual_assets_count": len(visual_docs),
            "problematic_visual_assets_count": len(problematic_visuals),
            "problematic_visual_assets": problematic_visuals[:500],
            "detected_units": sorted({d.unit_title for d in docs if d.unit_title}),
            "detected_chapters": sorted({d.chapter_title for d in docs if d.chapter_title}),
            "detected_lessons": sorted({d.lesson_title for d in docs if d.lesson_title}),
            "printed_page_numbers_detected": sum(1 for p in extractions if p.printed_page_number),
            "recommended_for_live_index": bool(ocr_stats["recommended_for_live_index"] and vlm_recommended),
        }
        (self.output_dir / "quality_report.json").write_text(
            json.dumps(quality_report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        outline = build_content_tree(book_id, docs)
        structure = {
            "book_id": book_id,
            "units": sorted({d.unit_title for d in docs if d.unit_title}),
            "chapter_titles": sorted({d.chapter_title for d in docs if d.chapter_title}),
            "lesson_titles": sorted({d.lesson_title for d in docs if d.lesson_title}),
            "sections": sorted({d.section_title for d in docs if d.section_title}),
            "tree": outline["chapters"],
            "hierarchy_events": [
                {
                    "pdf_page_number": p.pdf_page_number,
                    "printed_page_number": p.printed_page_number,
                    "unit": p.explicit_unit_title,
                    "chapter": p.explicit_chapter_title,
                    "lesson": p.explicit_lesson_title,
                    "section": p.explicit_section_title,
                }
                for p in sorted(extractions, key=lambda x: x.pdf_page_number)
                if any(
                    [
                        p.explicit_unit_title,
                        p.explicit_chapter_title,
                        p.explicit_lesson_title,
                        p.explicit_section_title,
                    ]
                )
            ],
        }
        (self.output_dir / "structure.json").write_text(
            json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (self.output_dir / "outline.json").write_text(
            json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest = {
            "schema_version": 3,
            "book_id": book_id,
            "source_pdf": str(self.pdf_path),
            "text_parser": "mineru" if self.reader.mineru is not None else "pymupdf",
            "mineru_source": getattr(self.reader.mineru, "source", None),
            "mineru_backend": getattr(self.reader.mineru, "backend", None),
            "page_count": self.reader.page_count,
            "processed_pages": len(extractions),
            "indexed_blocks": len(docs),
            "ocr_records": sum(1 for d in docs if d.content_type == ContentType.OCR_PAGE.value or d.subtype == "ocr_block"),
            "visual_assets": len(visual_docs),
            "metadata": metadata.model_dump(),
            "documents_jsonl": str(jsonl_path),
            "quality_report": str(self.output_dir / "quality_report.json"),
            "structure": str(self.output_dir / "structure.json"),
            "outline": str(self.output_dir / "outline.json"),
            "checkpoint": str(checkpoint_path(self.output_dir)),
        }
        (self.output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def run(
        self,
        overrides: dict[str, Any],
        start_page: int = 1,
        end_page: int | None = None,
        resume: bool = True,
        progress_callback: ProgressCallback | None = None,
        cancel_check: CancelCheck | None = None,
        page_docs_callback: PageDocsCallback | None = None,
        ocr_only: bool = False,
    ) -> tuple[BookMetadata, str, list[IndexDocument]]:
        jsonl_path = self.index_dir / "documents.jsonl"
        ckpt_file = checkpoint_path(self.output_dir)
        checkpoint = JobCheckpoint.load_or_new(ckpt_file) if resume else JobCheckpoint()
        if resume:
            checkpoint.hydrate_from_artifacts(
                self.extracted_dir,
                jsonl_path,
                mineru_pages_dir=self.output_dir / "mineru_pages",
            )
        elif jsonl_path.exists():
            jsonl_path.unlink()

        skip_vlm = ocr_only or not settings.vlm_page_extraction_enabled

        def emit(
            stage: str,
            progress: float,
            message: str,
            current_page: int | None = None,
            total_pages: int | None = None,
        ) -> None:
            if progress_callback:
                progress_callback(
                    {
                        "stage": stage,
                        "progress": round(float(progress), 2),
                        "message": message,
                        "current_page": current_page,
                        "total_pages": total_pages,
                        "checkpoint": checkpoint.to_dict(),
                    }
                )

        def persist(stage: str, current_page: int | None = None) -> dict[str, Any]:
            checkpoint.stage = stage
            if current_page is not None:
                checkpoint.current_page = current_page
            return self._persist_checkpoint(checkpoint)

        def check_cancel() -> None:
            if cancel_check and cancel_check():
                persist(checkpoint.stage or "paused", checkpoint.current_page)
                raise JobCancelled("Extraction job was stopped")

        check_cancel()
        if start_page > self.reader.page_count:
            raise ValueError(f"start_page {start_page} exceeds PDF page count {self.reader.page_count}")
        end_page = min(end_page or self.reader.page_count, self.reader.page_count)
        if end_page < start_page:
            raise ValueError("end_page must be greater than or equal to start_page")
        check_cancel()
        meta_path = self.output_dir / "book_metadata.final.json"
        detected: BookMetadata | None = None
        if resume and meta_path.exists():
            try:
                detected = BookMetadata.model_validate_json(meta_path.read_text(encoding="utf-8"))
                emit("metadata", 4.0, "Resuming with saved metadata")
            except Exception:
                detected = None

        if detected is None and skip_vlm:
            emit("metadata", 4.0, "Using catalog/filename metadata (OCR-only)")
            detected = BookMetadata(
                title=self.pdf_path.stem,
                language=str(overrides.get("language") or "ar"),
                confidence=0.3,
            )
        elif detected is None:
            emit("metadata", 1.0, "Detecting textbook metadata")
            try:
                detected = self.detect_metadata()
            except JobCancelled:
                raise
            except Exception as exc:
                fallback = {
                    "stage": "metadata_detection",
                    "error": str(exc),
                    "fallback": "catalog_and_filename",
                }
                with (self.output_dir / "errors.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(fallback, ensure_ascii=False) + "\n")
                console.print(
                    f"[yellow]Metadata detection failed ({exc}); continuing with catalog metadata[/yellow]"
                )
                emit("metadata", 3.0, "Vision metadata failed; using catalog data")
                detected = BookMetadata(title=self.pdf_path.stem, confidence=0.2)

        metadata = merge_metadata(detected, overrides)
        resource_id = str(overrides.get("book_resource_id") or "").strip()
        book_id = resource_id or checkpoint.book_id or stable_book_id(self.pdf_path, metadata)
        checkpoint.book_id = book_id
        checkpoint.metadata = metadata.model_dump()
        meta_path.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
        persist("metadata")
        emit("metadata", 5.0, "Metadata detected", total_pages=self.reader.page_count)
        check_cancel()

        requested_pages = max(1, end_page - start_page + 1)
        checkpoint.start_page = start_page
        checkpoint.end_page = end_page
        checkpoint.total_pages = requested_pages

        existing_docs = self._load_jsonl_documents(jsonl_path) if resume else []
        docs_by_page: dict[int, list[IndexDocument]] = {}
        for doc in existing_docs:
            docs_by_page.setdefault(doc.pdf_page_number, []).append(doc)
        existing_ids = {d.id for d in existing_docs}
        vlm_jsonl_pages = {
            page
            for page, page_docs in docs_by_page.items()
            if any(not self._is_ocr_document(d) for d in page_docs)
        }

        emit("ocr_index", 5.2, "Indexing page content into OpenSearch", total_pages=requested_pages)
        ocr_docs = self._index_mineru_ocr(
            metadata=metadata,
            book_id=book_id,
            start_page=start_page,
            end_page=end_page,
            jsonl_path=jsonl_path,
            docs_by_page=docs_by_page,
            existing_ids=existing_ids,
            resume=resume,
            emit=emit,
            persist=persist,
            check_cancel=check_cancel,
            page_docs_callback=page_docs_callback,
            checkpoint=checkpoint,
            language=str(overrides.get("language") or metadata.language or "") or None,
            ocr_end_progress=88.0 if skip_vlm else 40.0,
        )
        persist("ocr_index")
        emit("ocr_index", 88.0 if skip_vlm else 40.0, f"Stored {len(ocr_docs)} OCR records", total_pages=requested_pages)
        check_cancel()

        resolver = HierarchyResolver(book_id=book_id)
        extractions_by_page: dict[int, PageExtraction] = {}
        all_docs: list[IndexDocument] = list(ocr_docs)
        if skip_vlm:
            emit("ocr_index", 90.0, "OCR-only mode: skipping VLM page extraction", total_pages=requested_pages)
            check_cancel()
            emit("artifact_generation", 91.0, "Writing extraction artifacts")
            docs = self._load_jsonl_documents(jsonl_path) or all_docs
            checkpoint.extracted_records = len(docs)
            checkpoint.indexed_records = len(docs)
            checkpoint.visual_assets = sum(1 for d in docs if d.asset_id)
            self._write_run_artifacts(
                book_id=book_id,
                metadata=metadata,
                extractions=[],
                docs=docs,
                start_page=start_page,
                end_page=end_page,
                jsonl_path=jsonl_path,
            )
            persist("extraction_complete")
            emit("extraction_complete", 95.0, "Page OCR indexed; records already in OpenSearch")
            return metadata, book_id, docs

        if resume:
            for page_no in range(start_page, end_page + 1):
                loaded = self._load_page_extraction(page_no)
                if loaded is not None:
                    extractions_by_page[page_no] = loaded

        console.print("[cyan]Extracting, classifying, and indexing pages incrementally...[/cyan]")

        for ordinal, page_no in enumerate(range(start_page, end_page + 1), start=1):
            check_cancel()
            checkpoint.current_page = page_no
            progress = 40.0 + (50.0 * ordinal / requested_pages)
            page_ex = extractions_by_page.get(page_no)
            already_extracted = page_ex is not None or page_no in checkpoint.extracted_pages
            already_in_jsonl = page_no in vlm_jsonl_pages
            already_indexed = page_no in checkpoint.indexed_pages

            if already_extracted and page_ex is None:
                page_ex = self._load_page_extraction(page_no)
                if page_ex is None:
                    already_extracted = False

            if not already_extracted:
                page = self.reader.render_page(page_no)
                try:
                    page_ex = self.extract_page(page, metadata, resume=resume)
                except JobCancelled:
                    raise
                except Exception as exc:
                    error = {"pdf_page_number": page_no, "stage": "page_extraction", "error": repr(exc)}
                    with (self.output_dir / "errors.jsonl").open("a", encoding="utf-8") as f:
                        f.write(json.dumps(error, ensure_ascii=False) + "\n")
                    console.print(f"[red]Page {page_no} failed: {exc}[/red]")
                    checkpoint.mark_failed(page_no)
                    persist("page_extraction", page_no)
                    emit(
                        "page_extraction",
                        progress,
                        f"Failed page {page_no} of {end_page}",
                        current_page=page_no,
                        total_pages=requested_pages,
                    )
                    continue
                checkpoint.mark_extracted(page_no)
                persist("page_extraction", page_no)

            assert page_ex is not None
            extractions_by_page[page_no] = page_ex
            window = [extractions_by_page[p] for p in sorted(extractions_by_page) if p <= page_no]
            lookahead = [extractions_by_page[p] for p in sorted(extractions_by_page) if p > page_no]
            if lookahead:
                window = window + lookahead[:1]
            self.question_intelligence.enrich_pages(window)
            page_ex = extractions_by_page[page_no]
            self._page_extraction_path(page_no).write_text(
                page_ex.model_dump_json(indent=2), encoding="utf-8"
            )

            hierarchy = resolver.apply_page(page_ex)
            if already_indexed:
                page_docs = [d for d in docs_by_page.get(page_no, []) if not self._is_ocr_document(d)]
                if not page_docs:
                    page_docs = self._build_page_documents(
                        metadata,
                        book_id,
                        page_ex,
                        hierarchy,
                        resume=resume,
                        cancel_check=cancel_check,
                    )
                    if page_docs_callback:
                        page_docs_callback(page_no, page_docs)
                    self._append_jsonl(jsonl_path, page_docs)
                    ocr_kept = [d for d in docs_by_page.get(page_no, []) if self._is_ocr_document(d)]
                    docs_by_page[page_no] = ocr_kept + page_docs
                    vlm_jsonl_pages.add(page_no)
                all_docs.extend(page_docs)
                emit(
                    "page_extraction",
                    progress,
                    f"Resumed page {page_no} of {end_page} (already indexed)",
                    current_page=page_no,
                    total_pages=requested_pages,
                )
                continue

            if already_in_jsonl:
                page_docs = [d for d in docs_by_page.get(page_no, []) if not self._is_ocr_document(d)]
                if page_docs_callback:
                    page_docs_callback(page_no, page_docs)
                all_docs.extend(page_docs)
                checkpoint.mark_indexed(page_no)
                checkpoint.extracted_records = len(all_docs)
                checkpoint.indexed_records = len(all_docs)
                checkpoint.visual_assets = sum(1 for d in all_docs if d.asset_id)
                persist("indexing", page_no)
                emit(
                    "indexing",
                    progress,
                    f"Re-indexed saved page {page_no} of {end_page}",
                    current_page=page_no,
                    total_pages=requested_pages,
                )
                continue

            page_docs = self._build_page_documents(
                metadata,
                book_id,
                page_ex,
                hierarchy,
                resume=resume,
                cancel_check=cancel_check,
            )
            if page_docs_callback:
                page_docs_callback(page_no, page_docs)
            self._append_jsonl(jsonl_path, page_docs)
            ocr_kept = [d for d in docs_by_page.get(page_no, []) if self._is_ocr_document(d)]
            docs_by_page[page_no] = ocr_kept + page_docs
            vlm_jsonl_pages.add(page_no)
            all_docs.extend(page_docs)
            checkpoint.mark_indexed(page_no)
            checkpoint.extracted_records = len(all_docs)
            checkpoint.indexed_records = len(all_docs)
            checkpoint.visual_assets = sum(1 for d in all_docs if d.asset_id)
            persist("indexing", page_no)
            emit(
                "indexing",
                progress,
                f"Extracted and indexed page {page_no} of {end_page}",
                current_page=page_no,
                total_pages=requested_pages,
            )

        check_cancel()
        emit("artifact_generation", 91.0, "Writing extraction artifacts")
        docs = self._load_jsonl_documents(jsonl_path) or all_docs
        extractions = [extractions_by_page[p] for p in sorted(extractions_by_page)]
        checkpoint.extracted_records = len(docs)
        checkpoint.indexed_records = len(docs)
        checkpoint.visual_assets = sum(1 for d in docs if d.asset_id)
        self._write_run_artifacts(
            book_id=book_id,
            metadata=metadata,
            extractions=extractions,
            docs=docs,
            start_page=start_page,
            end_page=end_page,
            jsonl_path=jsonl_path,
        )
        persist("extraction_complete")
        emit("extraction_complete", 95.0, "Extraction complete; records already indexed")
        return metadata, book_id, docs

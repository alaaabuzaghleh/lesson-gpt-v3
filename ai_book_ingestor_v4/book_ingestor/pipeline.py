from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import orjson
from rich.console import Console
from rich.progress import Progress

from .config import settings
from .hierarchy import HierarchyResolver
from .normalizer import build_search_text, normalize_general
from .pdf_reader import PDFReader, PageData
from .prompts import BOOK_METADATA_PROMPT, BOOK_METADATA_SYSTEM, PAGE_SYSTEM, page_prompt
from .quality import block_quality_score
from .question_intelligence import QuestionIntelligenceEngine
from .schemas import BookMetadata, ContentType, IndexDocument, PageExtraction, QuestionData, VISUAL_TYPES, VisualAnalysis
from .visual_analyzer import UniversalVisualAnalyzer
from .vlm_client import OpenAICompatibleVLM

console = Console()


class JobCancelled(RuntimeError):
    """Raised when an external caller requests cooperative cancellation."""


ProgressCallback = Callable[[dict[str, Any]], None]
CancelCheck = Callable[[], bool]


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
            page_prompt(page.pdf_page_number, page.text_layer, metadata.model_dump()),
            [page.as_data_url()],
        )
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
                        parts.append(f"[{tag} PDF text layer]\n{p.text_layer[:settings.visual_context_chars]}")
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
                raise JobCancelled("Extraction job was cancelled")
            hierarchy = resolver.apply_page(page_ex)
            page_data = self.reader.render_page(page_ex.pdf_page_number)
            hierarchy_path = [
                x
                for x in [
                    hierarchy.unit_title,
                    hierarchy.chapter_title,
                    hierarchy.lesson_title,
                    hierarchy.section_title,
                ]
                if x
            ]

            for block in page_ex.blocks:
                if cancel_check and cancel_check():
                    raise JobCancelled("Extraction job was cancelled")
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
                normalized = normalize_general(text)
                search_text = build_search_text(
                    metadata.title,
                    metadata.subject,
                    metadata.grade,
                    hierarchy_path,
                    block.title,
                    text,
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
                        hierarchy_path=hierarchy_path,
                        sequence=block.sequence,
                        content_type=ctype,
                        subtype=block.subtype,
                        title=block.title,
                        text=text,
                        normalized_text=normalized,
                        search_text=search_text,
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

    def run(
        self,
        overrides: dict[str, Any],
        start_page: int = 1,
        end_page: int | None = None,
        resume: bool = True,
        progress_callback: ProgressCallback | None = None,
        cancel_check: CancelCheck | None = None,
    ) -> tuple[BookMetadata, str, list[IndexDocument]]:
        def emit(stage: str, progress: float, message: str, current_page: int | None = None, total_pages: int | None = None) -> None:
            if progress_callback:
                progress_callback({
                    "stage": stage,
                    "progress": round(float(progress), 2),
                    "message": message,
                    "current_page": current_page,
                    "total_pages": total_pages,
                })

        def check_cancel() -> None:
            if cancel_check and cancel_check():
                raise JobCancelled("Extraction job was cancelled")

        check_cancel()
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
        book_id = stable_book_id(self.pdf_path, metadata)
        (self.output_dir / "book_metadata.final.json").write_text(
            metadata.model_dump_json(indent=2), encoding="utf-8"
        )
        emit("metadata", 5.0, "Metadata detected", total_pages=self.reader.page_count)
        check_cancel()

        if start_page > self.reader.page_count:
            raise ValueError(f"start_page {start_page} exceeds PDF page count {self.reader.page_count}")
        end_page = min(end_page or self.reader.page_count, self.reader.page_count)
        if end_page < start_page:
            raise ValueError("end_page must be greater than or equal to start_page")
        extractions: list[PageExtraction] = []
        requested_pages = max(1, end_page - start_page + 1)
        for ordinal, page_no in enumerate(range(start_page, end_page + 1), start=1):
            check_cancel()
            page = self.reader.render_page(page_no)
            try:
                extractions.append(self.extract_page(page, metadata, resume=resume))
            except Exception as exc:
                error = {"pdf_page_number": page_no, "stage": "page_extraction", "error": repr(exc)}
                with (self.output_dir / "errors.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(error, ensure_ascii=False) + "\n")
                console.print(f"[red]Page {page_no} failed: {exc}[/red]")
            emit(
                "page_extraction",
                5.0 + (55.0 * ordinal / requested_pages),
                f"Extracted page {page_no} of {end_page}",
                current_page=page_no,
                total_pages=requested_pages,
            )

        check_cancel()
        emit("question_intelligence", 62.0, "Classifying questions and pedagogical scope")
        console.print("[cyan]Classifying textbook questions and pedagogical scope...[/cyan]")
        extractions = self.question_intelligence.enrich_pages(extractions)
        for enriched in extractions:
            (self.extracted_dir / f"page_{enriched.pdf_page_number:04d}.json").write_text(
                enriched.model_dump_json(indent=2), encoding="utf-8"
            )

        check_cancel()
        emit("visual_analysis", 65.0, "Building records and deeply analyzing visual assets")
        console.print("[cyan]Building structured records and deeply analyzing visual assets...[/cyan]")
        docs = self.build_documents(
            metadata,
            book_id,
            extractions,
            resume=resume,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )
        check_cancel()
        emit("artifact_generation", 91.0, "Writing extraction artifacts")
        jsonl_path = self.index_dir / "documents.jsonl"
        with jsonl_path.open("w", encoding="utf-8") as f:
            for doc in docs:
                f.write(doc.model_dump_json() + "\n")

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
                verification_counts[doc.visual_verification_status] = verification_counts.get(doc.visual_verification_status, 0) + 1
            if doc.question_scope:
                question_scope_counts[doc.question_scope] = question_scope_counts.get(doc.question_scope, 0) + 1
            if doc.question_format:
                question_format_counts[doc.question_format] = question_format_counts.get(doc.question_format, 0) + 1
            if doc.question_purpose:
                question_purpose_counts[doc.question_purpose] = question_purpose_counts.get(doc.question_purpose, 0) + 1
            if doc.question_bloom_level:
                question_bloom_counts[doc.question_bloom_level] = question_bloom_counts.get(doc.question_bloom_level, 0) + 1

        processed_page_numbers = {p.pdf_page_number for p in extractions}
        empty_pages = [p.pdf_page_number for p in extractions if not p.blocks]
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

        emit("quality_report", 93.0, "Generating quality report")
        quality_report = {
            "book_id": book_id,
            "source_page_count": self.reader.page_count,
            "processed_pages": len(processed_page_numbers),
            "processing_coverage": round(len(processed_page_numbers) / max(1, end_page - start_page + 1), 4),
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
            "visual_type_counts": dict(sorted(visual_type_counts.items())),
            "visual_verification_counts": dict(sorted(verification_counts.items())),
            "visual_assets_count": len(visual_docs),
            "problematic_visual_assets_count": len(problematic_visuals),
            "problematic_visual_assets": problematic_visuals[:500],
            "detected_units": sorted({d.unit_title for d in docs if d.unit_title}),
            "detected_chapters": sorted({d.chapter_title for d in docs if d.chapter_title}),
            "detected_lessons": sorted({d.lesson_title for d in docs if d.lesson_title}),
            "printed_page_numbers_detected": sum(1 for p in extractions if p.printed_page_number),
            "recommended_for_live_index": (
                len(processed_page_numbers) == (end_page - start_page + 1)
                and len(empty_pages) == 0
                and (len(low_confidence) / max(1, len(docs))) <= 0.05
                and (len(problematic_visuals) / max(1, len(visual_docs))) <= 0.05
            ),
        }
        (self.output_dir / "quality_report.json").write_text(
            json.dumps(quality_report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        structure = {
            "book_id": book_id,
            "units": sorted({d.unit_title for d in docs if d.unit_title}),
            "chapters": sorted({d.chapter_title for d in docs if d.chapter_title}),
            "lessons": sorted({d.lesson_title for d in docs if d.lesson_title}),
            "sections": sorted({d.section_title for d in docs if d.section_title}),
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
                if any([p.explicit_unit_title, p.explicit_chapter_title, p.explicit_lesson_title, p.explicit_section_title])
            ],
        }
        (self.output_dir / "structure.json").write_text(
            json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        manifest = {
            "schema_version": 3,
            "book_id": book_id,
            "source_pdf": str(self.pdf_path),
            "page_count": self.reader.page_count,
            "processed_pages": len(extractions),
            "indexed_blocks": len(docs),
            "visual_assets": len(visual_docs),
            "metadata": metadata.model_dump(),
            "documents_jsonl": str(jsonl_path),
            "quality_report": str(self.output_dir / "quality_report.json"),
            "structure": str(self.output_dir / "structure.json"),
        }
        (self.output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        emit("extraction_complete", 95.0, "Extraction complete; ready for indexing")
        return metadata, book_id, docs

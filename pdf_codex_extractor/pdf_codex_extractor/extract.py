from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from book_ingestor.hierarchy import HierarchyResolver, build_content_tree
from book_ingestor.schemas import BookMetadata

from .codex_runner import CodexError
from .config import Settings, settings
from .local_vlm_runner import LocalVLMError
from .opensearch_indexer import OpenSearchIndexer, book_id_for_pdf, build_page_documents, metadata_from_pdf
from .pdf_renderer import PDFRenderer
from .runner_factory import make_page_runner


@dataclass
class ExtractionManifest:
    pdf_path: str
    output_dir: str
    book_id: str
    backend: str
    text_source: str
    codex_bin: str
    codex_model: str | None
    render_dpi: int
    index_to_opensearch: bool
    opensearch_index: str | None = None
    metadata: dict[str, Any] | None = None
    started_at: str = ""
    finished_at: str | None = None
    total_pages: int = 0
    extracted_pages: int = 0
    indexed_documents: int = 0
    last_completed_page: int = 0
    pages: list[dict] | None = None


def _job_dir(base_output: Path, pdf_path: Path, backend: str) -> Path:
    suffix = "" if backend == "codex" else f"_{backend}"
    return base_output / f"{pdf_path.stem}{suffix}"


def _page_json_path(pages_json_dir: Path, page_number: int) -> Path:
    return pages_json_dir / f"page_{page_number:04d}.json"


def extract_pdf(
    pdf_path: str | Path,
    *,
    output_dir: Path | None = None,
    start_page: int = 1,
    end_page: int | None = None,
    language_hint: str = "Arabic and English textbook content",
    app_settings: Settings | None = None,
    index_to_opensearch: bool | None = None,
    book_metadata: BookMetadata | None = None,
    resume: bool = True,
    backend: str | None = None,
) -> Path:
    cfg = app_settings or settings
    chosen_backend = (backend or cfg.extractor_backend).strip().lower()
    pdf = Path(pdf_path).resolve()
    root = output_dir or cfg.output_dir
    root.mkdir(parents=True, exist_ok=True)
    job_dir = _job_dir(root, pdf, chosen_backend)
    pages_dir = job_dir / "pages"
    pages_json_dir = job_dir / "pages_json"
    pages_json_dir.mkdir(parents=True, exist_ok=True)

    metadata = book_metadata or metadata_from_pdf(pdf)
    book_id = book_id_for_pdf(pdf, metadata)
    should_index = cfg.index_to_opensearch if index_to_opensearch is None else index_to_opensearch
    indexer = OpenSearchIndexer(cfg) if should_index else None
    hierarchy = HierarchyResolver(book_id=book_id)

    manifest_path = job_dir / "manifest.json"
    if resume and manifest_path.is_file():
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        pages = manifest_data.get("pages") or []
        last_completed = int(manifest_data.get("last_completed_page") or 0)
        indexed_documents = int(manifest_data.get("indexed_documents") or 0)
        if last_completed >= start_page:
            start_page = last_completed + 1
    else:
        pages = []
        indexed_documents = 0

    manifest = ExtractionManifest(
        pdf_path=str(pdf),
        output_dir=str(job_dir),
        book_id=book_id,
        backend=chosen_backend,
        text_source="codex" if chosen_backend == "codex" else "local_vlm",
        codex_bin=str(cfg.codex_bin),
        codex_model=cfg.codex_model,
        render_dpi=cfg.render_dpi,
        index_to_opensearch=should_index,
        opensearch_index=cfg.opensearch_index if should_index else None,
        metadata=metadata.model_dump(mode="json"),
        started_at=datetime.now(timezone.utc).isoformat(),
        pages=pages,
        indexed_documents=indexed_documents,
        last_completed_page=start_page - 1,
    )
    manifest_path.write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2), encoding="utf-8")

    page_runner, text_source = make_page_runner(cfg, chosen_backend)
    page_delay = cfg.codex_page_delay_seconds if chosen_backend == "codex" else cfg.local_page_delay_seconds

    with PDFRenderer(pdf, pages_dir, dpi=cfg.render_dpi) as renderer:
        last_page = end_page or renderer.page_count
        if start_page > last_page:
            manifest.finished_at = datetime.now(timezone.utc).isoformat()
            manifest_path.write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
            return job_dir
        if start_page < 1 or last_page > renderer.page_count or start_page > last_page:
            raise ValueError(
                f"Invalid page range {start_page}..{last_page} for PDF with {renderer.page_count} pages"
            )
        manifest.total_pages = last_page

        for page_number in range(start_page, last_page + 1):
            page_file = _page_json_path(pages_json_dir, page_number)
            used_runner = False
            if resume and page_file.is_file():
                page_data = json.loads(page_file.read_text(encoding="utf-8"))
                rendered_path = pages_dir / f"page_{page_number:04d}.png"
            else:
                try:
                    rendered = renderer.render_page(page_number)
                    page_data = page_runner.extract_page(
                        page_number=page_number,
                        image_path=rendered.image_path,
                        work_dir=job_dir,
                        language_hint=language_hint,
                    )
                except (CodexError, LocalVLMError) as exc:
                    print(
                        f"Stopped before completing page {page_number}: {exc}\n"
                        f"Re-run with --backend {chosen_backend} --resume when ready."
                    )
                    break
                page_file.write_text(json.dumps(page_data, ensure_ascii=False, indent=2), encoding="utf-8")
                rendered_path = rendered.image_path
                used_runner = True

            if indexer is not None:
                docs = build_page_documents(
                    page_data=page_data,
                    metadata=metadata,
                    book_id=book_id,
                    pdf_path=pdf,
                    page_image_path=rendered_path,
                    hierarchy=hierarchy,
                    text_source=text_source,
                )
                success, _errors = indexer.index_documents(docs)
                manifest.indexed_documents += success

            if not any(int(p.get("pdf_page_number") or 0) == page_number for p in pages):
                pages.append(page_data)
            else:
                pages = [
                    page_data if int(p.get("pdf_page_number") or 0) == page_number else p for p in pages
                ]

            manifest.extracted_pages = len(pages)
            manifest.pages = pages
            manifest.last_completed_page = page_number
            manifest_path.write_text(
                json.dumps(asdict(manifest), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"Completed page {page_number}/{last_page} (indexed docs total: {manifest.indexed_documents})")
            if used_runner and page_number < last_page and page_delay > 0:
                print(f"Waiting {page_delay:.0f}s before next page...")
                time.sleep(page_delay)

    manifest.finished_at = datetime.now(timezone.utc).isoformat()
    manifest.pages = pages
    manifest_path.write_text(
        json.dumps(asdict(manifest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    combined_path = job_dir / "pages.json"
    combined_path.write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")

    if pages and indexer is not None:
        all_docs = []
        hierarchy = HierarchyResolver(book_id=book_id)
        for page_data in sorted(pages, key=lambda item: int(item.get("pdf_page_number") or 0)):
            page_no = int(page_data.get("pdf_page_number") or 0)
            rendered_path = pages_dir / f"page_{page_no:04d}.png"
            all_docs.extend(
                build_page_documents(
                    page_data=page_data,
                    metadata=metadata,
                    book_id=book_id,
                    pdf_path=pdf,
                    page_image_path=rendered_path,
                    hierarchy=hierarchy,
                    text_source=text_source,
                )
            )
        outline = build_content_tree(book_id, all_docs)
        (job_dir / "outline.json").write_text(json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8")

    return job_dir

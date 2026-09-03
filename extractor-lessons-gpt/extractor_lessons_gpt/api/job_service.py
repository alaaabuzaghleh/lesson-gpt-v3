from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from remote_lessons_gpt.hierarchy import HierarchyResolver, build_content_tree
from remote_lessons_gpt.schemas import BookMetadata

from extractor_lessons_gpt.codex_runner import CodexError
from extractor_lessons_gpt.config import settings
from extractor_lessons_gpt.extract import ExtractionManifest
from extractor_lessons_gpt.local_vlm_runner import LocalVLMError
from extractor_lessons_gpt.opensearch_indexer import book_id_for_pdf, build_page_documents
from extractor_lessons_gpt.pdf_renderer import PDFRenderer
from extractor_lessons_gpt.runner_factory import make_page_runner


class JobCancelled(RuntimeError):
    pass


ProgressCallback = Callable[[dict[str, Any]], None]
CancelCheck = Callable[[], bool]
RemotePageCallback = Callable[[int, dict[str, Any], list[dict[str, Any]], dict[str, Any]], None]


def _page_json_path(pages_json_dir: Path, page_number: int) -> Path:
    return pages_json_dir / f"page_{page_number:04d}.json"


def run_extraction_job(
    *,
    pdf_path: Path,
    output_dir: Path,
    backend: str,
    start_page: int,
    end_page: int | None,
    resume: bool,
    book_metadata: BookMetadata,
    language_hint: str,
    progress_callback: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
    on_page_remote: RemotePageCallback | None = None,
    book_resource_id: str | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pages_dir = output_dir / "pages"
    pages_json_dir = output_dir / "pages_json"
    pages_json_dir.mkdir(parents=True, exist_ok=True)

    book_id = book_id_for_pdf(pdf_path, book_metadata)
    hierarchy = HierarchyResolver(book_id=book_id)
    page_runner, text_source = make_page_runner(settings, backend)
    page_delay = settings.codex_page_delay_seconds if backend == "codex" else settings.local_page_delay_seconds

    manifest_path = output_dir / "manifest.json"
    pages: list[dict] = []
    remote_synced = 0
    if resume and manifest_path.is_file():
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        pages = manifest_data.get("pages") or []
        last_completed = int(manifest_data.get("last_completed_page") or 0)
        if last_completed >= start_page:
            start_page = last_completed + 1

    manifest = ExtractionManifest(
        pdf_path=str(pdf_path),
        output_dir=str(output_dir),
        book_id=book_id,
        backend=backend,
        text_source=text_source,
        codex_bin=str(settings.codex_bin),
        codex_model=settings.codex_model,
        render_dpi=settings.render_dpi,
        index_to_opensearch=False,
        opensearch_index=None,
        metadata=book_metadata.model_dump(mode="json"),
        started_at=datetime.now(timezone.utc).isoformat(),
        pages=pages,
        indexed_documents=0,
        last_completed_page=start_page - 1,
    )
    manifest_path.write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2), encoding="utf-8")

    def emit(progress: float, stage: str, message: str, *, page: int | None = None, total: int | None = None) -> None:
        if progress_callback:
            progress_callback(
                {
                    "progress": progress,
                    "stage": stage,
                    "message": message,
                    "current_page": page,
                    "total_pages": total,
                }
            )

    with PDFRenderer(pdf_path, pages_dir, dpi=settings.render_dpi) as renderer:
        last_page = end_page or renderer.page_count
        if start_page > last_page:
            manifest.finished_at = datetime.now(timezone.utc).isoformat()
            manifest_path.write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
            return _result_dict(
                book_id=book_id,
                book_metadata=book_metadata,
                pages=pages,
                remote_synced=remote_synced,
                output_dir=output_dir,
                backend=backend,
            )

        manifest.total_pages = last_page
        emit(5, "rendering", "Starting page extraction", page=start_page, total=last_page)

        for page_number in range(start_page, last_page + 1):
            if cancel_check and cancel_check():
                raise JobCancelled("Stop requested")

            page_file = _page_json_path(pages_json_dir, page_number)
            if resume and page_file.is_file():
                page_data = json.loads(page_file.read_text(encoding="utf-8"))
                rendered_path = pages_dir / f"page_{page_number:04d}.png"
                used_runner = False
            else:
                emit(
                    min(95, 5 + (page_number / max(last_page, 1)) * 90),
                    "extracting",
                    f"Extracting page {page_number}/{last_page} ({backend})",
                    page=page_number,
                    total=last_page,
                )
                rendered = renderer.render_page(page_number)
                try:
                    page_data = page_runner.extract_page(
                        page_number=page_number,
                        image_path=rendered.image_path,
                        work_dir=output_dir,
                        language_hint=language_hint,
                    )
                except (CodexError, LocalVLMError) as exc:
                    raise RuntimeError(str(exc)) from exc
                page_file.write_text(json.dumps(page_data, ensure_ascii=False, indent=2), encoding="utf-8")
                rendered_path = rendered.image_path
                used_runner = True

            docs = build_page_documents(
                page_data=page_data,
                metadata=book_metadata,
                book_id=book_id,
                pdf_path=pdf_path,
                page_image_path=rendered_path,
                hierarchy=hierarchy,
                text_source=text_source,
            )
            page_docs = [doc.model_dump(mode="json") for doc in docs]

            if on_page_remote and page_docs:
                progress_value = min(95, 5 + (page_number / max(last_page, 1)) * 90)
                on_page_remote(
                    page_number,
                    page_data,
                    page_docs,
                    {
                        "progress": progress_value,
                        "total_pages": last_page,
                        "stage": "remote_ingest",
                        "message": f"Published page {page_number} to remote server",
                    },
                )
                remote_synced += len(page_docs)

            pages = [p for p in pages if int(p.get("pdf_page_number") or 0) != page_number]
            pages.append(page_data)
            manifest.extracted_pages = len(pages)
            manifest.pages = pages
            manifest.last_completed_page = page_number
            manifest.indexed_documents = remote_synced
            manifest_path.write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2), encoding="utf-8")

            if used_runner and page_number < last_page and page_delay > 0:
                emit(
                    min(95, 5 + (page_number / max(last_page, 1)) * 90),
                    "waiting",
                    f"Waiting {page_delay:.0f}s before next page",
                    page=page_number,
                    total=last_page,
                )
                import time

                time.sleep(page_delay)

    manifest.finished_at = datetime.now(timezone.utc).isoformat()
    manifest.pages = pages
    manifest_path.write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "pages.json").write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")

    if pages:
        all_docs = []
        hierarchy = HierarchyResolver(book_id=book_id)
        for page_data in sorted(pages, key=lambda item: int(item.get("pdf_page_number") or 0)):
            page_no = int(page_data.get("pdf_page_number") or 0)
            rendered_path = pages_dir / f"page_{page_no:04d}.png"
            all_docs.extend(
                build_page_documents(
                    page_data=page_data,
                    metadata=book_metadata,
                    book_id=book_id,
                    pdf_path=pdf_path,
                    page_image_path=rendered_path,
                    hierarchy=hierarchy,
                    text_source=text_source,
                )
            )
        outline = build_content_tree(book_id, all_docs)
        (output_dir / "outline.json").write_text(json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8")

    emit(100, "completed", "Extraction completed", page=last_page, total=last_page)
    return _result_dict(
        book_id=book_id,
        book_metadata=book_metadata,
        pages=pages,
        remote_synced=remote_synced,
        output_dir=output_dir,
        backend=backend,
    )


def _result_dict(
    *,
    book_id: str,
    book_metadata: BookMetadata,
    pages: list[dict],
    remote_synced: int,
    output_dir: Path,
    backend: str,
) -> dict[str, Any]:
    manifest_path = output_dir / "manifest.json"
    outline_path = output_dir / "outline.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    outline = json.loads(outline_path.read_text(encoding="utf-8")) if outline_path.exists() else None
    return {
        "book_id": book_id,
        "metadata": book_metadata.model_dump(mode="json"),
        "extracted_records": len(pages),
        "visual_assets": 0,
        "indexed_records": remote_synced,
        "remote_synced_records": remote_synced,
        "extractor_backend": backend,
        "output_dir": str(output_dir),
        "manifest_path": str(manifest_path),
        "outline_path": str(outline_path) if outline_path.exists() else None,
        "manifest": manifest,
        "outline": outline,
    }

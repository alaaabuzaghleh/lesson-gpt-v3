from __future__ import annotations

import json
import threading
import time
import traceback
from pathlib import Path
from typing import Any

from ..config import settings
from ..pipeline import BookIngestionPipeline, JobCancelled
from .job_store import JobStore


class ExtractionWorkerPool:
    def __init__(self, store: JobStore, worker_count: int | None = None):
        self.store = store
        self.worker_count = max(1, worker_count or settings.api_worker_count)
        self.stop_event = threading.Event()
        self.threads: list[threading.Thread] = []

    def start(self) -> None:
        recovered = self.store.recover_incomplete_jobs()
        if recovered["requeued"] or recovered["cancelled"]:
            print(f"Recovered jobs: {recovered}")
        for idx in range(self.worker_count):
            t = threading.Thread(target=self._loop, name=f"book-extractor-{idx + 1}", daemon=True)
            t.start()
            self.threads.append(t)

    def stop(self, timeout: float = 5.0) -> None:
        self.stop_event.set()
        for t in self.threads:
            t.join(timeout=timeout)

    def _loop(self) -> None:
        while not self.stop_event.is_set():
            job = self.store.claim_next_job()
            if job is None:
                self.stop_event.wait(settings.api_worker_poll_seconds)
                continue
            self._run_job(job)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _run_job(self, job: dict[str, Any]) -> None:
        job_id = job["job_id"]
        book = self.store.get_book(job["book_resource_id"])
        if not book:
            self.store.fail_job(job_id, f"Book resource not found: {job['book_resource_id']}")
            return

        try:
            pipeline = BookIngestionPipeline(book["stored_path"], job["output_dir"])
            base_meta = dict(book.get("metadata") or {})
            base_meta.update(job.get("metadata_overrides") or {})

            def progress(event: dict[str, Any]) -> None:
                self.store.update_progress(
                    job_id,
                    progress=float(event.get("progress") or 0),
                    stage=str(event.get("stage") or "running"),
                    message=str(event.get("message") or "Processing"),
                    current_page=event.get("current_page"),
                    total_pages=event.get("total_pages"),
                )

            metadata, book_id, docs = pipeline.run(
                base_meta,
                start_page=job["start_page"],
                end_page=job.get("end_page"),
                resume=bool(job["resume"]),
                progress_callback=progress,
                cancel_check=lambda: self.store.is_cancel_requested(job_id),
            )

            indexed_records = 0
            if job["index_to_opensearch"]:
                if self.store.is_cancel_requested(job_id):
                    raise JobCancelled("Cancellation requested before OpenSearch indexing")
                self.store.update_progress(
                    job_id,
                    progress=96,
                    stage="opensearch_indexing",
                    message="Indexing extracted records into OpenSearch",
                )
                from ..opensearch_index import bulk_index, create_client, ensure_index

                client = create_client()
                ensure_index(client, settings.opensearch_index, recreate=bool(job["recreate_index"]))
                success, errors = bulk_index(
                    client, settings.opensearch_index, [d.model_dump(mode="json") for d in docs]
                )
                indexed_records = int(success)
                if errors:
                    error_path = Path(job["output_dir"]) / "opensearch_errors.json"
                    error_path.write_text(json.dumps(errors, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
                    self.store.add_event(
                        job_id,
                        "warning",
                        stage="opensearch_indexing",
                        progress=99,
                        message=f"OpenSearch reported {len(errors)} bulk indexing errors",
                        payload={"errors_file": str(error_path), "error_count": len(errors)},
                    )

            output = Path(job["output_dir"])
            quality = self._read_json(output / "quality_report.json")
            manifest = self._read_json(output / "manifest.json")
            result = {
                "book_resource_id": job["book_resource_id"],
                "book_id": book_id,
                "metadata": metadata.model_dump(mode="json"),
                "extracted_records": len(docs),
                "visual_assets": sum(1 for d in docs if d.asset_id),
                "questions": sum(1 for d in docs if d.content_type == "question"),
                "indexed_records": indexed_records,
                "opensearch_index": settings.opensearch_index if job["index_to_opensearch"] else None,
                "output_dir": str(output),
                "manifest_path": str(output / "manifest.json"),
                "quality_report_path": str(output / "quality_report.json"),
                "documents_jsonl_path": str(output / "index" / "documents.jsonl"),
                "recommended_for_live_index": (quality or {}).get("recommended_for_live_index"),
                "manifest": manifest,
                "quality_summary": {
                    "processing_coverage": (quality or {}).get("processing_coverage"),
                    "low_confidence_blocks_count": (quality or {}).get("low_confidence_blocks_count"),
                    "problematic_visual_assets_count": (quality or {}).get("problematic_visual_assets_count"),
                    "questions_count": (quality or {}).get("questions_count"),
                    "visual_assets_count": (quality or {}).get("visual_assets_count"),
                },
            }
            self.store.complete_job(job_id, result=result)
        except JobCancelled as exc:
            self.store.mark_cancelled(job_id, str(exc))
        except Exception as exc:
            self.store.fail_job(job_id, repr(exc), traceback.format_exc())

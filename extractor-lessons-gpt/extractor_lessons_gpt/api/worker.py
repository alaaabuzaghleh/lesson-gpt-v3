from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any

from remote_lessons_gpt.config import settings
from remote_lessons_gpt.schemas import BookMetadata

from extractor_lessons_gpt.api.job_service import JobCancelled, run_extraction_job
from extractor_lessons_gpt.api.job_store import ExtendedJobStore
from extractor_lessons_gpt.api.remote_client import RemoteApiError, RemoteIngestClient, remote_api_configured


class ExtractionWorkerPool:
    def __init__(self, store: ExtendedJobStore, worker_count: int | None = None):
        self.store = store
        self.worker_count = max(1, worker_count or settings.api_worker_count)
        self.stop_event = __import__("threading").Event()
        self.threads: list[__import__("threading").Thread] = []

    def start(self) -> None:
        import threading

        recovered = self.store.recover_incomplete_jobs()
        if recovered.get("requeued") or recovered.get("paused") or recovered.get("cancelled"):
            print(f"Recovered jobs: {recovered}")
        for idx in range(self.worker_count):
            thread = threading.Thread(target=self._loop, name=f"pdf-extractor-{idx + 1}", daemon=True)
            thread.start()
            self.threads.append(thread)

    def stop(self, timeout: float = 5.0) -> None:
        self.stop_event.set()
        for thread in self.threads:
            thread.join(timeout=timeout)

    def _loop(self) -> None:
        while not self.stop_event.is_set():
            job = self.store.claim_next_job()
            if job is None:
                self.stop_event.wait(settings.api_worker_poll_seconds)
                continue
            self._run_job(job)

    def _run_job(self, job: dict[str, Any]) -> None:
        job_id = job["job_id"]
        book = self.store.get_book(job["book_resource_id"])
        if not book:
            self.store.fail_job(job_id, f"Book resource not found: {job['book_resource_id']}")
            return

        remote_client: RemoteIngestClient | None = None
        remote_job_id = str(job.get("remote_job_id") or job_id)
        sync_to_remote = bool(job.get("sync_to_remote"))
        remote_synced = 0

        try:
            metadata = BookMetadata.model_validate(dict(book.get("metadata") or {}))
            metadata_data = metadata.model_dump()
            metadata_data.update(job.get("metadata_overrides") or {})
            if book.get("subject_id"):
                path = self.store.get_subject_path(book["subject_id"])
                if path:
                    metadata_data.update(
                        {
                            "country": path.get("country_name"),
                            "education_system": path.get("education_system_name"),
                            "grade": path.get("grade_name"),
                            "subject": path.get("subject_name"),
                        }
                    )
            metadata = BookMetadata.model_validate(metadata_data)

            backend = str(job.get("extractor_backend") or "local")
            language_hint = str((job.get("metadata_overrides") or {}).get("language_hint") or "Arabic mathematics textbook content")
            output_dir = Path(job["output_dir"])

            if sync_to_remote and remote_api_configured():
                token = str(job.get("remote_auth_token") or "").strip()
                if not token:
                    raise RuntimeError("Remote sync is enabled but no remote auth token was stored on the job")
                remote_client = RemoteIngestClient(token)
                self.store.update_remote_sync(job_id, status="running", message="Publishing pages to remote server")

            last_event_progress = -1.0
            last_event_page = None
            last_event_stage = None

            def progress(event: dict[str, Any]) -> None:
                nonlocal last_event_progress, last_event_page, last_event_stage
                value = float(event.get("progress") or 0)
                page = event.get("current_page")
                stage = str(event.get("stage") or "running")
                notable = (
                    int(value) != int(last_event_progress)
                    or page != last_event_page
                    or stage != last_event_stage
                )
                self.store.update_progress(
                    job_id,
                    progress=value,
                    stage=stage,
                    message=str(event.get("message") or "Processing"),
                    current_page=page,
                    total_pages=event.get("total_pages"),
                    add_event=notable,
                )
                last_event_progress = value
                last_event_page = page
                last_event_stage = stage

            from extractor_lessons_gpt.opensearch_indexer import book_id_for_pdf

            book_id = book_id_for_pdf(Path(book["stored_path"]), metadata)

            def on_page_remote(page_number: int, page_data: dict[str, Any], page_docs: list[dict[str, Any]], info: dict[str, Any]) -> None:
                nonlocal remote_synced
                if not remote_client:
                    return
                printed = page_data.get("printed_page_number")
                printed_text = str(printed) if printed is not None else None
                response = remote_client.ingest_page(
                    remote_job_id,
                    book_id=book_id,
                    book_resource_id=str(book["resource_id"]),
                    pdf_page_number=page_number,
                    printed_page_number=printed_text,
                    page_json=page_data,
                    documents=page_docs,
                    progress=float(info.get("progress") or 0),
                    total_pages=info.get("total_pages"),
                    stage=str(info.get("stage") or "remote_ingest"),
                    message=str(info.get("message") or f"Published page {page_number}"),
                )
                remote_synced += int(response.get("indexed_documents") or len(page_docs))
                self.store.update_remote_sync(
                    job_id,
                    status="running",
                    synced_records=remote_synced,
                    message=f"Remote page {page_number} published",
                )

            result = run_extraction_job(
                pdf_path=Path(book["stored_path"]),
                output_dir=output_dir,
                backend=backend,
                start_page=int(job["start_page"]),
                end_page=job.get("end_page"),
                resume=bool(job["resume"]),
                index_to_opensearch=bool(job["index_to_opensearch"]),
                sync_to_remote=sync_to_remote,
                book_metadata=metadata,
                language_hint=language_hint,
                progress_callback=progress,
                cancel_check=lambda: self.store.is_cancel_requested(job_id),
                on_page_remote=on_page_remote if remote_client else None,
                book_resource_id=str(book["resource_id"]),
            )

            if remote_client:
                remote_client.complete_job(
                    remote_job_id,
                    book_id=str(result.get("book_id") or book_id),
                    extracted_records=int(result.get("extracted_records") or 0),
                    indexed_records=int(result.get("remote_synced_records") or remote_synced),
                    result=result,
                )
                self.store.update_remote_sync(
                    job_id,
                    status="completed",
                    synced_records=int(result.get("remote_synced_records") or remote_synced),
                    message="Remote PostgreSQL and OpenSearch sync completed",
                )

            self.store.complete_job(job_id, result=result)
        except JobCancelled as exc:
            self.store.mark_paused(job_id, str(exc) or "Job paused")
        except RemoteApiError as exc:
            if sync_to_remote:
                self.store.update_remote_sync(job_id, status="failed", message=str(exc))
            self.store.fail_job(job_id, str(exc).strip() or repr(exc), traceback.format_exc())
        except Exception as exc:
            if sync_to_remote:
                self.store.update_remote_sync(job_id, status="failed", message=str(exc))
            self.store.fail_job(job_id, str(exc).strip() or repr(exc), traceback.format_exc())

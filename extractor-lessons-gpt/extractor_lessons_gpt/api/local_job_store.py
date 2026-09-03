from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


class LocalFileJobStore:
    """File-based job/book store for the local extractor (no PostgreSQL)."""

    def __init__(self, data_root: str | Path):
        self.data_root = Path(data_root).resolve()
        self.books_root = self.data_root / "books"
        self.jobs_root = self.data_root / "jobs"
        self._lock = threading.RLock()

    def initialize(self) -> None:
        self.books_root.mkdir(parents=True, exist_ok=True)
        self.jobs_root.mkdir(parents=True, exist_ok=True)

    def close(self) -> None:
        return None

    def _book_meta_path(self, resource_id: str) -> Path:
        return self.books_root / resource_id / "meta.json"

    def _job_meta_path(self, job_id: str) -> Path:
        return self.jobs_root / job_id / "job.json"

    def _events_path(self, job_id: str) -> Path:
        return self.jobs_root / job_id / "events.jsonl"

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _update_job(self, job_id: str, **fields: Any) -> dict[str, Any] | None:
        with self._lock:
            job = self.get_job(job_id)
            if not job:
                return None
            job.update(fields)
            job["updated_at"] = _iso(utcnow())
            self._write_json(self._job_meta_path(job_id), job)
            return job

    def create_book(
        self,
        *,
        resource_id: str,
        original_filename: str,
        stored_path: str,
        size_bytes: int,
        sha256: str,
        metadata: dict[str, Any],
        subject_id: str | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        now = _iso(utcnow())
        catalog_path = None
        if metadata.get("country") and metadata.get("subject"):
            catalog_path = " / ".join(
                str(metadata.get(key) or "")
                for key in ("country", "education_system", "grade", "subject")
                if metadata.get(key)
            )
        book = {
            "resource_id": resource_id,
            "subject_id": subject_id,
            "catalog_path": catalog_path,
            "original_filename": original_filename,
            "stored_path": stored_path,
            "size_bytes": size_bytes,
            "sha256": sha256,
            "metadata": metadata,
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            self._write_json(self._book_meta_path(resource_id), book)
        return book

    def get_book(self, resource_id: str) -> dict[str, Any] | None:
        return self._read_json(self._book_meta_path(resource_id))

    def list_books(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        subject_id: str | None = None,
        grade_id: str | None = None,
        country_id: str | None = None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if not self.books_root.is_dir():
            return []
        for book_dir in sorted(self.books_root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            meta = self._read_json(book_dir / "meta.json")
            if not meta:
                continue
            if subject_id and meta.get("subject_id") != subject_id:
                continue
            md = meta.get("metadata") or {}
            if grade_id and md.get("grade_id") != grade_id:
                continue
            if country_id and md.get("country_id") != country_id:
                continue
            items.append(meta)
        return items[offset : offset + limit]

    def delete_book(self, resource_id: str) -> dict[str, Any] | None:
        book = self.get_book(resource_id)
        if not book:
            return None
        jobs = self.list_jobs(book_resource_id=resource_id, limit=500)
        with self._lock:
            self._book_meta_path(resource_id).unlink(missing_ok=True)
        return {"book": book, "jobs": jobs}

    def create_job(
        self,
        *,
        job_id: str,
        book_resource_id: str,
        output_dir: str,
        start_page: int,
        end_page: int | None,
        resume: bool,
        index_to_opensearch: bool,
        recreate_index: bool,
        metadata_overrides: dict[str, Any],
        extractor_backend: str = "local",
        sync_to_remote: bool = True,
        remote_job_id: str | None = None,
        remote_auth_token: str | None = None,
        retry_of: str | None = None,
    ) -> dict[str, Any]:
        now = _iso(utcnow())
        job = {
            "job_id": job_id,
            "book_resource_id": book_resource_id,
            "status": "queued",
            "progress": 0.0,
            "stage": "queued",
            "message": "Waiting for an extraction worker",
            "start_page": start_page,
            "end_page": end_page,
            "resume": resume,
            "index_to_opensearch": index_to_opensearch,
            "recreate_index": recreate_index,
            "metadata_overrides": metadata_overrides,
            "output_dir": output_dir,
            "retry_of": retry_of,
            "extractor_backend": extractor_backend,
            "sync_to_remote": sync_to_remote,
            "remote_sync_status": "pending" if sync_to_remote else None,
            "remote_synced_records": None,
            "remote_job_id": remote_job_id or job_id,
            "remote_auth_token": remote_auth_token,
            "book_id": None,
            "extracted_records": None,
            "visual_assets": None,
            "indexed_records": None,
            "result": None,
            "error": None,
            "traceback": None,
            "checkpoint": None,
            "current_page": None,
            "total_pages": None,
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "updated_at": now,
        }
        with self._lock:
            self._write_json(self._job_meta_path(job_id), job)
        self.add_event(
            job_id,
            "queued",
            stage="queued",
            progress=0,
            message=f"Job queued ({extractor_backend} backend)",
            payload={"extractor_backend": extractor_backend, "sync_to_remote": sync_to_remote},
        )
        return self.get_job(job_id)  # type: ignore[return-value]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        job = self._read_json(self._job_meta_path(job_id))
        if not job:
            return None
        if isinstance(job.get("result"), str):
            try:
                job["result"] = json.loads(job["result"])
            except json.JSONDecodeError:
                pass
        if isinstance(job.get("checkpoint"), str):
            try:
                job["checkpoint"] = json.loads(job["checkpoint"])
            except json.JSONDecodeError:
                pass
        return job

    def list_jobs(
        self,
        *,
        status: str | None = None,
        book_resource_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if not self.jobs_root.is_dir():
            return []
        for job_dir in self.jobs_root.iterdir():
            job = self._read_json(job_dir / "job.json")
            if not job:
                continue
            if status and job.get("status") != status:
                continue
            if book_resource_id and job.get("book_resource_id") != book_resource_id:
                continue
            items.append(job)
        items.sort(key=lambda j: j.get("created_at") or "", reverse=True)
        return items[offset : offset + limit]

    def claim_next_job(self) -> dict[str, Any] | None:
        with self._lock:
            queued: list[dict[str, Any]] = []
            if not self.jobs_root.is_dir():
                return None
            for job_dir in self.jobs_root.iterdir():
                job = self._read_json(job_dir / "job.json")
                if job and job.get("status") == "queued":
                    queued.append(job)
            if not queued:
                return None
            queued.sort(key=lambda j: j.get("created_at") or "")
            job_id = queued[0]["job_id"]
            now = _iso(utcnow())
            job = self._update_job(
                job_id,
                status="running",
                stage="starting",
                message="Worker started",
                started_at=now,
            )
        if job:
            self.add_event(job_id, "started", stage="starting", progress=0, message="Worker started")
        return job

    def update_progress(
        self,
        job_id: str,
        *,
        progress: float,
        stage: str,
        message: str,
        current_page: int | None = None,
        total_pages: int | None = None,
        add_event: bool = True,
    ) -> None:
        progress = max(0.0, min(100.0, float(progress)))
        fields: dict[str, Any] = {
            "progress": progress,
            "stage": stage,
            "message": message,
        }
        if current_page is not None:
            fields["current_page"] = current_page
        if total_pages is not None:
            fields["total_pages"] = total_pages
        self._update_job(job_id, **fields)
        if add_event:
            self.add_event(
                job_id,
                "progress",
                stage=stage,
                progress=progress,
                message=message,
                payload={"current_page": current_page, "total_pages": total_pages},
            )

    def complete_job(self, job_id: str, *, result: dict[str, Any]) -> None:
        now = _iso(utcnow())
        self._update_job(
            job_id,
            status="completed",
            progress=100.0,
            stage="completed",
            message="Completed",
            book_id=result.get("book_id"),
            extracted_records=result.get("extracted_records"),
            visual_assets=result.get("visual_assets"),
            indexed_records=result.get("indexed_records"),
            result=result,
            finished_at=now,
        )
        self.add_event(job_id, "completed", stage="completed", progress=100, message="Job completed", payload=result)

    def fail_job(self, job_id: str, error: str, traceback_text: str | None = None) -> None:
        now = _iso(utcnow())
        self._update_job(
            job_id,
            status="failed",
            stage="failed",
            message=error[:2000],
            error=error,
            traceback=traceback_text,
            finished_at=now,
        )
        self.add_event(
            job_id,
            "failed",
            stage="failed",
            message=error[:1000],
            payload={"error": error, "traceback": traceback_text},
        )

    def save_checkpoint(self, job_id: str, checkpoint: dict[str, Any] | None) -> None:
        if not checkpoint:
            return
        self._update_job(
            job_id,
            checkpoint=checkpoint,
            book_id=checkpoint.get("book_id"),
            extracted_records=checkpoint.get("extracted_records"),
            indexed_records=checkpoint.get("indexed_records"),
            visual_assets=checkpoint.get("visual_assets"),
            current_page=checkpoint.get("current_page"),
            total_pages=checkpoint.get("total_pages"),
        )

    def request_stop(self, job_id: str) -> dict[str, Any] | None:
        job = self.get_job(job_id)
        if not job:
            return None
        now = _iso(utcnow())
        if job["status"] == "queued":
            self._update_job(
                job_id,
                status="paused",
                stage="paused",
                message="Stopped before execution",
                finished_at=now,
            )
            self.add_event(
                job_id,
                "paused",
                stage="paused",
                progress=job.get("progress"),
                message="Stopped before execution",
            )
        elif job["status"] == "running":
            self._update_job(
                job_id,
                status="cancel_requested",
                stage="cancel_requested",
                message="Stop requested",
            )
            self.add_event(
                job_id,
                "stop_requested",
                stage="cancel_requested",
                progress=job.get("progress"),
                message="Stop requested; will pause after the current page",
            )
        return self.get_job(job_id)

    def request_cancel(self, job_id: str) -> dict[str, Any] | None:
        return self.request_stop(job_id)

    def mark_paused(self, job_id: str, message: str = "Job paused") -> None:
        now = _iso(utcnow())
        self._update_job(job_id, status="paused", stage="paused", message=message, finished_at=now)
        self.add_event(job_id, "paused", stage="paused", message=message)

    def resume_job(self, job_id: str) -> dict[str, Any] | None:
        job = self.get_job(job_id)
        if not job:
            return None
        if job["status"] not in {"paused", "failed", "cancelled"}:
            return job
        self._update_job(
            job_id,
            status="queued",
            stage="queued",
            message="Resuming from checkpoint",
            resume=True,
            recreate_index=False,
            error=None,
            traceback=None,
            finished_at=None,
        )
        self.add_event(
            job_id,
            "resumed",
            stage="queued",
            progress=job.get("progress"),
            message="Job resumed from checkpoint",
        )
        return self.get_job(job_id)

    def delete_job(self, job_id: str) -> dict[str, Any] | None:
        job = self.get_job(job_id)
        if not job:
            return None
        if job["status"] in {"running", "cancel_requested"}:
            return {"error": "job_active", "job": job}
        with self._lock:
            self._job_meta_path(job_id).unlink(missing_ok=True)
            self._events_path(job_id).unlink(missing_ok=True)
        return {"deleted": True, "job": job}

    def is_cancel_requested(self, job_id: str) -> bool:
        job = self.get_job(job_id)
        return bool(job and job.get("status") in {"cancel_requested", "cancelled", "paused"})

    def add_event(
        self,
        job_id: str,
        event_type: str,
        *,
        stage: str | None = None,
        progress: float | None = None,
        message: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        path = self._events_path(job_id)
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            next_id = 1
            if path.is_file():
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        try:
                            next_id = max(next_id, int(json.loads(line)["id"]) + 1)
                        except (json.JSONDecodeError, KeyError, TypeError):
                            pass
            event = {
                "id": next_id,
                "job_id": job_id,
                "event_type": event_type,
                "stage": stage,
                "progress": progress,
                "message": message,
                "payload": payload,
                "created_at": _iso(utcnow()),
            }
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

    def list_events(self, job_id: str, *, after_id: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        path = self._events_path(job_id)
        if not path.is_file():
            return []
        items: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if int(event.get("id") or 0) > after_id:
                items.append(event)
        return items[:limit]

    def recover_incomplete_jobs(self) -> dict[str, int]:
        requeued = 0
        paused = 0
        if not self.jobs_root.is_dir():
            return {"requeued": 0, "paused": 0, "cancelled": 0}
        for job_dir in self.jobs_root.iterdir():
            job = self._read_json(job_dir / "job.json")
            if not job:
                continue
            status = job.get("status")
            if status == "cancel_requested":
                self.mark_paused(job["job_id"], "Stopped during service restart")
                paused += 1
            elif status == "running":
                self._update_job(
                    job["job_id"],
                    status="queued",
                    stage="queued",
                    message="Recovered after service restart",
                    started_at=None,
                )
                requeued += 1
        return {"requeued": requeued, "paused": paused, "cancelled": 0}

    def update_remote_sync(
        self,
        job_id: str,
        *,
        status: str,
        synced_records: int | None = None,
        message: str | None = None,
    ) -> None:
        fields: dict[str, Any] = {"remote_sync_status": status}
        if synced_records is not None:
            fields["remote_synced_records"] = synced_records
        self._update_job(job_id, **fields)
        if message:
            self.add_event(job_id, "remote_sync", stage="remote_sync", message=message)

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    """Small persistent SQLite job registry.

    A new SQLite connection is opened per operation so the store is safe to use
    from FastAPI request threads and ingestion worker threads simultaneously.
    WAL mode permits readers while workers update progress.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_lock = threading.Lock()
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def initialize(self) -> None:
        with self._init_lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS books (
                    resource_id TEXT PRIMARY KEY,
                    original_filename TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    book_resource_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0,
                    stage TEXT,
                    message TEXT,
                    current_page INTEGER,
                    total_pages INTEGER,
                    start_page INTEGER NOT NULL DEFAULT 1,
                    end_page INTEGER,
                    resume INTEGER NOT NULL DEFAULT 1,
                    index_to_opensearch INTEGER NOT NULL DEFAULT 1,
                    recreate_index INTEGER NOT NULL DEFAULT 0,
                    metadata_overrides_json TEXT NOT NULL DEFAULT '{}',
                    output_dir TEXT NOT NULL,
                    book_id TEXT,
                    extracted_records INTEGER,
                    visual_assets INTEGER,
                    indexed_records INTEGER,
                    result_json TEXT,
                    error TEXT,
                    traceback TEXT,
                    retry_of TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(book_resource_id) REFERENCES books(resource_id)
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at);
                CREATE INDEX IF NOT EXISTS idx_jobs_book ON jobs(book_resource_id, created_at);

                CREATE TABLE IF NOT EXISTS job_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    stage TEXT,
                    progress REAL,
                    message TEXT,
                    payload_json TEXT,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
                );

                CREATE INDEX IF NOT EXISTS idx_job_events_job_id ON job_events(job_id, id);
                """
            )

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        d = dict(row)
        for key in ("metadata_json", "metadata_overrides_json", "result_json", "payload_json"):
            if key in d:
                raw = d.pop(key)
                name = key.removesuffix("_json")
                try:
                    d[name] = json.loads(raw) if raw else None
                except Exception:
                    d[name] = raw
        for key in ("resume", "index_to_opensearch", "recreate_index"):
            if key in d:
                d[key] = bool(d[key])
        return d

    def create_book(
        self,
        resource_id: str,
        original_filename: str,
        stored_path: str,
        size_bytes: int,
        sha256: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        now = utcnow()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO books(resource_id, original_filename, stored_path, size_bytes, sha256, metadata_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (resource_id, original_filename, stored_path, size_bytes, sha256, json.dumps(metadata, ensure_ascii=False), now),
            )
        return self.get_book(resource_id)  # type: ignore[return-value]

    def get_book(self, resource_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            return self._row(conn.execute("SELECT * FROM books WHERE resource_id=?", (resource_id,)).fetchone())

    def list_books(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM books ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        return [self._row(r) for r in rows if r is not None]  # type: ignore[list-item]

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
        retry_of: str | None = None,
    ) -> dict[str, Any]:
        now = utcnow()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO jobs(
                    job_id, book_resource_id, status, progress, stage, message,
                    start_page, end_page, resume, index_to_opensearch, recreate_index,
                    metadata_overrides_json, output_dir, retry_of, created_at, updated_at
                ) VALUES (?, ?, 'queued', 0, 'queued', 'Waiting for an extraction worker', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_id, book_resource_id, start_page, end_page, int(resume), int(index_to_opensearch),
                    int(recreate_index), json.dumps(metadata_overrides, ensure_ascii=False), output_dir,
                    retry_of, now, now,
                ),
            )
        self.add_event(job_id, "queued", stage="queued", progress=0, message="Job queued")
        return self.get_job(job_id)  # type: ignore[return-value]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            return self._row(conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone())

    def list_jobs(
        self,
        *,
        status: str | None = None,
        book_resource_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status=?")
            params.append(status)
        if book_resource_id:
            clauses.append("book_resource_id=?")
            params.append(book_resource_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        params.extend([limit, offset])
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM jobs{where} ORDER BY created_at DESC LIMIT ? OFFSET ?", params
            ).fetchall()
        return [self._row(r) for r in rows if r is not None]  # type: ignore[list-item]

    def claim_next_job(self) -> dict[str, Any] | None:
        """Atomically claims the oldest queued job for a worker."""
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT job_id FROM jobs WHERE status='queued' ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            if row is None:
                conn.execute("COMMIT")
                return None
            job_id = row["job_id"]
            now = utcnow()
            updated = conn.execute(
                """UPDATE jobs SET status='running', stage='starting', message='Worker started',
                   started_at=COALESCE(started_at, ?), updated_at=? WHERE job_id=? AND status='queued'""",
                (now, now, job_id),
            ).rowcount
            conn.execute("COMMIT")
            if not updated:
                return None
        self.add_event(job_id, "started", stage="starting", progress=0, message="Worker started")
        return self.get_job(job_id)

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
        now = utcnow()
        progress = max(0.0, min(100.0, float(progress)))
        with self._connect() as conn:
            conn.execute(
                """UPDATE jobs SET progress=?, stage=?, message=?, current_page=?,
                   total_pages=COALESCE(?, total_pages), updated_at=? WHERE job_id=?""",
                (progress, stage, message, current_page, total_pages, now, job_id),
            )
        if add_event:
            self.add_event(
                job_id, "progress", stage=stage, progress=progress, message=message,
                payload={"current_page": current_page, "total_pages": total_pages},
            )

    def complete_job(self, job_id: str, *, result: dict[str, Any]) -> None:
        now = utcnow()
        with self._connect() as conn:
            conn.execute(
                """UPDATE jobs SET status='completed', progress=100, stage='completed', message='Completed',
                   book_id=?, extracted_records=?, visual_assets=?, indexed_records=?, result_json=?,
                   finished_at=?, updated_at=? WHERE job_id=?""",
                (
                    result.get("book_id"), result.get("extracted_records"), result.get("visual_assets"),
                    result.get("indexed_records"), json.dumps(result, ensure_ascii=False), now, now, job_id,
                ),
            )
        self.add_event(job_id, "completed", stage="completed", progress=100, message="Job completed", payload=result)

    def fail_job(self, job_id: str, error: str, traceback_text: str | None = None) -> None:
        now = utcnow()
        with self._connect() as conn:
            conn.execute(
                """UPDATE jobs SET status='failed', stage='failed', message=?, error=?, traceback=?,
                   finished_at=?, updated_at=? WHERE job_id=?""",
                (error[:2000], error, traceback_text, now, now, job_id),
            )
        self.add_event(job_id, "failed", stage="failed", message=error[:1000])

    def request_cancel(self, job_id: str) -> dict[str, Any] | None:
        job = self.get_job(job_id)
        if not job:
            return None
        now = utcnow()
        if job["status"] == "queued":
            with self._connect() as conn:
                conn.execute(
                    """UPDATE jobs SET status='cancelled', stage='cancelled', message='Cancelled before execution',
                       finished_at=?, updated_at=? WHERE job_id=? AND status='queued'""",
                    (now, now, job_id),
                )
            self.add_event(job_id, "cancelled", stage="cancelled", progress=job.get("progress"), message="Cancelled before execution")
        elif job["status"] == "running":
            with self._connect() as conn:
                conn.execute(
                    "UPDATE jobs SET status='cancel_requested', stage='cancel_requested', message='Cancellation requested', updated_at=? WHERE job_id=? AND status='running'",
                    (now, job_id),
                )
            self.add_event(job_id, "cancel_requested", stage="cancel_requested", progress=job.get("progress"), message="Cancellation requested")
        return self.get_job(job_id)

    def mark_cancelled(self, job_id: str, message: str = "Job cancelled") -> None:
        now = utcnow()
        with self._connect() as conn:
            conn.execute(
                """UPDATE jobs SET status='cancelled', stage='cancelled', message=?, finished_at=?, updated_at=?
                   WHERE job_id=?""",
                (message, now, now, job_id),
            )
        self.add_event(job_id, "cancelled", stage="cancelled", message=message)

    def is_cancel_requested(self, job_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT status FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        return bool(row and row["status"] in {"cancel_requested", "cancelled"})

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
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO job_events(job_id, created_at, event_type, stage, progress, message, payload_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (job_id, utcnow(), event_type, stage, progress, message, json.dumps(payload, ensure_ascii=False) if payload is not None else None),
            )

    def list_events(self, job_id: str, *, after_id: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM job_events WHERE job_id=? AND id>? ORDER BY id ASC LIMIT ?",
                (job_id, after_id, limit),
            ).fetchall()
        return [self._row(r) for r in rows if r is not None]  # type: ignore[list-item]

    def recover_incomplete_jobs(self) -> dict[str, int]:
        """Requeues jobs interrupted by a server/process restart."""
        now = utcnow()
        with self._connect() as conn:
            cancelled = conn.execute(
                """UPDATE jobs SET status='cancelled', stage='cancelled', message='Cancelled during service restart',
                   finished_at=?, updated_at=? WHERE status='cancel_requested'""",
                (now, now),
            ).rowcount
            requeued = conn.execute(
                """UPDATE jobs SET status='queued', stage='queued', message='Recovered after service restart',
                   started_at=NULL, updated_at=? WHERE status='running'""",
                (now,),
            ).rowcount
        return {"requeued": requeued, "cancelled": cancelled}

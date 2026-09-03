from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import psycopg

from book_ingestor.api.job_store import JobStore, utcnow


class ExtendedJobStore(JobStore):
    """PostgreSQL store with pdf_codex_extractor job fields."""

    def initialize(self) -> None:
        super().initialize()
        with self._init_lock, self.pool.connection() as conn:
            self._migrate_extractor(conn)
            conn.commit()
        self._reset_pool_after_schema_change()

    def _migrate_extractor(self, conn: psycopg.Connection) -> None:
        conn.execute(
            "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS extractor_backend TEXT NOT NULL DEFAULT 'local'"
        )
        conn.execute(
            "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS sync_to_remote BOOLEAN NOT NULL DEFAULT FALSE"
        )
        conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS remote_sync_status TEXT")
        conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS remote_synced_records INT")
        conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS remote_job_id TEXT")
        conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS remote_auth_token TEXT")

    @staticmethod
    def _normalize_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        data = JobStore._normalize_row(row)
        if not data:
            return None
        data.setdefault("extractor_backend", "local")
        data.setdefault("sync_to_remote", False)
        return data

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
        sync_to_remote: bool = False,
        remote_job_id: str | None = None,
        remote_auth_token: str | None = None,
        retry_of: str | None = None,
    ) -> dict[str, Any]:
        now = utcnow()
        with self.pool.connection() as conn:
            conn.execute(
                """INSERT INTO jobs(
                    job_id, book_resource_id, status, progress, stage, message,
                    start_page, end_page, resume, index_to_opensearch, recreate_index,
                    metadata_overrides_json, output_dir, retry_of,
                    extractor_backend, sync_to_remote, remote_sync_status,
                    remote_job_id, remote_auth_token,
                    created_at, updated_at
                ) VALUES (
                    %s, %s, 'queued', 0, 'queued', 'Waiting for an extraction worker',
                    %s, %s, %s, %s, %s, %s::jsonb, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s
                )""",
                (
                    job_id,
                    book_resource_id,
                    start_page,
                    end_page,
                    resume,
                    index_to_opensearch,
                    recreate_index,
                    json.dumps(metadata_overrides, ensure_ascii=False),
                    output_dir,
                    retry_of,
                    extractor_backend,
                    sync_to_remote,
                    "pending" if sync_to_remote else None,
                    remote_job_id or job_id,
                    remote_auth_token,
                    now,
                    now,
                ),
            )
            conn.commit()
        self.add_event(
            job_id,
            "queued",
            stage="queued",
            progress=0,
            message=f"Job queued ({extractor_backend} backend)",
            payload={"extractor_backend": extractor_backend, "sync_to_remote": sync_to_remote},
        )
        return self.get_job(job_id)  # type: ignore[return-value]

    def update_remote_sync(
        self,
        job_id: str,
        *,
        status: str,
        synced_records: int | None = None,
        message: str | None = None,
    ) -> None:
        fields = ["remote_sync_status=%s", "updated_at=%s"]
        params: list[Any] = [status, utcnow()]
        if synced_records is not None:
            fields.append("remote_synced_records=%s")
            params.append(synced_records)
        params.append(job_id)
        with self.pool.connection() as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE job_id=%s", params)
            conn.commit()
        if message:
            self.add_event(job_id, "remote_sync", stage="remote_sync", message=message)

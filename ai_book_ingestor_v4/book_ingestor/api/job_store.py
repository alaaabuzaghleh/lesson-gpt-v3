from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from ..config import settings
from .auth_utils import ALL_ROLES, hash_password


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL CHECK (role IN ('super_admin', 'admin', 'student')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS countries (
    id UUID PRIMARY KEY,
    code TEXT UNIQUE,
    name TEXT NOT NULL,
    name_ar TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS education_systems (
    id UUID PRIMARY KEY,
    country_id UUID NOT NULL REFERENCES countries(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    name_ar TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS grades (
    id UUID PRIMARY KEY,
    education_system_id UUID NOT NULL REFERENCES education_systems(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    name_ar TEXT,
    sort_order INT NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS subjects (
    id UUID PRIMARY KEY,
    grade_id UUID NOT NULL REFERENCES grades(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    name_ar TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS books (
    resource_id TEXT PRIMARY KEY,
    subject_id UUID REFERENCES subjects(id),
    original_filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    sha256 TEXT NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    book_resource_id TEXT NOT NULL REFERENCES books(resource_id),
    status TEXT NOT NULL,
    progress REAL NOT NULL DEFAULT 0,
    stage TEXT,
    message TEXT,
    current_page INT,
    total_pages INT,
    start_page INT NOT NULL DEFAULT 1,
    end_page INT,
    resume BOOLEAN NOT NULL DEFAULT TRUE,
    index_to_opensearch BOOLEAN NOT NULL DEFAULT TRUE,
    recreate_index BOOLEAN NOT NULL DEFAULT FALSE,
    metadata_overrides_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_dir TEXT NOT NULL,
    book_id TEXT,
    extracted_records INT,
    visual_assets INT,
    indexed_records INT,
    result_json JSONB,
    error TEXT,
    traceback TEXT,
    retry_of TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS job_events (
    id BIGSERIAL PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type TEXT NOT NULL,
    stage TEXT,
    progress REAL,
    message TEXT,
    payload_json JSONB
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_book ON jobs(book_resource_id, created_at);
CREATE INDEX IF NOT EXISTS idx_job_events_job_id ON job_events(job_id, id);
CREATE INDEX IF NOT EXISTS idx_books_subject ON books(subject_id, created_at);
CREATE INDEX IF NOT EXISTS idx_education_systems_country ON education_systems(country_id);
CREATE INDEX IF NOT EXISTS idx_grades_system ON grades(education_system_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_subjects_grade ON subjects(grade_id);
"""


class JobStore:
    """PostgreSQL-backed persistent store for catalog, users, books, and jobs."""

    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or settings.database_url
        self._init_lock = threading.Lock()
        self.pool = ConnectionPool(self.database_url, kwargs={"row_factory": dict_row}, open=True)
        self.initialize()

    def close(self) -> None:
        self.pool.close()

    def initialize(self) -> None:
        with self._init_lock, self.pool.connection() as conn:
            conn.execute(SCHEMA_SQL)
            conn.commit()
            self._seed_super_admin(conn)

    def _seed_super_admin(self, conn: psycopg.Connection) -> None:
        row = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        if row:
            return
        user_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO users(id, email, password_hash, full_name, role)
               VALUES (%s, %s, %s, %s, 'super_admin')""",
            (
                user_id,
                settings.super_admin_email.lower(),
                hash_password(settings.super_admin_password),
                settings.super_admin_name,
            ),
        )
        conn.commit()

    @staticmethod
    def _normalize_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        d = dict(row)
        for key in ("id", "country_id", "education_system_id", "grade_id", "subject_id", "created_by"):
            if key in d and d[key] is not None:
                d[key] = str(d[key])
        for key in ("created_at", "updated_at", "started_at", "finished_at"):
            if key in d and d[key] is not None and hasattr(d[key], "isoformat"):
                d[key] = d[key].isoformat()
        if "metadata_json" in d:
            d["metadata"] = d.pop("metadata_json") or {}
        if "metadata_overrides_json" in d:
            d["metadata_overrides"] = d.pop("metadata_overrides_json") or {}
        if "result_json" in d:
            d["result"] = d.pop("result_json")
        if "payload_json" in d:
            d["payload"] = d.pop("payload_json")
        return d

    # --- Users / Auth ---

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self.pool.connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email=%s", (email.lower(),)
            ).fetchone()
        return self._normalize_row(row)

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        with self.pool.connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id=%s", (user_id,)).fetchone()
        user = self._normalize_row(row)
        if user:
            user.pop("password_hash", None)
        return user

    def create_user(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
        role: str,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        if role not in ALL_ROLES:
            raise ValueError(f"Invalid role: {role}")
        user_id = str(uuid.uuid4())
        with self.pool.connection() as conn:
            conn.execute(
                """INSERT INTO users(id, email, password_hash, full_name, role, created_by)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (user_id, email.lower(), hash_password(password), full_name, role, created_by),
            )
            conn.commit()
        return self.get_user(user_id)  # type: ignore[return-value]

    def list_users(self, *, roles: list[str] | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if roles:
            clauses.append(f"role IN ({','.join(['%s'] * len(roles))})")
            params.extend(roles)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self.pool.connection() as conn:
            rows = conn.execute(
                f"SELECT id, email, full_name, role, is_active, created_at FROM users{where} ORDER BY created_at DESC",
                params,
            ).fetchall()
        return [self._normalize_row(r) for r in rows if r is not None]  # type: ignore[list-item]

    # --- Catalog ---

    def create_country(self, *, name: str, name_ar: str | None = None, code: str | None = None) -> dict[str, Any]:
        cid = str(uuid.uuid4())
        with self.pool.connection() as conn:
            conn.execute(
                "INSERT INTO countries(id, code, name, name_ar) VALUES (%s, %s, %s, %s)",
                (cid, code, name, name_ar),
            )
            conn.commit()
        return self.get_country(cid)  # type: ignore[return-value]

    def get_country(self, country_id: str) -> dict[str, Any] | None:
        with self.pool.connection() as conn:
            return self._normalize_row(conn.execute("SELECT * FROM countries WHERE id=%s", (country_id,)).fetchone())

    def list_countries(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        q = "SELECT * FROM countries"
        if active_only:
            q += " WHERE is_active=TRUE"
        q += " ORDER BY name"
        with self.pool.connection() as conn:
            rows = conn.execute(q).fetchall()
        return [self._normalize_row(r) for r in rows if r is not None]  # type: ignore[list-item]

    def create_education_system(self, *, country_id: str, name: str, name_ar: str | None = None) -> dict[str, Any]:
        sid = str(uuid.uuid4())
        with self.pool.connection() as conn:
            conn.execute(
                "INSERT INTO education_systems(id, country_id, name, name_ar) VALUES (%s, %s, %s, %s)",
                (sid, country_id, name, name_ar),
            )
            conn.commit()
        return self.get_education_system(sid)  # type: ignore[return-value]

    def get_education_system(self, system_id: str) -> dict[str, Any] | None:
        with self.pool.connection() as conn:
            return self._normalize_row(
                conn.execute("SELECT * FROM education_systems WHERE id=%s", (system_id,)).fetchone()
            )

    def list_education_systems(self, *, country_id: str | None = None, active_only: bool = True) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if country_id:
            clauses.append("country_id=%s")
            params.append(country_id)
        if active_only:
            clauses.append("is_active=TRUE")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self.pool.connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM education_systems{where} ORDER BY name", params
            ).fetchall()
        return [self._normalize_row(r) for r in rows if r is not None]  # type: ignore[list-item]

    def create_grade(
        self, *, education_system_id: str, name: str, name_ar: str | None = None, sort_order: int = 0
    ) -> dict[str, Any]:
        gid = str(uuid.uuid4())
        with self.pool.connection() as conn:
            conn.execute(
                "INSERT INTO grades(id, education_system_id, name, name_ar, sort_order) VALUES (%s, %s, %s, %s, %s)",
                (gid, education_system_id, name, name_ar, sort_order),
            )
            conn.commit()
        return self.get_grade(gid)  # type: ignore[return-value]

    def get_grade(self, grade_id: str) -> dict[str, Any] | None:
        with self.pool.connection() as conn:
            return self._normalize_row(conn.execute("SELECT * FROM grades WHERE id=%s", (grade_id,)).fetchone())

    def list_grades(self, *, education_system_id: str | None = None, active_only: bool = True) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if education_system_id:
            clauses.append("education_system_id=%s")
            params.append(education_system_id)
        if active_only:
            clauses.append("is_active=TRUE")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self.pool.connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM grades{where} ORDER BY sort_order, name", params
            ).fetchall()
        return [self._normalize_row(r) for r in rows if r is not None]  # type: ignore[list-item]

    def create_subject(self, *, grade_id: str, name: str, name_ar: str | None = None) -> dict[str, Any]:
        sid = str(uuid.uuid4())
        with self.pool.connection() as conn:
            conn.execute(
                "INSERT INTO subjects(id, grade_id, name, name_ar) VALUES (%s, %s, %s, %s)",
                (sid, grade_id, name, name_ar),
            )
            conn.commit()
        return self.get_subject(sid)  # type: ignore[return-value]

    def get_subject(self, subject_id: str) -> dict[str, Any] | None:
        with self.pool.connection() as conn:
            return self._normalize_row(conn.execute("SELECT * FROM subjects WHERE id=%s", (subject_id,)).fetchone())

    def list_subjects(self, *, grade_id: str | None = None, active_only: bool = True) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if grade_id:
            clauses.append("grade_id=%s")
            params.append(grade_id)
        if active_only:
            clauses.append("is_active=TRUE")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self.pool.connection() as conn:
            rows = conn.execute(f"SELECT * FROM subjects{where} ORDER BY name", params).fetchall()
        return [self._normalize_row(r) for r in rows if r is not None]  # type: ignore[list-item]

    def get_catalog_tree(self) -> list[dict[str, Any]]:
        with self.pool.connection() as conn:
            countries = conn.execute(
                "SELECT * FROM countries WHERE is_active=TRUE ORDER BY name"
            ).fetchall()
            tree: list[dict[str, Any]] = []
            for country in countries:
                c = self._normalize_row(country)
                assert c is not None
                systems = conn.execute(
                    "SELECT * FROM education_systems WHERE country_id=%s AND is_active=TRUE ORDER BY name",
                    (c["id"],),
                ).fetchall()
                c["education_systems"] = []
                for system in systems:
                    s = self._normalize_row(system)
                    assert s is not None
                    grades = conn.execute(
                        "SELECT * FROM grades WHERE education_system_id=%s AND is_active=TRUE ORDER BY sort_order, name",
                        (s["id"],),
                    ).fetchall()
                    s["grades"] = []
                    for grade in grades:
                        g = self._normalize_row(grade)
                        assert g is not None
                        subjects = conn.execute(
                            "SELECT * FROM subjects WHERE grade_id=%s AND is_active=TRUE ORDER BY name",
                            (g["id"],),
                        ).fetchall()
                        g["subjects"] = [self._normalize_row(sub) for sub in subjects if sub]
                        s["grades"].append(g)
                    c["education_systems"].append(s)
                tree.append(c)
            return tree

    def get_subject_path(self, subject_id: str) -> dict[str, Any] | None:
        with self.pool.connection() as conn:
            row = conn.execute(
                """
                SELECT s.id AS subject_id, s.name AS subject_name, s.name_ar AS subject_name_ar,
                       g.id AS grade_id, g.name AS grade_name, g.name_ar AS grade_name_ar,
                       es.id AS education_system_id, es.name AS education_system_name, es.name_ar AS education_system_name_ar,
                       c.id AS country_id, c.name AS country_name, c.name_ar AS country_name_ar, c.code AS country_code
                FROM subjects s
                JOIN grades g ON g.id = s.grade_id
                JOIN education_systems es ON es.id = g.education_system_id
                JOIN countries c ON c.id = es.country_id
                WHERE s.id = %s
                """,
                (subject_id,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        for k, v in list(d.items()):
            if v is not None and hasattr(v, "hex"):
                d[k] = str(v)
        return d

    # --- Books ---

    def create_book(
        self,
        resource_id: str,
        original_filename: str,
        stored_path: str,
        size_bytes: int,
        sha256: str,
        metadata: dict[str, Any],
        *,
        subject_id: str | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        with self.pool.connection() as conn:
            conn.execute(
                """INSERT INTO books(resource_id, subject_id, original_filename, stored_path, size_bytes, sha256, metadata_json, created_by)
                   VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)""",
                (
                    resource_id, subject_id, original_filename, stored_path, size_bytes, sha256,
                    json.dumps(metadata, ensure_ascii=False), created_by,
                ),
            )
            conn.commit()
        return self.get_book(resource_id)  # type: ignore[return-value]

    def get_book(self, resource_id: str) -> dict[str, Any] | None:
        with self.pool.connection() as conn:
            row = conn.execute("SELECT * FROM books WHERE resource_id=%s", (resource_id,)).fetchone()
        book = self._normalize_row(row)
        if book and book.get("subject_id"):
            book["catalog_path"] = self.get_subject_path(book["subject_id"])
        return book

    def list_books(
        self,
        limit: int = 100,
        offset: int = 0,
        *,
        subject_id: str | None = None,
        grade_id: str | None = None,
        country_id: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        joins = ""
        if subject_id:
            clauses.append("b.subject_id=%s")
            params.append(subject_id)
        if grade_id:
            joins = " JOIN subjects sub ON sub.id = b.subject_id "
            clauses.append("sub.grade_id=%s")
            params.append(grade_id)
        if country_id:
            if not joins:
                joins = " JOIN subjects sub ON sub.id = b.subject_id JOIN grades g ON g.id = sub.grade_id JOIN education_systems es ON es.id = g.education_system_id "
            else:
                joins += " JOIN grades g ON g.id = sub.grade_id JOIN education_systems es ON es.id = g.education_system_id "
            clauses.append("es.country_id=%s")
            params.append(country_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.extend([limit, offset])
        with self.pool.connection() as conn:
            rows = conn.execute(
                f"SELECT b.* FROM books b{joins}{where} ORDER BY b.created_at DESC LIMIT %s OFFSET %s",
                params,
            ).fetchall()
        books = [self._normalize_row(r) for r in rows if r is not None]
        for book in books:
            if book and book.get("subject_id"):
                book["catalog_path"] = self.get_subject_path(book["subject_id"])
        return books  # type: ignore[return-value]

    # --- Jobs (same interface as before) ---

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
        with self.pool.connection() as conn:
            conn.execute(
                """INSERT INTO jobs(
                    job_id, book_resource_id, status, progress, stage, message,
                    start_page, end_page, resume, index_to_opensearch, recreate_index,
                    metadata_overrides_json, output_dir, retry_of, created_at, updated_at
                ) VALUES (%s, %s, 'queued', 0, 'queued', 'Waiting for an extraction worker',
                          %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)""",
                (
                    job_id, book_resource_id, start_page, end_page, resume, index_to_opensearch,
                    recreate_index, json.dumps(metadata_overrides, ensure_ascii=False), output_dir,
                    retry_of, now, now,
                ),
            )
            conn.commit()
        self.add_event(job_id, "queued", stage="queued", progress=0, message="Job queued")
        return self.get_job(job_id)  # type: ignore[return-value]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.pool.connection() as conn:
            return self._normalize_row(conn.execute("SELECT * FROM jobs WHERE job_id=%s", (job_id,)).fetchone())

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
            clauses.append("status=%s")
            params.append(status)
        if book_resource_id:
            clauses.append("book_resource_id=%s")
            params.append(book_resource_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.extend([limit, offset])
        with self.pool.connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM jobs{where} ORDER BY created_at DESC LIMIT %s OFFSET %s", params
            ).fetchall()
        return [self._normalize_row(r) for r in rows if r is not None]  # type: ignore[list-item]

    def claim_next_job(self) -> dict[str, Any] | None:
        now = utcnow()
        with self.pool.connection() as conn:
            row = conn.execute(
                """
                WITH next_job AS (
                    SELECT job_id FROM jobs WHERE status='queued'
                    ORDER BY created_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED
                )
                UPDATE jobs SET status='running', stage='starting', message='Worker started',
                       started_at=COALESCE(started_at, %s), updated_at=%s
                FROM next_job WHERE jobs.job_id = next_job.job_id
                RETURNING jobs.*
                """,
                (now, now),
            ).fetchone()
            conn.commit()
        if not row:
            return None
        job_id = row["job_id"]
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
        with self.pool.connection() as conn:
            conn.execute(
                """UPDATE jobs SET progress=%s, stage=%s, message=%s, current_page=%s,
                   total_pages=COALESCE(%s, total_pages), updated_at=%s WHERE job_id=%s""",
                (progress, stage, message, current_page, total_pages, now, job_id),
            )
            conn.commit()
        if add_event:
            self.add_event(
                job_id, "progress", stage=stage, progress=progress, message=message,
                payload={"current_page": current_page, "total_pages": total_pages},
            )

    def complete_job(self, job_id: str, *, result: dict[str, Any]) -> None:
        now = utcnow()
        with self.pool.connection() as conn:
            conn.execute(
                """UPDATE jobs SET status='completed', progress=100, stage='completed', message='Completed',
                   book_id=%s, extracted_records=%s, visual_assets=%s, indexed_records=%s, result_json=%s::jsonb,
                   finished_at=%s, updated_at=%s WHERE job_id=%s""",
                (
                    result.get("book_id"), result.get("extracted_records"), result.get("visual_assets"),
                    result.get("indexed_records"), json.dumps(result, ensure_ascii=False), now, now, job_id,
                ),
            )
            conn.commit()
        self.add_event(job_id, "completed", stage="completed", progress=100, message="Job completed", payload=result)

    def fail_job(self, job_id: str, error: str, traceback_text: str | None = None) -> None:
        now = utcnow()
        with self.pool.connection() as conn:
            conn.execute(
                """UPDATE jobs SET status='failed', stage='failed', message=%s, error=%s, traceback=%s,
                   finished_at=%s, updated_at=%s WHERE job_id=%s""",
                (error[:2000], error, traceback_text, now, now, job_id),
            )
            conn.commit()
        self.add_event(job_id, "failed", stage="failed", message=error[:1000])

    def request_cancel(self, job_id: str) -> dict[str, Any] | None:
        job = self.get_job(job_id)
        if not job:
            return None
        now = utcnow()
        if job["status"] == "queued":
            with self.pool.connection() as conn:
                conn.execute(
                    """UPDATE jobs SET status='cancelled', stage='cancelled', message='Cancelled before execution',
                       finished_at=%s, updated_at=%s WHERE job_id=%s AND status='queued'""",
                    (now, now, job_id),
                )
                conn.commit()
            self.add_event(job_id, "cancelled", stage="cancelled", progress=job.get("progress"), message="Cancelled before execution")
        elif job["status"] == "running":
            with self.pool.connection() as conn:
                conn.execute(
                    """UPDATE jobs SET status='cancel_requested', stage='cancel_requested',
                       message='Cancellation requested', updated_at=%s WHERE job_id=%s AND status='running'""",
                    (now, job_id),
                )
                conn.commit()
            self.add_event(job_id, "cancel_requested", stage="cancel_requested", progress=job.get("progress"), message="Cancellation requested")
        return self.get_job(job_id)

    def mark_cancelled(self, job_id: str, message: str = "Job cancelled") -> None:
        now = utcnow()
        with self.pool.connection() as conn:
            conn.execute(
                """UPDATE jobs SET status='cancelled', stage='cancelled', message=%s, finished_at=%s, updated_at=%s
                   WHERE job_id=%s""",
                (message, now, now, job_id),
            )
            conn.commit()
        self.add_event(job_id, "cancelled", stage="cancelled", message=message)

    def is_cancel_requested(self, job_id: str) -> bool:
        with self.pool.connection() as conn:
            row = conn.execute("SELECT status FROM jobs WHERE job_id=%s", (job_id,)).fetchone()
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
        with self.pool.connection() as conn:
            conn.execute(
                """INSERT INTO job_events(job_id, event_type, stage, progress, message, payload_json)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    job_id, event_type, stage, progress, message,
                    json.dumps(payload, ensure_ascii=False) if payload is not None else None,
                ),
            )
            conn.commit()

    def list_events(self, job_id: str, *, after_id: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        with self.pool.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM job_events WHERE job_id=%s AND id>%s ORDER BY id ASC LIMIT %s",
                (job_id, after_id, limit),
            ).fetchall()
        return [self._normalize_row(r) for r in rows if r is not None]  # type: ignore[list-item]

    def recover_incomplete_jobs(self) -> dict[str, int]:
        now = utcnow()
        with self.pool.connection() as conn:
            cancelled = conn.execute(
                """UPDATE jobs SET status='cancelled', stage='cancelled', message='Cancelled during service restart',
                   finished_at=%s, updated_at=%s WHERE status='cancel_requested'""",
                (now, now),
            ).rowcount
            requeued = conn.execute(
                """UPDATE jobs SET status='queued', stage='queued', message='Recovered after service restart',
                   started_at=NULL, updated_at=%s WHERE status='running'""",
                (now,),
            ).rowcount
            conn.commit()
        return {"requeued": requeued, "cancelled": cancelled}

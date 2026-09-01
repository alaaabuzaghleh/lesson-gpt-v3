import os
import uuid

import pytest

from book_ingestor.api.job_store import JobStore


@pytest.fixture
def store():
    url = os.environ.get("TEST_DATABASE_URL", os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/lessons_gpt_test"))
    try:
        s = JobStore(url)
    except Exception as exc:
        pytest.skip(f"PostgreSQL not available: {exc}")
    with s.pool.connection() as conn:
        conn.execute("TRUNCATE job_events, jobs, books RESTART IDENTITY CASCADE")
        conn.commit()
    yield s
    s.close()


def _book(store: JobStore, tmp_path, subject_id: str | None = None):
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF")
    return store.create_book(
        resource_id=uuid.uuid4().hex,
        original_filename="كتاب-test.pdf",
        stored_path=str(pdf),
        size_bytes=pdf.stat().st_size,
        sha256="abc",
        metadata={"country": "Jordan", "language": "ar,en"},
        subject_id=subject_id,
    )


def test_persistent_job_lifecycle(store, tmp_path):
    book = _book(store, tmp_path)
    job = store.create_job(
        job_id=uuid.uuid4().hex,
        book_resource_id=book["resource_id"],
        output_dir=str(tmp_path / "out"),
        start_page=1,
        end_page=10,
        resume=True,
        index_to_opensearch=False,
        recreate_index=False,
        metadata_overrides={"subject": "Science"},
    )
    assert job["status"] == "queued"

    claimed = store.claim_next_job()
    assert claimed is not None
    assert claimed["status"] == "running"

    store.update_progress(
        claimed["job_id"], progress=42.5, stage="page_extraction", message="page 4", current_page=4, total_pages=10
    )
    current = store.get_job(claimed["job_id"])
    assert current["progress"] == 42.5
    assert current["current_page"] == 4

    store.complete_job(claimed["job_id"], result={"book_id": "semantic-book-id", "extracted_records": 120, "visual_assets": 9, "indexed_records": 0})
    done = store.get_job(claimed["job_id"])
    assert done["status"] == "completed"
    assert done["progress"] == 100
    assert done["book_id"] == "semantic-book-id"
    assert store.list_events(claimed["job_id"])[-1]["event_type"] == "completed"


def test_cancel_queued_and_running_jobs(store, tmp_path):
    book = _book(store, tmp_path)
    qid = uuid.uuid4().hex
    store.create_job(
        job_id=qid,
        book_resource_id=book["resource_id"],
        output_dir=str(tmp_path / "q"),
        start_page=1,
        end_page=None,
        resume=True,
        index_to_opensearch=False,
        recreate_index=False,
        metadata_overrides={},
    )
    assert store.request_cancel(qid)["status"] == "cancelled"

    rid = uuid.uuid4().hex
    store.create_job(
        job_id=rid,
        book_resource_id=book["resource_id"],
        output_dir=str(tmp_path / "r"),
        start_page=1,
        end_page=None,
        resume=True,
        index_to_opensearch=False,
        recreate_index=False,
        metadata_overrides={},
    )
    claimed = store.claim_next_job()
    assert claimed is not None
    assert store.request_cancel(claimed["job_id"])["status"] == "cancel_requested"
    assert store.is_cancel_requested(claimed["job_id"]) is True
    store.mark_cancelled(claimed["job_id"])
    assert store.get_job(claimed["job_id"])["status"] == "cancelled"


def test_restart_recovery(store, tmp_path):
    book = _book(store, tmp_path)
    jid = uuid.uuid4().hex
    store.create_job(
        job_id=jid,
        book_resource_id=book["resource_id"],
        output_dir=str(tmp_path / "out"),
        start_page=1,
        end_page=None,
        resume=True,
        index_to_opensearch=False,
        recreate_index=False,
        metadata_overrides={},
    )
    claimed = store.claim_next_job()
    assert claimed is not None
    assert claimed["job_id"] == jid
    assert claimed["status"] == "running"
    result = store.recover_incomplete_jobs()
    assert result["requeued"] >= 1
    assert store.get_job(jid)["status"] == "queued"

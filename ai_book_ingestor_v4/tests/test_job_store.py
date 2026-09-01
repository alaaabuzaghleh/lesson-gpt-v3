from pathlib import Path

from book_ingestor.api.job_store import JobStore


def _book(store: JobStore, tmp_path: Path):
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF")
    return store.create_book(
        resource_id="book1",
        original_filename="كتاب-test.pdf",
        stored_path=str(pdf),
        size_bytes=pdf.stat().st_size,
        sha256="abc",
        metadata={"country": "Jordan", "language": "ar,en"},
    )


def test_persistent_job_lifecycle(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    _book(store, tmp_path)
    job = store.create_job(
        job_id="job1",
        book_resource_id="book1",
        output_dir=str(tmp_path / "out"),
        start_page=1,
        end_page=10,
        resume=True,
        index_to_opensearch=False,
        recreate_index=False,
        metadata_overrides={"subject": "Science"},
    )
    assert job["status"] == "queued"
    assert job["metadata_overrides"]["subject"] == "Science"

    claimed = store.claim_next_job()
    assert claimed is not None
    assert claimed["job_id"] == "job1"
    assert claimed["status"] == "running"

    store.update_progress(
        "job1", progress=42.5, stage="page_extraction", message="page 4", current_page=4, total_pages=10
    )
    current = store.get_job("job1")
    assert current["progress"] == 42.5
    assert current["current_page"] == 4

    store.complete_job("job1", result={"book_id": "semantic-book-id", "extracted_records": 120, "visual_assets": 9, "indexed_records": 0})
    done = store.get_job("job1")
    assert done["status"] == "completed"
    assert done["progress"] == 100
    assert done["book_id"] == "semantic-book-id"
    assert store.list_events("job1")[-1]["event_type"] == "completed"


def test_cancel_queued_and_running_jobs(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    _book(store, tmp_path)

    store.create_job(
        job_id="queued",
        book_resource_id="book1",
        output_dir=str(tmp_path / "q"),
        start_page=1,
        end_page=None,
        resume=True,
        index_to_opensearch=False,
        recreate_index=False,
        metadata_overrides={},
    )
    assert store.request_cancel("queued")["status"] == "cancelled"

    store.create_job(
        job_id="running",
        book_resource_id="book1",
        output_dir=str(tmp_path / "r"),
        start_page=1,
        end_page=None,
        resume=True,
        index_to_opensearch=False,
        recreate_index=False,
        metadata_overrides={},
    )
    assert store.claim_next_job()["job_id"] == "running"
    assert store.request_cancel("running")["status"] == "cancel_requested"
    assert store.is_cancel_requested("running") is True
    store.mark_cancelled("running")
    assert store.get_job("running")["status"] == "cancelled"


def test_restart_recovery(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    _book(store, tmp_path)
    store.create_job(
        job_id="recover-me",
        book_resource_id="book1",
        output_dir=str(tmp_path / "out"),
        start_page=1,
        end_page=None,
        resume=True,
        index_to_opensearch=False,
        recreate_index=False,
        metadata_overrides={},
    )
    store.claim_next_job()
    assert store.get_job("recover-me")["status"] == "running"
    result = store.recover_incomplete_jobs()
    assert result["requeued"] == 1
    assert store.get_job("recover-me")["status"] == "queued"

import os
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from book_ingestor.api.job_store import JobStore
from book_ingestor.api import worker as worker_module
from book_ingestor.config import settings


class FakeMetadata:
    def model_dump(self, mode=None):
        return {"title": "كتاب / Book", "subject": "Science", "language": "ar,en"}


class FakeDoc:
    def __init__(self, content_type="definition", asset_id=None):
        self.content_type = content_type
        self.asset_id = asset_id

    def model_dump(self, mode=None):
        return {"id": "x", "content_type": self.content_type, "asset_id": self.asset_id}


class FakePipeline:
    def __init__(self, pdf_path, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(self, overrides, start_page=1, end_page=None, resume=True, progress_callback=None, cancel_check=None, **kwargs):
        if progress_callback:
            progress_callback({"stage": "metadata", "progress": 5, "message": "metadata", "total_pages": 2})
            progress_callback({"stage": "page_extraction", "progress": 60, "message": "page 2", "current_page": 2, "total_pages": 2})
            progress_callback({"stage": "extraction_complete", "progress": 95, "message": "done"})
        (self.output_dir / "quality_report.json").write_text(
            '{"recommended_for_live_index": true, "processing_coverage": 1.0, "questions_count": 1, "visual_assets_count": 1}',
            encoding="utf-8",
        )
        (self.output_dir / "manifest.json").write_text('{"schema_version": 3}', encoding="utf-8")
        (self.output_dir / "index").mkdir(exist_ok=True)
        (self.output_dir / "index" / "documents.jsonl").write_text('{}\n', encoding="utf-8")
        return FakeMetadata(), "book-semantic-id", [FakeDoc("question"), FakeDoc("figure", "asset-1")]


@pytest.fixture
def pg_store():
    url = os.environ.get("TEST_DATABASE_URL", os.environ.get("DATABASE_URL", settings.database_url))
    try:
        store = JobStore(url)
    except Exception as exc:
        pytest.skip(f"PostgreSQL not available: {exc}")
    with store.pool.connection() as conn:
        conn.execute("TRUNCATE job_events, jobs, books RESTART IDENTITY CASCADE")
        conn.commit()
    yield store
    store.close()


def test_worker_completes_persisted_background_job(tmp_path, monkeypatch, pg_store):
    store = pg_store
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF")
    resource_id = f"b-{uuid.uuid4().hex[:12]}"
    store.create_book(resource_id, "book.pdf", str(pdf), pdf.stat().st_size, "hash", {"country": "Jordan"})
    job_id = f"j-{uuid.uuid4().hex[:12]}"
    store.create_job(
        job_id=job_id,
        book_resource_id=resource_id,
        output_dir=str(tmp_path / "out"),
        start_page=1,
        end_page=None,
        resume=True,
        index_to_opensearch=False,
        recreate_index=False,
        metadata_overrides={},
    )
    job = store.claim_next_job()
    assert job is not None
    assert job["job_id"] == job_id
    monkeypatch.setattr(worker_module, "BookIngestionPipeline", FakePipeline)
    pool = worker_module.ExtractionWorkerPool(store, worker_count=1)
    pool._run_job(job)
    done = store.get_job(job_id)
    assert done["status"] == "completed"
    assert done["progress"] == 100
    assert done["book_id"] == "book-semantic-id"
    assert done["extracted_records"] == 2
    assert done["visual_assets"] == 1
    assert done["result"]["questions"] == 1


def test_worker_records_readable_pipeline_failure(tmp_path, monkeypatch, pg_store):
    class BoomPipeline:
        def __init__(self, pdf_path, output_dir):
            pass

        def run(self, *args, **kwargs):
            raise RuntimeError("Vision model returned empty content (finish_reason='stop')")

    store = pg_store
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF")
    resource_id = f"b-{uuid.uuid4().hex[:12]}"
    store.create_book(resource_id, "book.pdf", str(pdf), pdf.stat().st_size, "hash", {"country": "Jordan"})
    job_id = f"j-{uuid.uuid4().hex[:12]}"
    store.create_job(
        job_id=job_id,
        book_resource_id=resource_id,
        output_dir=str(tmp_path / "out"),
        start_page=1,
        end_page=None,
        resume=True,
        index_to_opensearch=False,
        recreate_index=False,
        metadata_overrides={},
    )
    job = store.claim_next_job()
    monkeypatch.setattr(worker_module, "BookIngestionPipeline", BoomPipeline)
    pool = worker_module.ExtractionWorkerPool(store, worker_count=1)
    pool._run_job(job)
    done = store.get_job(job_id)
    assert done["status"] == "failed"
    assert "empty content" in done["error"]
    failed = [event for event in store.list_events(job_id) if event["event_type"] == "failed"][-1]
    assert failed["payload"]["error"]
    assert failed["payload"]["traceback"]


def test_worker_pauses_when_pipeline_stops(tmp_path, monkeypatch, pg_store):
    from book_ingestor.pipeline import JobCancelled

    class StopPipeline:
        def __init__(self, pdf_path, output_dir):
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            (Path(output_dir) / "checkpoint.json").write_text(
                '{"book_id":"paused-book","indexed_pages":[1],"extracted_pages":[1,2]}',
                encoding="utf-8",
            )

        def run(self, *args, **kwargs):
            raise JobCancelled("Extraction job was stopped")

    store = pg_store
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF")
    resource_id = f"b-{uuid.uuid4().hex[:12]}"
    store.create_book(resource_id, "book.pdf", str(pdf), pdf.stat().st_size, "hash", {"country": "Jordan"})
    job_id = f"j-{uuid.uuid4().hex[:12]}"
    store.create_job(
        job_id=job_id,
        book_resource_id=resource_id,
        output_dir=str(tmp_path / "out"),
        start_page=1,
        end_page=None,
        resume=True,
        index_to_opensearch=False,
        recreate_index=False,
        metadata_overrides={},
    )
    job = store.claim_next_job()
    monkeypatch.setattr(worker_module, "BookIngestionPipeline", StopPipeline)
    pool = worker_module.ExtractionWorkerPool(store, worker_count=1)
    pool._run_job(job)
    done = store.get_job(job_id)
    assert done["status"] == "paused"
    assert done["checkpoint"]["indexed_pages"] == [1]

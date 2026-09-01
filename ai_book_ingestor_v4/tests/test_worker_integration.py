from pathlib import Path
from types import SimpleNamespace

from book_ingestor.api.job_store import JobStore
from book_ingestor.api import worker as worker_module


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

    def run(self, overrides, start_page=1, end_page=None, resume=True, progress_callback=None, cancel_check=None):
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


def test_worker_completes_persisted_background_job(tmp_path, monkeypatch):
    store = JobStore(tmp_path / "jobs.sqlite3")
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF")
    store.create_book("b1", "book.pdf", str(pdf), pdf.stat().st_size, "hash", {"country": "Jordan"})
    store.create_job(
        job_id="j1",
        book_resource_id="b1",
        output_dir=str(tmp_path / "out"),
        start_page=1,
        end_page=None,
        resume=True,
        index_to_opensearch=False,
        recreate_index=False,
        metadata_overrides={},
    )
    job = store.claim_next_job()
    monkeypatch.setattr(worker_module, "BookIngestionPipeline", FakePipeline)
    pool = worker_module.ExtractionWorkerPool(store, worker_count=1)
    pool._run_job(job)
    done = store.get_job("j1")
    assert done["status"] == "completed"
    assert done["progress"] == 100
    assert done["book_id"] == "book-semantic-id"
    assert done["extracted_records"] == 2
    assert done["visual_assets"] == 1
    assert done["result"]["questions"] == 1

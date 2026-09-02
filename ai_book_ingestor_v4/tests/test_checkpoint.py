from pathlib import Path

from book_ingestor.checkpoint import JobCheckpoint, checkpoint_path


def test_checkpoint_round_trip(tmp_path: Path):
    ckpt = JobCheckpoint(book_id="book-1", stage="indexing", current_page=3, total_pages=10)
    ckpt.mark_extracted(1)
    ckpt.mark_extracted(2)
    ckpt.mark_indexed(1)
    ckpt.extracted_records = 8
    path = checkpoint_path(tmp_path)
    saved = ckpt.save(path)
    assert path.exists()
    assert saved["extracted_pages"] == [1, 2]
    assert saved["indexed_pages"] == [1]

    loaded = JobCheckpoint.load(path)
    assert loaded is not None
    assert loaded.book_id == "book-1"
    assert loaded.extracted_pages == [1, 2]
    assert loaded.indexed_pages == [1]
    assert loaded.extracted_records == 8


def test_hydrate_from_artifacts_does_not_mark_jsonl_as_indexed(tmp_path: Path):
    extracted = tmp_path / "extracted_pages"
    extracted.mkdir()
    (extracted / "page_0001.json").write_text("{}", encoding="utf-8")
    (extracted / "page_0002.json").write_text("{}", encoding="utf-8")
    jsonl = tmp_path / "index" / "documents.jsonl"
    jsonl.parent.mkdir()
    jsonl.write_text(
        '{"id":"a","book_id":"book-9","pdf_page_number":1,"asset_id":"x"}\n'
        '{"id":"b","book_id":"book-9","pdf_page_number":2}\n',
        encoding="utf-8",
    )

    ckpt = JobCheckpoint()
    ckpt.hydrate_from_artifacts(extracted, jsonl)
    assert ckpt.extracted_pages == [1, 2]
    assert ckpt.indexed_pages == []
    assert ckpt.book_id == "book-9"
    assert ckpt.extracted_records == 2
    assert ckpt.visual_assets == 1

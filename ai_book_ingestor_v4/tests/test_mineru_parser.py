import io
import json
import zipfile
from pathlib import Path

import pytest

from book_ingestor.mineru_parser import (
    MinerUBlock,
    MinerUDocument,
    MinerUError,
    MinerUPage,
    format_mineru_page_text,
    load_mineru_document,
    mineru_bbox_dict,
    mineru_block_is_indexable,
    mineru_content_type,
    mineru_ocr_language,
    parse_content_list,
    parse_content_list_v2,
    parse_middle_json,
    parse_via_http_api,
)
from book_ingestor.prompts import page_prompt


def test_mineru_ocr_language_maps_arabic_and_english():
    assert mineru_ocr_language("ar") == "arabic"
    assert mineru_ocr_language("mixed") == "arabic"
    assert mineru_ocr_language("en,ar") == "arabic"
    assert mineru_ocr_language("en") == "ch"
    assert mineru_ocr_language("korean") == "korean"
    assert mineru_ocr_language(None) == "arabic"


def test_parse_content_list_restores_reversed_arabic():
    pages = parse_content_list(
        [
            {
                "type": "title",
                "text": "ميلعتلا ةرازو",
                "text_level": 1,
                "page_idx": 0,
            },
            {
                "type": "text",
                "text": "تاراسملا ماظن",
                "page_idx": 0,
            },
            {
                "type": "text",
                "text": "لحلا ناف،وه نيددعلل ربكالا كرتشملا مساقلا نا امب",
                "page_idx": 0,
            },
        ]
    )
    assert "وزارة التعليم" in pages[1].text
    assert "نظام المسارات" in pages[1].text
    assert "القاسم المشترك" in pages[1].text
    assert "لحلا" not in pages[1].text


def test_parse_content_list_applies_page_offset_and_formats_tables():
    items = [
        {
            "type": "title",
            "text": "الوحدة الأولى",
            "text_level": 1,
            "bbox": [10, 20, 400, 80],
            "page_idx": 0,
        },
        {
            "type": "table",
            "table_caption": ["جدول 1"],
            "table_body": "<table><tr><td>1</td></tr></table>",
            "page_idx": 0,
        },
        {
            "type": "equation",
            "text": "$$F = ma$$",
            "page_idx": 1,
        },
    ]
    pages = parse_content_list(items, page_offset=9)
    assert set(pages) == {10, 11}
    assert "الوحدة الأولى" in pages[10].text
    assert "[table]" in pages[10].text
    assert "جدول 1" in pages[10].text
    assert "$$F = ma$$" in pages[11].text
    assert pages[10].blocks[0].bbox == [10, 20, 400, 80]


def test_parse_content_list_v2_groups_by_page():
    pages = parse_content_list_v2(
        [
            [
                {
                    "type": "title",
                    "content": {"title_content": [{"type": "text", "content": "Lesson 2"}], "level": 1},
                    "bbox": [1, 2, 3, 4],
                },
                {
                    "type": "paragraph",
                    "content": {"paragraph_content": [{"type": "text", "content": "Newton's second law"}]},
                },
            ]
        ]
    )
    assert pages[1].text.startswith("# Lesson 2")
    assert "Newton's second law" in pages[1].text


def test_parse_middle_json_reads_para_blocks():
    pages = parse_middle_json(
        {
            "pdf_info": [
                {
                    "page_idx": 0,
                    "para_blocks": [
                        {
                            "type": "text",
                            "bbox": [1, 2, 3, 4],
                            "lines": [{"spans": [{"content": "Visible sentence", "type": "text"}]}],
                        }
                    ],
                }
            ]
        }
    )
    assert pages[1].text == "Visible sentence"


def test_format_mineru_page_text_skips_headers_and_empty_blocks():
    text = format_mineru_page_text(
        [
            MinerUBlock(type="page_header", text="Grade 8 Science"),
            MinerUBlock(type="text", text="Body paragraph"),
            MinerUBlock(type="image", text="شكل 3-1 الدورة"),
            MinerUBlock(type="text", text=""),
        ]
    )
    assert "Grade 8 Science" not in text
    assert "Body paragraph" in text
    assert "[image] شكل 3-1 الدورة" in text


def test_load_mineru_document_prefers_content_list(tmp_path: Path):
    folder = tmp_path / "book" / "auto"
    folder.mkdir(parents=True)
    (folder / "book_content_list.json").write_text(
        json.dumps(
            [
                {"type": "text", "text": "Cached page", "page_idx": 0, "bbox": [0, 0, 10, 10]},
            ]
        ),
        encoding="utf-8",
    )
    document = load_mineru_document(tmp_path)
    assert document is not None
    assert document.page(1) is not None
    assert document.page(1).text == "Cached page"


def test_page_prompt_includes_mineru_hints():
    prompt = page_prompt(
        12,
        "قانون نيوتن الثاني",
        {"title": "Science"},
        text_source="mineru",
        structured_blocks='[{"type":"equation","text":"$$F=ma$$"}]',
    )
    assert "MinerU reading-order extract" in prompt
    assert "قانون نيوتن الثاني" in prompt
    assert "BEGIN MINERU BLOCKS" in prompt
    assert "$$F=ma$$" in prompt


def test_parse_via_http_api_submits_task_and_extracts_zip(tmp_path: Path, monkeypatch):
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF")
    out = tmp_path / "mineru"

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as archive:
        archive.writestr(
            "book/auto/book_content_list.json",
            json.dumps([{"type": "text", "text": "From API", "page_idx": 0}]),
        )

    class FakeResponse:
        def __init__(self, status_code, payload=None, content=b"", text=""):
            self.status_code = status_code
            self._payload = payload
            self.content = content
            self.text = text

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(self.status_code)

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, data=None, files=None):
            self.calls.append(("post", url, data))
            return FakeResponse(
                202,
                {
                    "task_id": "t1",
                    "status_url": "/tasks/t1",
                    "result_url": "/tasks/t1/result",
                },
            )

        def get(self, url, timeout=None):
            if url.endswith("/tasks/t1"):
                return FakeResponse(200, {"status": "completed"})
            return FakeResponse(200, content=zip_buf.getvalue())

    monkeypatch.setattr("book_ingestor.mineru_parser.settings.mineru_api_url", "http://mineru.local")
    monkeypatch.setattr("book_ingestor.mineru_parser.httpx.Client", FakeClient)

    document = parse_via_http_api(
        pdf, out, language="arabic", start_page=1, end_page=1
    )
    assert document.page(1).text == "From API"
    assert document.source == "mineru-api"


def test_http_api_rejects_zip_path_traversal(tmp_path: Path, monkeypatch):
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as archive:
        archive.writestr("../escape.json", "{}")

    class FakeResponse:
        status_code = 202
        content = zip_buf.getvalue()
        text = ""

        def json(self):
            return {"task_id": "t1", "status_url": "/tasks/t1", "result_url": "/tasks/t1/result"}

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            return FakeResponse()

        def get(self, url, timeout=None):
            if url.endswith("/result"):
                return FakeResponse()
            resp = FakeResponse()
            resp.json = lambda: {"status": "completed"}
            return resp

    monkeypatch.setattr("book_ingestor.mineru_parser.settings.mineru_api_url", "http://mineru.local")
    monkeypatch.setattr("book_ingestor.mineru_parser.httpx.Client", FakeClient)

    with pytest.raises(MinerUError, match="unsafe"):
        parse_via_http_api(pdf, tmp_path / "out", language="arabic", start_page=1, end_page=1)


def test_pdf_reader_prefers_mineru_text(tmp_path: Path):
    import fitz

    from book_ingestor.pdf_reader import PDFReader

    pdf = tmp_path / "tiny.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "raw pdf layer")
    doc.save(pdf)
    doc.close()

    reader = PDFReader(pdf, tmp_path / "work", dpi=72)
    reader.attach_mineru(
        MinerUDocument(
            pages={
                1: MinerUPage(
                    pdf_page_number=1,
                    blocks=[MinerUBlock(type="text", text="mineru reading order")],
                )
            }
        )
    )
    rendered = reader.render_page(1)
    assert rendered.text_source == "mineru"
    assert rendered.text_layer == "mineru reading order"
    reader.close()


def test_mineru_content_type_and_bbox_helpers():
    title = MinerUBlock(type="title", text="الوحدة الأولى", extra={"text_level": 1}, bbox=[10, 20, 400, 80])
    assert mineru_content_type(title) == "unit_title"
    assert mineru_bbox_dict(title) == {"x1": 10, "y1": 20, "x2": 400, "y2": 80}
    assert mineru_content_type(MinerUBlock(type="equation", text="F=ma")) == "equation"
    assert not mineru_block_is_indexable(MinerUBlock(type="page_header", text="Grade 8"))
    assert mineru_block_is_indexable(MinerUBlock(type="text", text="body"))


def test_pipeline_builds_opensearch_ocr_documents(tmp_path: Path):
    import fitz

    from book_ingestor.pipeline import BookIngestionPipeline
    from book_ingestor.schemas import BookMetadata

    pdf = tmp_path / "tiny.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "raw pdf layer")
    doc.save(pdf)
    doc.close()

    pipeline = BookIngestionPipeline(pdf, tmp_path / "out")
    pipeline.reader.attach_mineru(
        MinerUDocument(
            pages={
                1: MinerUPage(
                    pdf_page_number=1,
                    blocks=[
                        MinerUBlock(type="title", text="الوحدة الأولى", extra={"text_level": 1}, bbox=[10, 20, 400, 80]),
                        MinerUBlock(type="text", text="قانون نيوتن الثاني", bbox=[10, 100, 800, 200]),
                        MinerUBlock(type="page_header", text="should skip"),
                    ],
                )
            },
            source="mineru",
        )
    )
    docs = pipeline._build_ocr_documents(BookMetadata(title="Science", language="ar"), "book1", 1)
    pipeline.reader.close()

    assert any(d.content_type == "ocr_page" and "قانون نيوتن الثاني" in d.ocr_text for d in docs)
    assert any(d.subtype == "ocr_block" and d.content_type == "unit_title" for d in docs)
    assert any(d.subtype == "ocr_block" and "قانون نيوتن الثاني" in d.text for d in docs)
    assert all("should skip" not in (d.text or "") for d in docs)
    assert all(d.ocr_source == "mineru" for d in docs)


def test_pipeline_indexes_empty_page_as_ocr_page(tmp_path: Path):
    import fitz

    from book_ingestor.pipeline import BookIngestionPipeline
    from book_ingestor.schemas import BookMetadata

    pdf = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(pdf)
    doc.close()

    pipeline = BookIngestionPipeline(pdf, tmp_path / "out")
    docs = pipeline._build_ocr_documents(BookMetadata(title="Blank", language="ar"), "book1", 1)
    pipeline.reader.close()
    assert len(docs) == 1
    assert docs[0].content_type == "ocr_page"
    assert "empty_page" in docs[0].extraction_notes


def test_ocr_only_run_checkpoints_each_page(tmp_path: Path, monkeypatch):
    import fitz

    from book_ingestor.checkpoint import JobCheckpoint, checkpoint_path
    from book_ingestor.pipeline import BookIngestionPipeline

    monkeypatch.setattr("book_ingestor.pipeline.settings.mineru_enabled", False)
    monkeypatch.setattr("book_ingestor.pipeline.settings.vlm_page_extraction_enabled", False)

    pdf = tmp_path / "book.pdf"
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((72, 72), "الصفحة الأولى")
    page2 = doc.new_page()
    page2.insert_text((72, 72), "الصفحة الثانية")
    doc.save(pdf)
    doc.close()

    seen: list[int] = []

    def on_page(page_no, docs):
        seen.append(page_no)
        assert any(d.content_type == "ocr_page" for d in docs)

    pipeline = BookIngestionPipeline(pdf, tmp_path / "out")
    metadata, book_id, docs = pipeline.run(
        {"title": "رياضيات", "language": "ar", "subject": "الرياضيات"},
        ocr_only=True,
        page_docs_callback=on_page,
    )
    pipeline.reader.close()

    assert seen == [1, 2]
    assert book_id
    assert metadata.title == "رياضيات"
    assert sum(1 for d in docs if d.content_type == "ocr_page") == 2
    ckpt = JobCheckpoint.load(checkpoint_path(tmp_path / "out"))
    assert ckpt is not None
    assert ckpt.ocr_pages == [1, 2]
    assert ckpt.stage == "extraction_complete"

    seen.clear()
    pipeline2 = BookIngestionPipeline(pdf, tmp_path / "out")
    pipeline2.run(
        {"title": "رياضيات", "language": "ar"},
        ocr_only=True,
        resume=True,
        page_docs_callback=on_page,
    )
    pipeline2.reader.close()
    assert seen == []


def test_load_incremental_mineru_document_merges_page_caches(tmp_path: Path):
    from book_ingestor.mineru_parser import load_incremental_mineru_document

    page1 = tmp_path / "mineru_pages" / "page_0001"
    page1.mkdir(parents=True)
    (page1 / "parse_meta.json").write_text('{"page_offset": 0, "start_page": 1}', encoding="utf-8")
    (page1 / "book_content_list.json").write_text(
        json.dumps([{"type": "text", "text": "one", "page_idx": 0}]),
        encoding="utf-8",
    )
    page3 = tmp_path / "mineru_pages" / "page_0003"
    page3.mkdir(parents=True)
    (page3 / "parse_meta.json").write_text('{"page_offset": 2, "start_page": 3}', encoding="utf-8")
    (page3 / "book_content_list.json").write_text(
        json.dumps([{"type": "text", "text": "three", "page_idx": 0}]),
        encoding="utf-8",
    )

    document = load_incremental_mineru_document(tmp_path)
    assert document is not None
    assert set(document.pages) == {1, 3}
    assert "one" in document.page(1).text
    assert "three" in document.page(3).text
